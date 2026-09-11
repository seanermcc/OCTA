"""One-time prerelease correction of derived targets, never annotation files.

Preserve the rejected development state-head attempt. Prove position/image
arrays unchanged so completed position training and evidence caches are reused.
"""
import hashlib
import shutil
import json
from .common import *
from .audit import targets
from eight_surface.labels import load_label

def run():
    marker=OUT/"data/state_semantics_correction.json"
    if marker.exists():return
    rejected=directory(OUT/"development_rejected_state_assumption")
    m=json.loads((OUT/"data/manifest.json").read_text())
    p=json.loads((OUT/"models/protocol.json").read_text())
    write_json(rejected/"manifest.json",m);write_json(rejected/"protocol.json",p)
    position_proof=[];audit=[]
    for r in m["records"]:
        d=load_npz(r["cache"]["path"]);lab=load_label(r["label"]["path"]);src=m["sources"][r["scan_id"]]
        proof=lambda:hashlib.sha256(b"".join(d[k].tobytes() for k in ("x","rows","valid"))).hexdigest()
        before=proof()
        save_npz(rejected/"derived_state_targets"/f"{r['key']}.npz",trace_target=d["trace_target"],reliability_target=d["reliability_target"])
        t=targets(lab,d["shadow"],src["label_band"][1]-src["label_band"][0],int(d["label_offset"]))
        d["trace_target"]=t["trace_target"];d["reliability_target"]=t["reliability_target"]
        assert proof()==before
        save_npz(r["cache"]["path"],**d);r["cache"]=fingerprint(r["cache"]["path"])
        position_proof.append(dict(key=r["key"],image_rows_valid_before_and_after=before))
        for k,name in enumerate(m["surface_names"]):
            audit.append(dict(key=r["key"],animal=r["animal"],boundary=name,verdict=lab["verdict"],format=lab["label_format_version"],path=r["label"]["path"],
                not_traceable=int((t["trace_target"][k]==0).sum()),traceable=int((t["trace_target"][k]==1).sum()),
                unreliable=int((t["reliability_target"][k]==0).sum()),reliable=int((t["reliability_target"][k]==1).sum()),
                unknown_trace=int((t["trace_target"][k]<0).sum()),unknown_reliability=int((t["reliability_target"][k]<0).sum()),positions=int(t["valid"][k].sum())))
    m["state_policy"]="explicit tri-state and negative whole-boundary judgments only; unknown remains masked even when a manual position exists"
    m.pop("dataset_id");m["dataset_id"]=digest(m)
    write_json(OUT/"data/manifest.json",m);write_csv(OUT/"data/label_audit.csv",audit)
    census=json.loads((OUT/"data/census.json").read_text())
    census["counts"]={key:sum(a[key] for a in audit) for key in ("not_traceable","traceable","unreliable","reliable","positions","unknown_trace","unknown_reliability")}
    write_json(OUT/"data/census.json",census)
    for path in list((OUT/"models").glob("*/states*.pt"))+list((OUT/"models").glob("*/complete.json")):
        dst=rejected/path.relative_to(OUT);directory(dst.parent);shutil.move(path,dst)
    for path in (OUT/"predictions",OUT/"evaluation",OUT/"calibration"):
        if path.exists():shutil.move(path,rejected/path.name)
    for folder in (OUT/"volumes").iterdir():
        if not folder.is_dir():continue
        for name in ("neural","neural_complete.json"):
            path=folder/name
            if path.exists():
                dst=rejected/path.relative_to(OUT);directory(dst.parent);shutil.move(path,dst)
    (OUT/"models/protocol.json").unlink()
    write_json(marker,dict(reason="Do not turn unknown reliability into positive supervision from a stroke",parent_position_protocol_id=digest(p),
        position_arrays_bit_identical=position_proof,rejected_development_artifacts=str(rejected),
        human_label_files_modified=False,position_models_reused=True,state_models_retrain_from_scratch=True))
    progress("state semantics corrected before release",counts=census["counts"])

if __name__=="__main__":run()
