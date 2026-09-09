"""Four-surface evaluation without changing the resumable stage_a package.

Read saved predictions against the frozen manual targets. The original masks,
coordinates, checkpoint and predictions remain unchanged. Missing predictions
remain failures; INNER_RETINA requires evidence at both ILM and IPL_INL.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path

import numpy as np

from stage_a.common import DEFAULT, fingerprint, output_dir, write_csv, write_json
from stage_a.metrics import evaluate as evaluate_eight, stats

SURFACES = ("ILM", "RNFL_GCL", "GCL_IPL", "IPL_INL")
BANDS = ("RNFL", "GCL", "IPL", "INNER_RETINA")
SENSITIVITY_KEY = "TS325_OD_2026-05-26_6mo_s01_112940_b0510"


def is_inner(row):
    return row["name"] in (SURFACES if row["kind"] == "boundary" else BANDS)


def evaluate(records, targets, predictions, sources, gross_um=25.0):
    """Same metrics/masks as Stage A, plus the endpoint-defined inner span.

    Eight-head results are read unchanged. A four-head result may also be
    evaluated: its absent outer heads are padded internally only for reuse of
    the existing metrics, then excluded from every reported table.
    """
    expanded = {}
    for key, prediction in predictions.items():
        rows = np.asarray(prediction["rows"])
        keep = np.asarray(prediction["retained"], bool)
        if rows.ndim != 2 or rows.shape != keep.shape or rows.shape[0] not in (4, 8):
            raise ValueError(f"Expected matching [4 or 8, A-line] arrays: {key}")
        if rows.shape[0] == 4:
            rows = np.concatenate([rows, np.full_like(rows, np.nan, dtype=float)])
            keep = np.concatenate([keep, np.zeros_like(keep)])
        expanded[key] = {**prediction, "rows": rows, "retained": keep}
    report = evaluate_eight(records, targets, expanded, sources, gross_um)
    for field in ("summary", "animal_macro", "per_bscan"):
        report[field] = [row for row in report[field] if is_inner(row)]
    # Recompute decision counts on the four reported boundaries only.
    for decision in report["decisions"]:
        key = decision["key"]
        valid = targets[key]["valid"][:4]
        p = expanded.get(key)
        rows = np.full(valid.shape, np.nan) if p is None else p["rows"][:4]
        keep = np.zeros_like(valid) if p is None else p["retained"][:4]
        decision.update(eligible=bool(valid.any()),
                        raw_prediction_columns=int(np.isfinite(rows).sum()),
                        retained_prediction_columns=int((keep & np.isfinite(rows)).sum()),
                        total_boundary_columns=int(rows.size))

    accum = defaultdict(list)
    for r in records:
        t, p = targets[r["key"]], expanded.get(r["key"])
        truth = t["rows_label"]
        rows = np.full_like(truth, np.nan) if p is None else p["rows"]
        keep = np.zeros_like(t["valid"]) if p is None else p["retained"]
        delta = ((rows[3] - rows[0]) - (truth[3] - truth[0])) * r["px_um"]
        valid = t["valid"][0] & t["valid"][3]
        for mode, retained in (("raw", np.ones_like(valid)),
                               ("retained", keep[0] & keep[3])):
            st = stats(delta, valid, retained, gross_um, sources[r["scan_id"]]["aline_um"])
            report["per_bscan"].append(dict(key=r["key"], animal=r["animal"],
                qc_group=r["qc_group"], scope_status=r["scope_status"],
                kind="thickness", name="INNER_RETINA", mode=mode, **st))
            for axis, group in (("pooled", "all"), ("animal", r["animal"]),
                                ("qc", r["qc_group"]), ("biology", r["biological_group"]),
                                ("scope", r["scope_status"])):
                accum[axis, group, mode].append((delta, valid, retained, st))
    for (axis, group, mode), parts in sorted(accum.items()):
        joined = [np.concatenate([np.r_[p[k], False if k else np.nan] for p in parts])
                  for k in range(3)]
        st = stats(*joined, gross_um=gross_um)
        for field in ("longest_failure_um", "longest_gross_error_um"):
            st[field] = max(p[3][field] for p in parts)
        medians = [p[3]["median_abs_um"] for p in parts if p[3]["median_abs_um"] is not None]
        st["historical_median_of_bscan_medians_um"] = float(np.median(medians)) if medians else None
        st["historical_p90_of_bscan_medians_um"] = float(np.quantile(medians, .9)) if medians else None
        report["summary"].append(dict(axis=axis, group=group, kind="thickness",
                                      name="INNER_RETINA", mode=mode, **st))
    for mode in ("raw", "retained"):
        items = [s for s in report["summary"] if s["axis"] == "animal"
                 and s["kind"] == "thickness" and s["name"] == "INNER_RETINA"
                 and s["mode"] == mode and s["n_eligible"]]
        row = dict(kind="thickness", name="INNER_RETINA", mode=mode, n_animals=len(items))
        for field in ("mean_abs_um", "mean_signed_um", "coverage", "failure_fraction_of_eligible"):
            values = [s[field] for s in items if s[field] is not None]
            row[field] = float(np.mean(values)) if values else None
            row[field + "_n_animals"] = len(values)
        report["animal_macro"].append(row)
    report["scope"] = "inner-retina: ILM, RNFL_GCL, GCL_IPL, IPL_INL; RNFL, GCL, IPL, INNER_RETINA"
    report["retention_convention"] = "Saved withholding is unchanged, including original outer-surface interaction flags."
    return report


def sensitivity(records):
    return (("with_b0510", records),
            ("without_b0510", [r for r in records if r["key"] != SENSITIVITY_KEY]))


def load_predictions(directory, records):
    predictions, provenance = {}, {}
    for r in records:
        path = Path(directory) / f"{r['key']}.npz"
        if path.exists():
            provenance[r["key"]] = fingerprint(path)
            with np.load(path, allow_pickle=False) as d:
                predictions[r["key"]] = {k: d[k].copy() for k in d.files}
            if fingerprint(path) != provenance[r["key"]]:
                raise RuntimeError(f"Prediction changed during read: {path}")
    return predictions, provenance


def run(args):
    # Check before constructing Dataset: it has no independent test guard.
    if args.split not in ("train", "validation"):
        raise ValueError("Final-test animals are locked")
    from stage_a.data import Dataset
    data = Dataset(args.data, args.split, eligible_only=False)
    out = output_dir(args.out)
    if any(out.iterdir()):
        raise FileExistsError("Choose an empty output directory to freeze a new evaluation")
    targets = {}
    for r in data.records:
        with np.load(r["targets"], allow_pickle=False) as d:
            targets[r["key"]] = {k: d[k].copy() for k in d.files}
    predictions, provenance = load_predictions(args.eval, data.records)
    rows, macro, per_bscan = [], [], []
    for scenario, subset in sensitivity(data.records):
        report = evaluate(subset, targets, predictions, data.manifest["sources"], args.gross_um)
        rows.extend(dict(sensitivity=scenario, **r) for r in report["summary"])
        macro.extend(dict(sensitivity=scenario, **r) for r in report["animal_macro"])
        per_bscan.extend(dict(sensitivity=scenario, **r) for r in report["per_bscan"])
        write_json(out / f"metrics_{scenario}.json", report)
    write_csv(out / "metrics.csv", rows)
    write_csv(out / "animal_macro.csv", macro)
    write_csv(out / "per_bscan.csv", per_bscan)
    write_json(out / "evaluation_meta.json", dict(identity=data.identity, split=args.split,
        predictions=provenance, targets=[r["targets_fingerprint"] for r in data.records],
        sensitivity_key=SENSITIVITY_KEY, experimental=True, validated=False,
        checkpoint_retrained=False, ground_truth="Frozen eligible human-drawn targets only"))
    print(f"Frozen inner-retina evaluation: {len(predictions)}/{len(data.records)} decisions; {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT)
    parser.add_argument("--split", choices=("train", "validation"), default="validation")
    parser.add_argument("--eval", type=Path, required=True, help="Existing Stage A prediction directory")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--gross-um", type=float, default=25.)
    run(parser.parse_args())
