"""Score saved classical/hybrid experiments on the frozen validation cohort."""
import argparse
from pathlib import Path
import numpy as np
from stage_a.common import DEFAULT, output_dir, write_csv, write_json, fingerprint
from stage_a_review import FrozenSplit
from stage_a_inner_retina import evaluate, sensitivity


def run(args):
    data = FrozenSplit(args.data, "validation")
    targets, predictions, sources = {}, {k: {} for k in ("baseline", "candidate")}, []
    loaded = {}
    for r in data.records:
        with np.load(r["targets"], allow_pickle=False) as d:
            t = {k: d[k].copy() for k in d.files}
        targets[r["key"]] = t
        sid = r["scan_id"]
        path = args.experiment / f"{sid}_predictions.npz"
        if not path.exists():
            continue
        if sid not in loaded:
            sources.append(fingerprint(path))
            with np.load(path, allow_pickle=False) as d:
                loaded[sid] = {k: d[k].copy() for k in d.files}
        d = loaded[sid]
        indices = np.flatnonzero(d["bscans"] == r["bscan"])
        if not len(indices):
            continue
        i = indices[0]
        shadow = d["shadow"][i] if "shadow" in d else t["shadow"]
        for key in predictions:
            rows = d[key][i]
            keep = np.broadcast_to(t["scope"] & ~shadow, rows.shape).copy() & np.isfinite(rows)
            crossing = rows[:-1] > rows[1:]
            keep[:-1][crossing] = False; keep[1:][crossing] = False
            predictions[key][r["key"]] = dict(rows=rows, retained=keep)
    out = output_dir(args.out)
    metrics = []
    for name, pred in predictions.items():
        for scenario, selected in sensitivity(data.records):
            report = evaluate(selected, targets, pred, data.manifest["sources"])
            metrics.extend(dict(predictor=name, sensitivity=scenario, **r) for r in report["summary"])
            write_json(out / f"{name}_{scenario}.json", report)
    write_csv(out / "metrics.csv", metrics)
    write_json(out / "input_provenance.json", dict(experiment=str(args.experiment), predictions=sources,
        cohort="Frozen validation, with all eligible denominators retained", final_test_used=False))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, default=DEFAULT)
    p.add_argument("--experiment", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    run(p.parse_args())
