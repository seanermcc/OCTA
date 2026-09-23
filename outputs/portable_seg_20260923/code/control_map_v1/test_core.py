import copy
import tempfile
import unittest
from pathlib import Path
import numpy as np
from . import DEFAULTS
from .geometry import (feret,dilate_um,lesion_buffer,vessel_buffer,fit_onh,branches,convergence,
                       apply,sample_native,register,xy_grid)
from .masks import local_screen,exclusions
from .io import write,require_verified,unique_scans,Stage,save
from .aggregate import balanced,repeat_pair,repeated_component
from .pipeline import localize


class GeometryTests(unittest.TestCase):
    def setUp(self):self.cfg=copy.deepcopy(DEFAULTS)

    def test_feret_irregular_longest_span(self):
        m=np.zeros((30,40),bool);m[10,10:20]=True
        self.assertAlmostEqual(feret(m,(1,1)),np.hypot(10,1))

    def test_diameter_10_clearance_10(self):
        # A rectangular physical lesion whose corner-to-corner span is exactly 10.
        m=np.zeros((80,80),bool);m[30:36,30:38]=True
        b,rows=lesion_buffer(m,(1,1))
        self.assertAlmostEqual(rows[0]["diameter_um"],10.)
        self.assertEqual(rows[0]["clearance_um"],10.)
        self.assertTrue(b[33,47]);self.assertFalse(b[33,49])

    def test_anisotropic_physical_buffer(self):
        m=np.zeros((41,41),bool);m[20,20]=True
        b=dilate_um(m,10,(2,1))
        self.assertTrue(b[25,20]);self.assertTrue(b[20,30]);self.assertFalse(b[27,20])

    def test_empty_masks_stay_empty(self):
        m=np.zeros((30,30),bool)
        self.assertFalse(lesion_buffer(m,(1,1))[0].any());self.assertFalse(vessel_buffer(m,(1,1)).any())

    def test_visible_onh_and_short_arc(self):
        y,x=np.indices((101,101));disc=(x-50)**2+(y-50)**2<=20**2
        loc=fit_onh(disc,np.zeros_like(disc),(2,2),self.cfg)
        self.assertTrue(loc["resolved"]);np.testing.assert_allclose(loc["center_um"],[100,100],atol=1)
        arc=disc&~__import__('scipy').ndimage.binary_erosion(disc)&(x>65)&(y>45)&(y<55)
        self.assertFalse(fit_onh(np.zeros_like(disc),arc,(2,2),self.cfg)["resolved"])

    def test_synthetic_off_image_convergence(self):
        center=np.array([-100.,150.]);rs=[]
        for p in ([10,10],[20,300],[150,150],[200,10],[200,350]):
            v=np.array(p)-center;v/=np.linalg.norm(v)
            rs.append(dict(point=p,direction=v.tolist(),accepted=True))
        result=convergence(rs,self.cfg)
        self.assertTrue(result["resolved"]);np.testing.assert_allclose(result["center_um"],center,atol=1e-8)

    def test_parallel_branches_unresolved(self):
        rs=[dict(point=[i*10,30],direction=[0,1],accepted=True) for i in range(5)]
        self.assertFalse(convergence(rs,self.cfg)["resolved"])

    def test_curved_branches_rejected(self):
        y,x=np.indices((200,200));r=np.hypot(x-100,y-100)
        mask=(r>60)&(r<64)&(x>100)
        rs,_=branches(mask,(2,2),self.cfg)
        self.assertTrue(rs);self.assertTrue(all(not r["accepted"] for r in rs))

    def test_hidden_onh_crop_from_synthetic_vessels(self):
        from skimage.draw import line
        from scipy.ndimage import binary_dilation
        vessel=np.zeros((201,201),bool)
        for endpoint in ((0,200),(60,200),(140,200),(200,200)):
            rr,cc=line(100,40,*endpoint);vessel[rr,cc]=True
        vessel=binary_dilation(vessel,iterations=2)
        cropped=vessel[:,80:]
        records,_=branches(cropped,(2,2),self.cfg);result=convergence(records,self.cfg)
        self.assertTrue(result["resolved"],result)
        np.testing.assert_allclose(result["center_um"],[-80,200],atol=4)

    def test_real_feature_extraction_translation(self):
        from .geometry import features
        from scipy.ndimage import gaussian_filter,binary_dilation
        from skimage.draw import line
        rng=np.random.default_rng(5);shape=(256,256);vessel=np.zeros(shape,bool)
        for _ in range(18):
            p=rng.integers(30,226,size=(2,2));rr,cc=line(*p[0],*p[1]);vessel[rr,cc]=True
        vessel=binary_dilation(vessel,iterations=2)
        image=gaussian_filter(rng.normal(size=shape),.7)+vessel*1.5
        blank=np.zeros(shape,bool);spacing=np.array([2.,2.])
        a=dict(enface=image,vessel=vessel,registration_blocked=blank,spacing=spacing)
        b=dict(enface=np.roll(image,7,axis=1),vessel=np.roll(vessel,7,axis=1),registration_blocked=blank,spacing=spacing)
        fa=features(a["enface"],a["vessel"],blank,spacing);fb=features(b["enface"],b["vessel"],blank,spacing)
        result=register(a,b,fa,fb,self.cfg)
        self.assertTrue(result["verified"],result)
        np.testing.assert_allclose(np.array(result["matrix"])[:2,2],[14,0],atol=2)

    def test_nearest_sampling_does_not_fill_nan(self):
        a=np.arange(25,dtype=float).reshape(5,5);a[2,2]=np.nan
        sampled,valid=sample_native(a,np.array([[2,2],[2,1],[9,9]]),(1,1))
        self.assertTrue(np.isnan(sampled[0]));self.assertEqual(sampled[1],7);self.assertFalse(valid[2])

    def test_known_rigid_registration_and_scale(self):
        from scipy.ndimage import gaussian_filter
        from skimage.transform import EuclideanTransform
        rng=np.random.default_rng(4);shape=(120,120);spacing=np.array([2.,2.])
        image=gaussian_filter(rng.normal(size=shape),1)
        vessel=rng.random(shape)>.8;blocked=np.zeros(shape,bool)
        # Same image translated in physical x by 10 um (five native pixels).
        bimage=np.roll(image,5,axis=1);bvessel=np.roll(vessel,5,axis=1)
        points=rng.uniform(35,170,(25,2));descriptor=rng.random((25,256))>.5
        f=dict(points=points,descriptors=descriptor,branches=points[:6])
        g=dict(points=points+[10,0],descriptors=descriptor,branches=points[:6]+[10,0])
        a=dict(enface=image,vessel=vessel,registration_blocked=blocked,spacing=spacing)
        b=dict(enface=bimage,vessel=bvessel,registration_blocked=blocked,spacing=spacing)
        result=register(a,b,f,g,self.cfg)
        self.assertTrue(result["verified"],result)
        np.testing.assert_allclose(np.array(result["matrix"])[:2,2],[10,0],atol=1e-8)
        self.assertAlmostEqual(np.linalg.det(np.array(result["matrix"])[:2,:2]),1.)
        # Known rotation checks the same physical rigid estimator's correspondence path.
        transform=EuclideanTransform(rotation=.15,translation=[3,-5])
        np.testing.assert_allclose(apply(points,transform.params),transform(points))

    def test_registration_without_branches_fails(self):
        shape=(32,32);p=np.arange(20).reshape(10,2)+8;desc=np.eye(10,dtype=bool)
        f=dict(points=p,descriptors=desc,branches=np.empty((0,2)))
        a=dict(enface=np.random.default_rng(1).normal(size=shape),vessel=np.ones(shape,bool),
               registration_blocked=np.zeros(shape,bool),spacing=[1,1])
        self.assertFalse(register(a,a,f,f,self.cfg)["verified"])


