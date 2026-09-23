"""Small synthetic export fixture exercises the full adapter and artifact chain."""
import copy
import json
import tempfile
import unittest
import os
import shutil
from pathlib import Path
import numpy as np
from . import DEFAULTS,LAYERS
from .io import save,write,sha,read,fingerprint,load_scan,analysis_inputs
from .pipeline import initialize,run


def make_fixture(root):
    batch=root/"batch";batch.mkdir();sid="TS1_OD_2025-01-01_fixture"
    volume=batch/"volumes"/sid;volume.mkdir(parents=True)
    source=root/"synthetic_processedVolumes.mat";source.write_bytes(b"synthetic fixture, not a raw acquisition")
    shape=(48,48);rng=np.random.default_rng(12);images=rng.normal(50,10,(48,260,48)).astype(np.float32)
    np.save(volume/"images.npy",images)
    y,x=np.indices(shape);disc=(x-24)**2+(y-24)**2<=5**2;blank=np.zeros(shape,bool)
    save(volume/"geometry.npz",native_shape=np.array([48,48,260]),vessel=blank,cnv=blank,
        onh=disc,onh_edge=blank,shadow=blank)
    save(volume/"qc_masks.npz",excluded=blank)
    save(volume/"measurements.npz",placeholder=np.array([1]))
    write(volume/"neural_complete.json",dict(scan_id=sid));write(volume/"complete.json",dict(scan_id=sid))
    image_fp=fingerprint(volume/"images.npy");image_fp["mtime_ns"]=(volume/"images.npy").stat().st_mtime_ns
    write(volume/"prepared.json",dict(images_fingerprint=image_fp,enface_label=None,footprints=dict(status="synthetic empty vessel mask")))
    write(volume/"qc_complete.json",dict(verified=True))
    endpoints=np.broadcast_to(np.array([0,50,60,110,140,160,210,240])[None,:,None],(48,8,48)).copy().astype(np.float32)
    thickness=np.stack([(endpoints[:,b]-endpoints[:,a])*1.12 for a,b in [(0,7),(0,1),(1,2),(2,3),(3,4),(4,5),(5,6),(6,7)]])
    # Local full-retina/outer disruption gives a candidate and a real linked panel.
    thickness[0,8:11,8:11]+=60
    meta=dict(scan_id=sid,layers=LAYERS,units="um",axis_order="layer,B-scan,A-line",canonical_vitreous_at_depth_zero=True,
        source_fingerprints={p:sha(volume/p) for p in ("geometry.npz","measurements.npz","complete.json","neural_complete.json")},correction_fingerprints={})
    exp=batch/"thick/exports"/(sid+"_batch.npz")
    save(exp,metadata_json=np.array(json.dumps(meta)),exclude_unreliable_um=thickness,shadow=blank,
         reported_endpoints_crop_px=endpoints,reported_endpoint_sources=np.ones_like(endpoints,np.uint8),endpoint_reason=np.ones_like(endpoints,np.uint8))
    write(exp.with_suffix(".json"),meta)
    row=dict(scan_id=sid,animal="TS1",eye="OD",session_date="2025-01-01",source=str(source),days_post_laser="0")
    write(batch/"manifest.json",dict(scans=[row],unavailable=[],synthetic_test_fixture=True))
    write(batch/"FINAL_VERIFIED.json",dict(passed=True,scans=1,all_native_grid_checks=True,all_input_artifact_hashes_verified=True,synthetic_test_fixture=True))
    return batch,row


class IntegrationTests(unittest.TestCase):
    def test_audit_skip_is_explicit_and_still_requires_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);batch,row=make_fixture(root)
            (batch/"FINAL_VERIFIED.json").unlink()
            with self.assertRaises(RuntimeError):analysis_inputs(batch)
            manifest,audit=analysis_inputs(batch,skip_batch_audit=True)
            self.assertEqual(len(manifest["scans"]),1)
            self.assertEqual(audit["status"],"skipped_by_user")
            self.assertIsNone(audit["verification"])
            self.assertFalse((batch/"FINAL_VERIFIED.json").exists())
            (batch/"thick/exports"/(row["scan_id"]+"_batch.npz")).unlink()
            with self.assertRaises(ValueError):analysis_inputs(batch,skip_batch_audit=True)

    def test_export_adapter_and_stale_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);batch,row=make_fixture(root)
            cfg=copy.deepcopy(DEFAULTS);data,info=load_scan(batch,row,cfg)
            self.assertEqual(data["thickness"].shape,(8,48,48));self.assertEqual(info["annotation_reviewed"],[False]*3)
            export=batch/"thick/exports"/(row["scan_id"]+"_batch.npz")
            write(Path(str(export)+".stale.json"),dict(stale=True))
            with self.assertRaises(ValueError):load_scan(batch,row,cfg)

    def test_end_to_end_figures_captions_and_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);batch,row=make_fixture(root);out=root/"atlas"
            initialize(out,batch);cfg=read(out/"config.json")
            cfg.update(field_um=240.,neighborhood_diameter_um=60.,candidate_min_area_um2=20.,grid_um=10.)
            write(out/"config.json",cfg)
            result=run(out,batch)
            self.assertEqual(result["status"],"analysis_complete_preliminary")
            self.assertTrue(read(out/"qc/figure_audit.json")["passed"])
            self.assertTrue((out/"tables/cohort_cells.csv").stat().st_size>100)
            if os.environ.get("CONTROL_MAP_QA_DIR"):
                qa=Path(os.environ["CONTROL_MAP_QA_DIR"]);qa.mkdir(parents=True,exist_ok=True)
                for family in (2,4,5,8):
                    rec=next(r for r in result["figures"] if r["family"]==family)
                    shutil.copy2(out/rec["file"],qa/Path(rec["file"]).name)
                shutil.copy2(out/"fig/FIGURE_CAPTIONS.md",qa/"FIGURE_CAPTIONS.md")
            analysis=out/"maps"/(row["scan_id"]+"_analysis.npz")
            before=analysis.stat().st_mtime_ns
            # The second call must reuse native preparation and eye summaries.
            # Avoid rerendering dozens of identical figures; their registry was
            # already exercised fully by the first run.
            from unittest.mock import patch
            (batch/"FINAL_VERIFIED.json").unlink()
            with patch("control_map_v1.figures.generate",return_value=result["figures"]):
                unaudited=run(out,batch,skip_batch_audit=True)
            self.assertEqual(before,analysis.stat().st_mtime_ns)
            self.assertEqual(unaudited["batch_audit"]["status"],"skipped_by_user")
            self.assertIsNone(unaudited["batch_verification"])
            self.assertFalse((batch/"FINAL_VERIFIED.json").exists())


if __name__=="__main__":unittest.main()
