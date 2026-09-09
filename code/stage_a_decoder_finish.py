"""Freeze the complete manual-reference comparison from saved decoder outputs.

All 14 manually supported validation decisions are required. Decisions with no
manual target are not an accuracy cohort. Full-volume crossing verification is
reported separately by the review-queue inference run.
"""
import argparse
import json
from pathlib import Path
import time
import numpy as np
from stage_a.common import DEFAULT, output_dir, write_json, write_csv, fingerprint
from stage_a_review import FrozenSplit
from stage_a_inner_retina import evaluate, sensitivity


def run(args):
    data = FrozenSplit(args.data, "validation")
    targets, records = {}, []
    for r in data.records:
        with np.load(r["targets"], allow_pickle=False) as d:
            t = {k: d[k].copy() for k in d.files}
        if t["valid"][:4].any():
            targets[r["key"]] = t; records.append(r)
    out = output_dir(args.out)
    methods = ("soft", "dp_project", "graph_cut")
    movement, metrics, provenance = [], [], {}
    bounds = json.loads(args.constraints.read_text())
    for method in methods:
        predictions = {}; provenance[method] = []
        for r in records:
            path = args.predictions / method / f"{r['key']}.npz"
            if not path.exists():
                raise ValueError(f"Missing manually supported decision: {path}")
            provenance[method].append(fingerprint(path))
            with np.load(path, allow_pickle=False) as d:
                p = {k: d[k].copy() for k in d.files}
            predictions[r["key"]] = p
            rows = p["rows"][:4]
            crossing = np.any(rows[:-1] > rows[1:], axis=0)
            if method != "soft":
                if crossing.any() or np.any(np.diff(rows, axis=0) < np.array(bounds["minimum"])[:, None] - 1e-4):
                    raise AssertionError("Saved decoder output violates minimum ordering")
                if np.any(np.abs(np.diff(rows, axis=1)) > 2.0001):
                    raise AssertionError("Saved decoder output violates lateral smoothness")
                if method == "graph_cut" and np.any(np.diff(rows, axis=0) > np.array(bounds["maximum"])[:, None]):
                    raise AssertionError("Saved graph output violates maximum gaps")
            displacement = np.abs(p["decoder_displacement_px"])
            changed = displacement > .5
            movement.append(dict(method=method, key=r["key"], animal=r["animal"],
                n_alines=rows.shape[1], crossing_alines=int(crossing.sum()),
                n_boundary_columns=rows.size, changed_boundary_columns=int(changed.sum()),
                moved_median_px=float(np.median(displacement[changed])) if changed.any() else 0.,
                moved_p95_px=float(np.quantile(displacement[changed], .95)) if changed.any() else 0.,
                mean_entropy_changed=float(p["entropy"][changed].mean()) if changed.any() else None,
                mean_entropy_unchanged=float(p["entropy"][~changed].mean()) if (~changed).any() else None))
        for scenario, selected in sensitivity(records):
            report = evaluate(selected, targets, predictions, data.manifest["sources"])
            metrics.extend(dict(decoder=method, sensitivity=scenario, **r) for r in report["summary"])
            write_json(out / f"{method}_{scenario}.json", report)
    write_csv(out / "metrics.csv", metrics)
    write_csv(out / "movement.csv", movement)
    write_json(out / "evaluation_meta.json", dict(checkpoint=fingerprint(args.checkpoint),
        constraints=fingerprint(args.constraints), predictions=provenance,
        cohort="Every validation B-scan with at least one eligible manually supported inner boundary",
        n_manual_validation_bscans=len(records), n_animals=len({r["animal"] for r in records}),
        n_validation_decisions_without_manual_targets=len(data.records)-len(records),
        all_manual_validation_decisions_complete=True, final_test_used=False,
        graph_algorithm="Original unpruned joint PyMaxflow closed-set minimum cut",
        full_volume_crossing_evidence="Separate complete-volume DP inference in review_queue/",
        choice="dp_project for experimental review triage; original soft estimator retained as the scientific baseline",
        strict_no_regression_passed=False,
        finding="Both constrained estimators reduce pooled errors and large tails, but small RNFL_GCL median regressions remain in per-animal/sensitivity rows. The graph's marginal error gains over DP do not establish a practical advantage."))
    print(out)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, default=DEFAULT)
    p.add_argument("--predictions", type=Path, required=True)
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--constraints", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    run(p.parse_args())
