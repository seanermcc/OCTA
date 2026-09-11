"""Single held-animal old/new U-Net comparison for the review-36 update."""
import argparse, json
from pathlib import Path
import numpy as np
from stage_a.data import Dataset
from stage_a.common import output_dir, write_csv, write_json, fingerprint
from stage_a_inner_train import load
from stage_a_inner_calibrate import predicted
from stage_a_inner_retina import evaluate

def run(a):
    import torch
    torch.set_num_threads(2)
    out = output_dir(a.out)
    datasets = [Dataset(a.data, s, eligible_only=False) for s in ("train", "validation")]
    records = [r for d in datasets for r in d.records if r["animal"] == a.held]
    targets = {}
    for r in records:
        with np.load(r["targets"], allow_pickle=False) as d: targets[r["key"]] = {k:d[k].copy() for k in d.files}
    bounds = json.loads(a.constraints.read_text())
    rows = []
    for name, checkpoint in (("old", a.old), ("updated", a.updated)):
        model, ck = load(checkpoint, a.device); model.eval()
        predictions = {}
        for r in records:
            t = targets[r["key"]]
            if not t["valid"][:4].any(): continue
            entry = next(d.cache["entries"][r["key"]] for d in datasets if r["key"] in d.cache["entries"])
            with np.load(entry["file"]["path"], allow_pickle=False) as d: x=d["x"]
            q = predicted(model, x, t["scope"], t["shadow"], "dp_project", bounds, a.device)
            for field in ("rows", "raw_rows", "full_raw_rows"): q[field] -= entry["label_offset"]
            predictions[r["key"]]=q
        for subset_name, subset in (("original_frozen", [r for r in records if r.get("source_decision")=="frozen_original"]),
                                    ("new_review36", [r for r in records if r.get("source_decision")=="new_review"]),
                                    ("combined", records)):
            result=evaluate(subset, targets, predictions, datasets[0].manifest["sources"])
            rows += [dict(model=name, subset=subset_name, **x) for x in result["summary"]]
    write_csv(out/"validation_metrics.csv", rows)
    write_json(out/"protocol.json", dict(held_animal=a.held, calibration_animal="TS250", training_animals=["TS165","TS169","TS241","TS267","TS283","TS305","TS325"], decoder="dp_project", identical_masks=True, constraints=fingerprint(a.constraints), old=fingerprint(a.old), updated=fingerprint(a.updated), note="Development validation only; TS247 and TS250 excluded from updated-fold training."))

if __name__ == "__main__":
 p=argparse.ArgumentParser(); p.add_argument("--data",type=Path,required=True); p.add_argument("--old",type=Path,required=True); p.add_argument("--updated",type=Path,required=True); p.add_argument("--constraints",type=Path,required=True); p.add_argument("--out",type=Path,required=True); p.add_argument("--held",default="TS247"); p.add_argument("--device",default="cuda"); run(p.parse_args())
