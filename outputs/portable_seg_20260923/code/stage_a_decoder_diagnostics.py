"""Measured decoder displacement, entropy association, and manual constraint fit."""
import argparse
import json
from pathlib import Path
from collections import defaultdict
import numpy as np
from stage_a.common import DEFAULT, output_dir, write_json, write_csv
from stage_a_review import FrozenSplit
from stage_a_inner_retina import SURFACES


def run(args):
    data = FrozenSplit(args.data, "validation")
    bounds = json.loads(args.constraints.read_text())
    methods = dict(item.split("=", 1) for item in args.evals)
    accum = defaultdict(list)
    manual = defaultdict(lambda: [0, 0])
    coverage = defaultdict(int)
    cpu_difference, retention_difference = [], 0
    for r in data.records:
        with np.load(r["targets"], allow_pickle=False) as d:
            t = {k: d[k].copy() for k in d.files}
        valid, truth = t["valid"][:4], t["rows_label"][:4]
        for k, name in enumerate(SURFACES):
            paired = valid[k, :-1] & valid[k, 1:]
            manual[name, "step_gt_2px"][0] += int(paired.sum())
            manual[name, "step_gt_2px"][1] += int((paired & (np.abs(np.diff(truth[k])) > 2)).sum())
        for k, name in enumerate(("RNFL", "GCL", "IPL")):
            paired = valid[k] & valid[k+1]
            gap = truth[k+1] - truth[k]
            outside = (gap < bounds["minimum"][k]) | (gap > bounds["maximum"][k])
            manual[name, "outside_training_gap_interval"][0] += int(paired.sum())
            manual[name, "outside_training_gap_interval"][1] += int((paired & outside).sum())
        with np.load(args.baseline / f"{r['key']}.npz", allow_pickle=False) as d:
            original = {k: d[k].copy() for k in d.files}
        raw, entropy = original["rows"][:4], original["entropy"][:4]
        for method, directory in methods.items():
            path = Path(directory) / f"{r['key']}.npz"
            if not path.exists():
                if valid.any():
                    raise ValueError("Missing predictions for manually supported validation decision")
                continue
            coverage[method] += 1
            with np.load(path, allow_pickle=False) as d:
                rows, retained = d["rows"][:4], d["retained"][:4]
            if method == "soft":
                cpu_difference.extend(np.abs(rows-raw).ravel().tolist())
                retention_difference += int((retained != original["retained"][:4]).sum())
            displacement = np.abs(rows-raw)
            masks = {"all_alines": np.ones(raw.shape, bool),
                "in_scope_unshadowed": np.broadcast_to(t["scope"] & ~t["shadow"], raw.shape),
                "manual_eligible": valid}
            for group, mask in masks.items():
                for k, name in enumerate(SURFACES):
                    good = mask[k] & np.isfinite(displacement[k]) & np.isfinite(entropy[k])
                    accum[method, group, name].append((displacement[k][good], entropy[k][good]))
    metrics = []
    for (method, group, name), arrays in accum.items():
        distance = np.concatenate([a[0] for a in arrays])
        entropy = np.concatenate([a[1] for a in arrays])
        if not len(distance):
            continue
        high = entropy >= np.quantile(entropy, .75)
        for threshold in (.5, 2, 5):
            changed = distance > threshold
            metrics.append(dict(method=method, cohort=group, surface=name, movement_threshold_px=threshold,
                n_columns=len(distance), n_changed=int(changed.sum()), fraction_changed=float(changed.mean()),
                changed_median_px=float(np.median(distance[changed])) if changed.any() else None,
                changed_p95_px=float(np.quantile(distance[changed], .95)) if changed.any() else None,
                mean_entropy_changed=float(entropy[changed].mean()) if changed.any() else None,
                mean_entropy_unchanged=float(entropy[~changed].mean()) if (~changed).any() else None,
                fraction_moved_in_highest_entropy_quartile=float(changed[high].mean()) if high.any() else None,
                fraction_moved_below_highest_entropy_quartile=float(changed[~high].mean()) if (~high).any() else None))
    consistency = [dict(name=name, criterion=criterion, n_manual_pairs=n, n_outside=count,
        fraction_outside=count/n if n else None) for (name, criterion), (n, count) in manual.items()]
    out = output_dir(args.out)
    write_csv(out / "movement_entropy.csv", metrics)
    write_csv(out / "manual_constraint_consistency.csv", consistency)
    write_json(out / "diagnostics.json", dict(decisions_by_method=dict(coverage),
        soft_vs_frozen_max_abs_px=max(cpu_difference) if cpu_difference else None,
        soft_vs_frozen_retention_bit_differences=retention_difference,
        constraints_tuned_on_validation=False, final_test_used=False,
        entropy_interpretation="Relative entropy association only; quartiles are descriptive within each evaluation group, not calibrated uncertainty thresholds."))
    print(out)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, default=DEFAULT)
    p.add_argument("--baseline", type=Path, required=True)
    p.add_argument("--constraints", type=Path, required=True)
    p.add_argument("--evals", nargs="+", required=True)
    p.add_argument("--out", type=Path, required=True)
    run(p.parse_args())
