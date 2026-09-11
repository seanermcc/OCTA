"""Release-wide invariants; scientific failures are reported, not hidden."""
import hashlib
import json
import numpy as np
from .common import *
from .decisions import *
from eight_surface import provenance as P
from eight_surface.labels import load_label

def run():
    m=json.loads((OUT/"data/manifest.json").read_text());c=json.loads((OUT/"data/census.json").read_text())
    evidence=[]
    correction=json.loads((OUT/"data/state_semantics_correction.json").read_text())
    proof={r["key"]:r["image_rows_valid_before_and_after"] for r in correction["position_arrays_bit_identical"]}
    for r in m["records"]:
        verify(r["cache"]);d=load_npz(r["cache"]["path"]);l=load_label(r["label"]["path"])
        assert hashlib.sha256(b"".join(d[k].tobytes() for k in ("x","rows","valid"))).hexdigest()==proof[r["key"]]
        assert np.all(d["trace_target"][P.record_visibility(l)==0]==-1)
        assert np.all(d["reliability_target"][P.record_reliability(l)==0]==-1)
        if l["verdict"]!="corrected":assert not d["valid"].any()
        assert not d["valid"][l["local_displaced"]].any()
        assert not d["valid"][:,l["region_excluded"]].any()
        assert not d["valid"][:,d["shadow"]].any()
        assert (d["rows"][d["valid"]]>=0).all() and (d["rows"][d["valid"]]<=d["x"].shape[1]-1).all()
        if not l["local_provenance_available"]:assert not d["valid"].any()
    examples=json.loads((OUT/"review_packs/queue.json").read_text())["examples"]
    assert len(examples)==30
    for i,a in enumerate(examples):
        for b in examples[i+1:]:
            assert a["scan_id"]!=b["scan_id"] or abs(a["bscan"]-b["bscan"])>=16
    for path in sorted((OUT/"volumes").glob("*/measurements.npz")):
        d=load_npz(path);sid=path.parent.name
        assert d["reported_positions"].shape==(512,8,512)
        assert d["probabilities"].shape==(512,8,2,512)
        assert not np.isfinite(d["reported_positions"][d["state"]!=1]).any()
        assert not np.isfinite(d["uncertain_estimates"][d["state"]==2]).any()
        assert not np.isfinite(d["uncertain_estimates"][np.isin(d["reason"],[7,8,9,10])]).any()
        np.testing.assert_array_equal(thickness(d["reported_positions"],d["shadow"]),d["primary_thickness_um"])
        a=load_npz(OUT/"review_packs/automatic"/f"{sid}.npz")
        np.testing.assert_allclose(a["surfaces"],d["reported_positions"]-int(d["label_offset"]),equal_nan=True)
        np.testing.assert_array_equal(np.isfinite(a["uncertain_estimates"]),np.isfinite(d["uncertain_estimates"]))
        # Explicit denials override automatic reports even when no eligible
        # positional target exists for that record.
        for r in [r for r in m["records"] if r["scan_id"]==sid]:
            human=load_npz(r["cache"]["path"]);b=r["bscan"]
            assert not np.isfinite(d["reported_positions"][b][human["trace_target"]==0]).any()
            assert not np.isfinite(d["uncertain_estimates"][b][human["trace_target"]==0]).any()
            assert not np.isfinite(d["reported_positions"][b][human["reliability_target"]==0]).any()
        evidence.append(dict(scan=sid,all_boundary_bscan_alines=int(np.prod(d["state"].shape)),nan_contract=True,
            measurement_estimate_separation=True,human_denials_enforced=True,gui_pack_same=True))
    assert len(evidence)==4
    write_json(OUT/"verification/contract.json",dict(dataset_records=len(m["records"]),
        strict_unknown_state_mask=True,position_arrays_unchanged_during_state_correction=True,
        human_labels_written_by_verification=False,queue_spacing=True,volumes=evidence,
        scientific_status="failed reliability validation; experimental review release"))
    progress("release measurement contract verified",volumes=4,queue_examples=30)

if __name__=="__main__":run()