class MaskTests(unittest.TestCase):
    def setUp(self):
        self.cfg=copy.deepcopy(DEFAULTS);self.cfg["neighborhood_diameter_um"]=6

    def test_exact_local_median_mad(self):
        rng=np.random.default_rng(8);full=rng.normal(100,5,(21,21));full[8,9]=np.nan
        eligible=np.ones((21,21),bool);eligible[10,8]=False
        result=local_screen(full,eligible,(1,1),self.cfg)
        y,x=np.indices(full.shape);values=full[((x-10)**2+(y-10)**2<=9)&eligible]
        med=np.nanmedian(values);mad=np.nanmedian(abs(values-med))
        self.assertAlmostEqual(result["trend"][10,10],med)
        self.assertAlmostEqual(result["sd"][10,10],max(1.12,1.4826*mad))

    def test_exact_median_at_tile_seams(self):
        rng=np.random.default_rng(3);full=rng.normal(100,6,(37,35)).astype(np.float32)
        eligible=rng.random(full.shape)>.2
        result=local_screen(full,eligible,(1,1),self.cfg)
        y,x=np.indices(full.shape)
        for cy,cx in ((15,15),(16,16),(31,32),(0,0)):
            values=full[((x-cx)**2+(y-cy)**2<=9)&eligible]
            med=np.median(values);mad=np.median(abs(values-med))
            self.assertAlmostEqual(result["trend"][cy,cx],med,places=5)
            self.assertAlmostEqual(result["sd"][cy,cx],max(1.12,1.4826*mad),places=5)

    def test_neighborhood_missing_half_is_unresolved(self):
        a=np.full((11,11),100.);eligible=np.zeros((11,11),bool);eligible[5,5]=True
        result=local_screen(a,eligible,(1,1),self.cfg)
        self.assertFalse(result["resolved"][5,5]);self.assertFalse(result["keep"][5,5])

    def test_floor_and_outlier(self):
        a=np.full((11,11),100.);a[5,5]=105
        result=local_screen(a,np.ones_like(a,bool),(1,1),self.cfg)
        self.assertEqual(result["sd"][5,5],1.12);self.assertFalse(result["keep"][5,5])

    def test_overlap_reasons_and_shared_B(self):
        z=np.zeros((21,21),bool);full=np.full((8,21,21),100.)
        data=dict(enface=full[0],thickness=full,spacing=[1,1],human_excluded=z.copy(),shadow=z.copy(),
                  vessel=z.copy(),onh=z.copy(),onh_edge=z.copy(),cnv_human=z.copy(),cnv_candidate=z.copy())
        data["shadow"][5,5]=True;data["cnv_human"][5,5]=True;data["thickness"][0,15,15]=np.nan
        masks,_,sized=exclusions(data,dict(resolved=False),self.cfg)
        self.assertEqual(int(masks["exclusion_reasons"][5,5])&(2|4),2|4)
        self.assertTrue(masks["eligible_A"][15,15]);self.assertFalse(masks["eligible_B"][15,15]);self.assertFalse(sized)


