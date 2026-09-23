"""Full-cohort descriptive baseline or animal-excluded decoder comparison.

The all-label model is never used for an independent error estimate. The old
v4 baseline is explicitly stratified by original model-development membership.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from stage_a.common import DEFAULT, output_dir, write_json, write_csv, fingerprint, verify
from stage_a_inner_retina import evaluate, sensitivity


def reports(records, targets, predictions, sources, original, method):
    rows = []
    strata = {"full_manual_cohort": (records, targets)}
    remote = {key: {**t, "valid": t["valid"] & t["original_stage_a_scope"][None]} for key,t in targets.items()}
    strata["original_stage_a_remote_control_scope"] = (records, remote)
    for split, animals in original["animals"].items():
        strata[f"historical_{split}_animals"] = ([r for r in records if r["animal"] in animals], targets)
    for name, (selected, truth) in strata.items():
        for scenario, subset in sensitivity(selected):
            result = evaluate(subset, truth, predictions, sources)
            rows.extend(dict(decoder=method, evidence_scope=name, sensitivity=scenario, **r) for r in result["summary"])
    return rows


def run(args):
    # Torch-free loading is optional for the saved-fold evaluation. Importing
    # matplotlib via FrozenSplit is avoided in this module for Windows OpenMP.
    import torch
    from stage_a.data import Dataset
    from stage_a.train import load_checkpoint
    from stage_a_inner_train import load as load_inner
    from stage_a_inner_calibrate import predicted
    from stage_a_decoder import fit
    torch.set_num_threads(2)
    datasets = [Dataset(args.data, s, eligible_only=False) for s in ("train", "validation")]
    records = [r for d in datasets for r in d.records]
    targets = {}
    for r in records:
        with np.load(r["targets"], allow_pickle=False) as d:
            targets[r["key"]] = {k: d[k].copy() for k in d.files}
    original = json.loads((args.original / "partitions.json").read_text())
    out = output_dir(args.out)
    if (out / "evaluation_summary.json").exists():
        raise FileExistsError("Evaluation is already frozen; choose a new directory")
    metrics, movements, provenance = [], [], {}
    fit_checkpoint = getattr(args, "fit_checkpoint", None)
    if args.checkpoint or fit_checkpoint:
        path = args.checkpoint or fit_checkpoint
        model, ck = (load_checkpoint if args.checkpoint else load_inner)(path, args.device)
        model.eval()
        if args.checkpoint and fingerprint(path)["sha256"] != "855397f3d77fbce2246e619ba9b06efb6339ef56ca0127dce4b14f6a9a3c9cbd":
            raise ValueError("Descriptive comparator must be the unchanged delivered v4 checkpoint")
        if fit_checkpoint and (ck["config"]["held_animal"] != "ALL_LABELLED"
                               or ck["identity"] != datasets[0].identity):
            raise ValueError("Fit diagnostic requires this dataset's explicit all-label inference model")
        if ck["identity"]["preprocessing"] != datasets[0].identity["preprocessing"]:
            raise ValueError("Comparator image preprocessing differs")
        fit(argparse.Namespace(data=args.data, out=out / "original_training_constraints",
            animals=original["animals"]["train"] if args.checkpoint else sorted({r["animal"] for r in records if r["eligible"]}), margin_fraction=.2))
        bounds = json.loads((out / "original_training_constraints/constraints.json").read_text())
        # This baseline is a descriptive cross-version comparison, not a new
        # checkpoint claiming it was trained on the full cohort.
        predictions = {method: {} for method in ("soft", "dp_project")}
        for data in datasets:
            for r in data.records:
                if not targets[r["key"]]["valid"][:4].any():
                    continue
                entry = data.cache["entries"][r["key"]]
                with np.load(entry["file"]["path"], allow_pickle=False) as d:
                    x = d["x"]
                for method in predictions:
                    t = targets[r["key"]]
                    result = predicted(model, x, t["scope"], t["shadow"], method, bounds, args.device)
                    for field in ("rows", "raw_rows", "full_raw_rows"):
                        result[field] -= entry["label_offset"]
                    predictions[method][r["key"]] = result
                    folder = output_dir(out / method)
                    np.savez_compressed(folder / f"{r['key']}.npz", **result)
        provenance["checkpoint"] = fingerprint(path)
        kind = ("Descriptive old v4 baseline; five animal groups contributed training and two contributed validation/checkpoint selection. Historical test animals are stratified separately. This is not pooled independent performance."
                if args.checkpoint else "IN-SAMPLE FIT DIAGNOSTIC ONLY. Every manually supported animal contributed training. These errors do not estimate generalization or deployment accuracy.")
    else:
        if not args.calibrations:
            raise ValueError("Specify the old baseline checkpoint or saved calibration folders")
        predictions = {}
        for spec in args.calibrations:
            method, folder = spec.split("=", 1)
            folder = Path(folder)
            summary = json.loads((folder / "calibration_summary.json").read_text())
            predictions[method] = {}
            for r in records:
                if not targets[r["key"]]["valid"][:4].any():
                    continue
                path = folder / r["animal"] / "held" / f"{r['key']}.npz"
                with np.load(path, allow_pickle=False) as d:
                    predictions[method][r["key"]] = {k: d[k].copy() for k in d.files}
            for fp in summary["checkpoints"].values(): verify(fp)
            provenance[method] = fingerprint(folder / "calibration_summary.json")
        kind = "Animal-excluded development cross-validation. Each evaluated animal was absent from both its network training and cutoff calibration. All-label inference model excluded."
    for method, prediction in predictions.items():
        metrics.extend(reports(records, targets, prediction, datasets[0].manifest["sources"], original, method))
        for r in records:
            if r["key"] not in prediction: continue
            p = prediction[r["key"]]
            raw = p["raw_rows"][:4]
            delta = np.abs(p["rows"] - raw)
            valid = targets[r["key"]]["valid"][:4]
            moved = valid & (delta > 5)
            movements.append(dict(key=r["key"], animal=r["animal"], decoder=method,
                eligible_boundary_columns=int(valid.sum()),
                moved_gt5_px=int(moved.sum()),
                mean_entropy_moved=float(p["entropy"][moved].mean()) if moved.any() else None,
                raw_crossing_alines=int(np.any(np.diff(raw, axis=0) < 0, axis=0).sum()),
                decoded_crossing_alines=int(np.any(np.diff(p["rows"], axis=0) < 0, axis=0).sum()),
                alines=p["rows"].shape[1]))
    write_csv(out / "metrics.csv", metrics)
    write_csv(out / "movement.csv", movements)
    write_json(out / "evaluation_summary.json", dict(evidence=kind, provenance=provenance,
        n_corrected_bscans=sum(r["verdict"] == "corrected" for r in records),
        n_manually_supported_inner_bscans=sum(t["valid"][:4].any().item() for t in targets.values()),
        former_test_released=True, production_validated=False,
        scope_sensitivity="Full manual cohort and original Stage A remote/control mask are both reported.",
        missing_predictions_not_dropped=True))
    print(out / "evaluation_summary.json", flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--original", type=Path, default=DEFAULT)
    p.add_argument("--checkpoint", type=Path)
    p.add_argument("--fit-checkpoint", type=Path, help="Explicitly in-sample diagnostic of the all-label model")
    p.add_argument("--calibrations", nargs="+")
    p.add_argument("--device", default="cpu")
    p.add_argument("--out", type=Path, required=True)
    run(p.parse_args())
