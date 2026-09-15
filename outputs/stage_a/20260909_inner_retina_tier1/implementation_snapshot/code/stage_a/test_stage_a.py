"""Synthetic invariants plus frozen-cache integrity; no held-out predictions."""
import copy
import json
import random
import tempfile
import unittest
from pathlib import Path
import numpy as np
import torch
from eight_surface.config import CASCADE_VERSION
from eight_surface.segment import prepare_bscan,detect_orientation
from .common import DEFAULT,verify,write_json,output_dir
from .eligibility import supervision,scope,region_targets
from .geometry import preprocess,label_offset,to_disk_rows
from .metrics import stats,evaluate
from .model import BoundaryUNet,losses,decode
from .partitions import validate_partition
from .train import save_checkpoint,load_checkpoint
from .inference import thickness,test_guard,prediction


def record(width=512):
    rows=np.repeat(np.arange(8)[:,None]*10.+10,width,axis=1)
    return dict(surfaces=rows,verdict="corrected",surface_edited=np.ones(8,bool),
        surface_displaced=np.zeros(8,bool),surface_visible=np.ones(8,bool),
        surface_reliable=np.ones(8,bool),region_excluded=np.zeros(width,bool),
        cascade_version=CASCADE_VERSION)


class StageATests(unittest.TestCase):
    def test_localized_100um_error_detected(self):
        d=np.zeros(512); d[210:261]=100
        s=stats(d,np.ones(512,bool),np.ones(512,bool))
        self.assertEqual(s["median_abs_um"],0)
        self.assertEqual(s["p95_abs_um"],100)
        self.assertAlmostEqual(s["gross_error_fraction_of_eligible"],51/512)
        self.assertEqual(s["longest_gross_error_columns"],51)
        self.assertAlmostEqual(s["longest_gross_error_um"],51*1460/512)

    def test_missing_predictions_do_not_disappear(self):
        d=np.zeros(100); d[10:40]=np.nan
        s=stats(d,np.ones(100,bool),np.ones(100,bool))
        self.assertEqual(s["n_eligible"],100)
        self.assertEqual(s["n_missing_or_abstained"],30)
        self.assertAlmostEqual(s["failure_fraction_of_eligible"],.3)
        self.assertIsNone(s["all_eligible_p90_um"])

    def test_abstention_cannot_hide_raw_failure(self):
        d=np.zeros(100); d[30:40]=100
        kept=np.ones(100,bool); kept[30:40]=False
        raw=stats(d,np.ones(100,bool),np.ones(100,bool))
        retained=stats(d,np.ones(100,bool),kept)
        self.assertEqual(raw["p95_abs_um"],100)
        self.assertEqual(retained["p95_abs_um"],0)
        self.assertEqual(retained["coverage"],.9)
        self.assertEqual(retained["failure_fraction_of_eligible"],.1)

    def test_absent_prediction_file_counts(self):
        r=dict(key="synthetic",animal="TS1",scan_id="synthetic",verdict="corrected",
            scope_status="control",qc_group="unknown",biological_group="WT",px_um=1.)
        t=dict(rows_label=np.zeros((8,10)),valid=np.ones((8,10),bool))
        report=evaluate([r],{"synthetic":t},{},{"synthetic":{"aline_um":2.}})
        for s in report["summary"]:
            self.assertEqual(s["coverage"],0)
            self.assertEqual(s["failure_fraction_of_eligible"],1)
            self.assertEqual(s["n_eligible"],10)

    def test_legacy_masks_displacement_and_exclusions(self):
        r=record(20)
        r["surface_displaced"][1]=True
        r["surface_edited"][2]=False
        r["surface_visible"][3]=False
        r["surface_reliable"][4]=False
        r["region_excluded"][5]=True
        allowed=np.ones(20,bool); allowed[7]=False
        shadow=np.zeros(20,bool); shadow[9]=True
        mask,_,_=supervision(r,allowed,shadow)
        self.assertFalse(mask[1:5].any())
        self.assertFalse(mask[:,[5,7,9]].any())
        self.assertEqual(int(mask.sum()),4*17)
        r["verdict"]="rejected"
        self.assertFalse(supervision(r,allowed)[0].any())

    def test_regions_require_two_valid_endpoints(self):
        r=record(4); rows=r["surfaces"]
        valid=np.zeros_like(rows,bool); valid[2:4]=True
        targets=region_targets(rows,valid,100)
        self.assertEqual(set(np.unique(targets)),{-100,2})
        valid[3,2]=False
        targets=region_targets(rows,valid,100)
        self.assertTrue((targets[:,2]==-100).all())
        self.assertTrue((targets[:10]==-100).all())
        self.assertTrue((targets[80:]==-100).all())

    def test_unknown_footprint_and_d0(self):
        md=dict(animal="TS283",day_label="D0",is_control=True)
        allowed,_,name,_=scope(md,None,(11,11))
        self.assertFalse(allowed.any())
        self.assertTrue(name.startswith("unknown"))
        foot=dict(reviewed=True,cnv_mask=np.zeros((11,11),bool))
        self.assertTrue(scope(md,foot,(11,11))[0].all())

    def test_physical_footprint_buffer(self):
        mask=np.zeros((11,11),bool); mask[5,5]=True
        foot=dict(reviewed=True,cnv_mask=mask,bscan_um=100.,aline_um=50.)
        allowed,d,_,_=scope({},foot,mask.shape,buffer_um=250)
        self.assertFalse(allowed[5,10])  # 250 micrometers exactly excluded
        self.assertTrue(allowed[8,5])   # 300 micrometers
        self.assertLess(d[5,5],0)

    def test_geometry_both_orientations_and_containment(self):
        raw=np.arange(12*96,dtype=np.float32).reshape(12,96)+1
        for vhi in (False,True):
            x,db,_=preprocess(raw,vhi)
            off=label_offset([10,80],96,vhi)
            self.assertTrue(np.array_equal(db[off:off+70],prepare_bscan(raw[:,10:80],vhi)))
            y=np.array([[2.,20.,65.]])
            native=y+off
            self.assertTrue(np.array_equal(native-off,y))
            disk=to_disk_rows(native,96,vhi)
            self.assertTrue(np.array_equal(to_disk_rows(disk,96,vhi),native))
            self.assertEqual(x.shape,(1,96,12))
        profile=np.r_[np.ones(5),np.full(40,50.),np.ones(51)]
        self.assertTrue(detect_orientation(profile))
        self.assertFalse(detect_orientation(profile[::-1]))

    def test_masked_loss_ignores_unknown_targets(self):
        torch.manual_seed(7)
        logits=torch.randn(1,8,96,16,requires_grad=True)
        region_logits=torch.randn(1,7,96,16,requires_grad=True)
        rows=torch.full((1,8,16),40.)
        valid=torch.zeros_like(rows,dtype=torch.bool); valid[:,1,:8]=True
        regions=torch.full((1,96,16),-100,dtype=torch.long)
        a,_=losses(logits,region_logits,rows,valid,regions)
        rows[~valid]=float("nan")
        b,_=losses(logits,region_logits,rows,valid,regions)
        self.assertEqual(float(a.detach()),float(b.detach()))
        b.backward()
        self.assertTrue(torch.isfinite(logits.grad).all())
        self.assertEqual(float(logits.grad[:,0].abs().sum()),0.)
        self.assertGreater(float(logits.grad[:,1,:,:8].abs().sum()),0.)

    def test_thickness_bias_and_two_endpoint_coverage(self):
        rows=record(10)["surfaces"]; kept=np.ones_like(rows,bool)
        kept[2,3]=False
        t=thickness(rows,kept,1.12)
        self.assertTrue(np.isnan(t["GCL"][3]))
        self.assertTrue(np.isnan(t["IPL"][3]))
        self.assertAlmostEqual(float(t["TOTAL"][3]),78.4,places=4)
        d=np.full(10,-12.); s=stats(d,np.ones(10,bool),np.ones(10,bool))
        self.assertEqual(s["mean_signed_um"],-12)
        self.assertEqual(s["mean_abs_um"],12)

    def test_inference_scope_shadow_and_original_rows(self):
        class Known(torch.nn.Module):
            def forward(self,x):
                a=torch.full((1,8,96,12),-100.)
                for k in range(8): a[:,k,10+10*k,:]=100.
                return a,torch.zeros((1,7,96,12))
        allowed=np.ones(12,bool); allowed[0]=False
        shadow=np.zeros(12,bool); shadow[1]=True
        p=prediction(Known(),np.zeros((1,96,12),np.float32),allowed,shadow)
        self.assertFalse(p["retained"][:,:2].any())
        self.assertTrue(p["retained"][:,2:].all())
        self.assertTrue(np.array_equal(p["rows"][:,4],np.arange(8)*10+10))
        for band in thickness(p["rows"],p["retained"],1.12).values():
            self.assertTrue(np.isnan(band[:2]).all())

    def test_thickness_common_shift_cancels(self):
        r=dict(key="synthetic",animal="TS1",scan_id="synthetic",verdict="corrected",
            scope_status="control",qc_group="unknown",biological_group="WT",px_um=1.)
        y=record(12)["surfaces"]
        t=dict(rows_label=y,valid=np.ones((8,12),bool))
        pred={"synthetic":dict(rows=y+100,retained=t["valid"])}
        report=evaluate([r],{"synthetic":t},pred,{"synthetic":{"aline_um":2.}})
        for s in report["summary"]:
            self.assertEqual(s["mean_signed_um"],0 if s["kind"]=="thickness" else 100)

    def test_checkpoint_optimizer_reload_and_odd_shape(self):
        torch.manual_seed(42)
        model=BoundaryUNet(); opt=torch.optim.AdamW(model.parameters())
        x=torch.randn(1,1,97,35)
        a,_=model(x); a.square().mean().backward(); opt.step()
        self.assertEqual(a.shape,(1,8,97,35))
        with tempfile.TemporaryDirectory(dir=output_dir(DEFAULT/"test_tmp")) as tmp:
            path=Path(tmp)/"checkpoint.pt"
            save_checkpoint(path,model,opt,{},dict(base=8),1,0,None,random.Random(1))
            restored,ck=load_checkpoint(path)
            self.assertTrue(torch.equal(model(x)[0],restored(x)[0]))
            self.assertTrue(ck["optimizer"]["state"])
            self.assertEqual(decode(restored(x)[0])[0].shape,(1,8,35))

    def test_split_isolation_and_final_test_lock(self):
        m=json.loads((DEFAULT/"manifest.json").read_text())
        p=json.loads((DEFAULT/"partitions.json").read_text())
        validate_partition(m,p)
        bad=copy.deepcopy(p); bad["animals"]["validation"].append("TS165")
        with self.assertRaises(ValueError): validate_partition(m,bad)
        with self.assertRaises(ValueError): test_guard(m,"test",None)

    def test_historical_cohort_separate(self):
        h=json.loads((DEFAULT/"historical_cohort.json").read_text())
        m=json.loads((DEFAULT/"manifest.json").read_text())
        self.assertEqual(h["n_bscans"],53)
        self.assertEqual(len(m["records"]),160)
        self.assertIn("cannot be certified",h["note"])


if __name__=="__main__":
    torch.set_num_threads(2)
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(StageATests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    write_json(DEFAULT/"test_results.json",dict(tests=result.testsRun,
        failures=[str(t) for t,_ in result.failures],errors=[str(t) for t,_ in result.errors],
        success=result.wasSuccessful(),final_test_predictions_used=False))
    raise SystemExit(0 if result.wasSuccessful() else 1)