class ContractTests(unittest.TestCase):
    def test_batch_gate_missing_and_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):require_verified(tmp)
            write(Path(tmp)/"FINAL_VERIFIED.json",dict(passed=False));write(Path(tmp)/"manifest.json",dict(scans=[]))
            with self.assertRaises(ValueError):require_verified(tmp)

    def test_duplicates_do_not_double_weight(self):
        r=dict(scan_id="TS241_test",source="input.mat",animal="TS241F",eye="OD",session_date="2025-01-01")
        rows,duplicates=unique_scans([r,r,dict(r,scan_id="TS241_alias")])
        self.assertEqual(len(rows),1);self.assertEqual(len(duplicates),2);self.assertEqual(rows[0]["animal"],"TS241")

    def test_conflicting_scan_identity_fails(self):
        r=dict(scan_id="TS241_test",source="input.mat",animal="TS241",eye="OD",session_date="2025-01-01")
        with self.assertRaises(ValueError):unique_scans([r,dict(r,source="different.mat")])

    def test_reprocessed_copy_not_an_extra_acquisition(self):
        r=dict(scan_id="TS241_test",source="input.mat",animal="TS241",eye="OD",session_date="2025-01-01")
        variant=dict(r,scan_id="TS241_test_source_other",source="reprocessed.mat",source_variant_of=r["scan_id"])
        rows,duplicates=unique_scans([r,variant])
        self.assertEqual(len(rows),1);self.assertEqual(duplicates[0]["canonical"],r["scan_id"])

    def test_resume_detects_changed_source_or_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"array.npz";save(p,a=np.array([1]))
            s=Stage(tmp,"x","a");s.finish([p]);self.assertTrue(s.valid())
            self.assertFalse(Stage(tmp,"x","b").valid());save(p,a=np.array([2]));self.assertFalse(s.valid())

    def test_balanced_dates_eyes_animals(self):
        rows=[]
        def add(animal,eye,date,values):
            for i,v in enumerate(values):rows.append(dict(kind="polar",cell_0=0,cell_1=0,layer="RNFL",version="A",
                animal=animal,eye=eye,date=date,scan_id=f"{animal}_{eye}_{date}_{i}",value_um=v,area_um2=1))
        add("TS1","OD","d1",[0]*10);add("TS1","OD","d2",[100]);add("TS1","OS","d1",[150]);add("TS2","OD","d1",[200])
        result=balanced(rows)
        # TS1 OD=50, OS=150 -> TS1=100. TS2=200 -> cohort=150.
        self.assertEqual(result["cohort"].value_um.iloc[0],150.)
        self.assertEqual(result["cohort"].animals.iloc[0],2)

    def test_registration_transfer_preserves_center_and_size(self):
        cfg=copy.deepcopy(DEFAULTS)
        visible=dict(resolved=True,center_um=[50,70],diameter_um=40,uncertainty_um=2)
        infos={"a":dict(visible_onh=visible,branches=[]),"b":dict(visible_onh=dict(resolved=False),branches=[])}
        m=dict(verified=True,scan_a="a",scan_b="b",matrix=[[1,0,10],[0,1,-5],[0,0,1]],residual_um=1.)
        loc=localize(["a","b"],infos,[m],cfg)
        self.assertTrue(loc["b"]["resolved"]);np.testing.assert_allclose(loc["b"]["center_um"],[60,65])
        self.assertEqual(loc["b"]["diameter_um"],40)

    def test_convergence_does_not_invent_disc_size(self):
        cfg=copy.deepcopy(DEFAULTS);rs=[]
        for p in ([100,0],[0,100],[100,100],[-100,100]):
            v=np.asarray(p,dtype=float);v/=np.linalg.norm(v);rs.append(dict(point=p,direction=v.tolist(),accepted=True))
        info={"a":dict(visible_onh=dict(resolved=False),branches=rs)}
        loc=localize(["a"],info,[],cfg)["a"]
        self.assertTrue(loc["resolved"]);self.assertIsNone(loc["diameter_um"])

    def test_repeat_date_and_exclusion_contract(self):
        shape=(5,5);z=np.zeros(shape,bool)
        a=dict(enface=np.zeros(shape),spacing=[1,1],thickness=np.ones((8,*shape))*100,
               eligible_A=~z,eligible_B=~z,cnv_human=z,cnv_candidate=z)
        b=copy.deepcopy(a);b["thickness"]+=10;b["eligible_A"][2,2]=False
        ia=dict(scan_id="a",animal="TS1",eye="OD",session_date="2025-01-01")
        ib=dict(ia,scan_id="b",session_date="2025-02-01")
        match=dict(matrix=np.eye(3),residual_um=1.,branch_residual_um=2.,overlap_fraction=1.)
        rows,maps=repeat_pair(a,b,ia,ib,match,DEFAULTS)
        self.assertEqual(rows[0]["interval"],"across_date");self.assertEqual(rows[0]["difference_b_minus_a_mean_um"],10)
        self.assertTrue(np.isnan(maps["difference_A_um"][:,2,2]).all())
        self.assertEqual(rows[0]["matched_native_pixels"],24)


if __name__=="__main__":unittest.main()
