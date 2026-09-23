"""Cross-fitted entropy coverage/error curves with disjoint calibration animals."""
import argparse
from collections import defaultdict
import json
from pathlib import Path

import numpy as np
import torch

from stage_a.common import DEFAULT, output_dir, write_csv, write_json, fingerprint, digest
from stage_a.data import Dataset
from stage_a.model import decode
from stage_a_inner_train import load
from stage_a_inner_retina import evaluate, sensitivity
from stage_a_decoder import fit as fit_bounds, graph_cut, dp_project


def predicted(model, x, scope, shadow, method, bound, device):
    with torch.no_grad():
        logits, _ = model(torch.from_numpy(x).unsqueeze(0).to(device))
        rows, entropy = decode(logits)
        cost = (-logits[:, :4].log_softmax(2))[0].cpu().numpy() if method != "soft" else None
    full = rows[0].cpu().numpy()
    rows, entropy = full[:4].copy(), entropy[0].cpu().numpy()[:4]
    reason = np.zeros(rows.shape, np.uint8)
    reason[:, ~scope] |= 1; reason[:, shadow] |= 2
    reason[~np.isfinite(rows)] |= 4
    cross = full[:-1] > full[1:]
    original = np.zeros(full.shape, np.uint8)
    original[:-1][cross] |= 8; original[1:][cross] |= 8
    if method == "soft":
        reason |= original[:4]
    else:
        func = graph_cut if method == "graph_cut" else dp_project
        rows = func(cost, bound["minimum"], bound["maximum"], 2)
    return dict(rows=rows.astype(np.float32), entropy=entropy, retained=reason == 0, reason_bits=reason,
                raw_rows=full[:4].copy(), full_raw_rows=full.copy())


def apply_threshold(predictions, threshold):
    output = {}
    for key, p in predictions.items():
        abstain = ~np.isfinite(p["entropy"]) | (p["entropy"] > threshold)
        reasons = p["reason_bits"].copy()
        reasons[abstain] |= 16
        output[key] = {**p, "retained": p["retained"] & ~abstain, "reason_bits": reasons}
    return output


def run(args):
    torch.set_num_threads(2)
    datasets = [Dataset(args.data, s, eligible_only=False) for s in ("train", "validation")]
    records = [r for d in datasets for r in d.records]
    lookup = {r["key"]: (d, r) for d in datasets for r in d.records}
    protocol = json.loads((args.models / "protocol.json").read_text())
    released = bool(datasets[0].partitions.get("authorization", {}).get("former_test_animals_released"))
    completion = args.models / "training_complete.json"
    if not completion.exists(): completion = args.models / "fold_evaluation_ready.json"
    if not completion.exists():
        raise ValueError("Complete and verify every independent evaluation fold before calibrating")
    complete = json.loads(completion.read_text())
    if complete["protocol_digest"] != digest(protocol):
        raise ValueError("Completed training does not match the calibration protocol")
    if protocol["dataset_identity"] != datasets[0].identity:
        raise ValueError("Cross-validation dataset changed")
    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    out = output_dir(args.out)
    if (out / "calibration_summary.json").exists():
        raise FileExistsError("Choose a new calibration version")
    targets, held_predictions, held_records, checkpoints = {}, {}, [], {}
    transferred, transfer_metrics = [], []
    quantiles = [.5, .6, .7, .8, .9, .95, .98, 1.]
    for fold in protocol["folds"]:
        held, calibration = fold["held_animal"], fold["calibration_animal"]
        if held == calibration or set(fold["training_animals"]) & {held, calibration}:
            raise ValueError("Train/calibration/held-out animal leakage")
        checkpoint = args.models / held / "last.pt"
        model, ck = load(checkpoint, device)
        checkpoints[held] = fingerprint(checkpoint)
        if (ck["protocol_digest"] != digest(protocol) or ck["epoch"] != protocol["epochs"]
                or ck["identity"] != datasets[0].identity):
            raise ValueError("Fold checkpoint identity or training budget differs from protocol")
        if any(ck["config"].get(k) != v for k, v in fold.items()):
            raise ValueError("Fold checkpoint does not match declared animal exclusions")
        model.eval()
        bound = None
        if args.decoder != "soft":
            bound_dir = out / held / "training_constraints"
            fit_bounds(argparse.Namespace(data=args.data, out=bound_dir, animals=fold["training_animals"], margin_fraction=.2))
            bound = json.loads((bound_dir / "constraints.json").read_text())
        selected = [r for r in records if r["animal"] in {held, calibration}]
        predictions = {}
        for r in selected:
            data, _ = lookup[r["key"]]
            entry = data.cache["entries"][r["key"]]
            with np.load(r["targets"], allow_pickle=False) as d:
                target = {k: d[k].copy() for k in d.files}
            targets[r["key"]] = target
            with np.load(entry["file"]["path"], allow_pickle=False) as d:
                x = d["x"]
            p = predicted(model, x, target["scope"], target["shadow"], args.decoder, bound, device)
            for field in ("rows", "raw_rows", "full_raw_rows"):
                p[field] -= entry["label_offset"]
            p["label_offset"] = np.array(entry["label_offset"])
            predictions[r["key"]] = p
            role = "held" if r["animal"] == held else "calibration"
            directory = output_dir(out / held / role)
            np.savez_compressed(directory / f"{r['key']}.npz", **p)
        cal_records = [r for r in selected if r["animal"] == calibration]
        test_records = [r for r in selected if r["animal"] == held]
        calibration_entropy = np.concatenate([predictions[r["key"]]["entropy"][targets[r["key"]]["valid"][:4]] for r in cal_records])
        calibration_entropy = calibration_entropy[np.isfinite(calibration_entropy)]
        if not len(calibration_entropy):
            raise ValueError("Calibration animal has no manual boundary evidence")
        test_pred = {r["key"]: predictions[r["key"]] for r in test_records}
        held_predictions.update(test_pred); held_records.extend(test_records)
        for q in quantiles:
            threshold = float(np.quantile(calibration_entropy, q))
            transferred.append(dict(held_animal=held, calibration_animal=calibration,
                calibration_quantile=q, threshold=threshold, calibration_columns=len(calibration_entropy)))
            for scenario, subset in sensitivity(test_records):
                report = evaluate(subset, targets, apply_threshold(test_pred, threshold), datasets[0].manifest["sources"])
                transfer_metrics.extend(dict(held_animal=held, calibration_animal=calibration,
                    calibration_quantile=q, threshold=threshold, sensitivity=scenario, **r)
                    for r in report["summary"] if r["axis"] == "pooled" and r["mode"] == "retained")
        print(f"Calibrated on {calibration}; measured on held-out {held}", flush=True)
        del model
    curves = []
    thresholds = [None] + np.arange(.2, 1.001, .05).round(4).tolist()
    for threshold in thresholds:
        pred = held_predictions if threshold is None else apply_threshold(held_predictions, threshold)
        for scenario, subset in sensitivity(held_records):
            report = evaluate(subset, targets, pred, datasets[0].manifest["sources"])
            curves.extend(dict(threshold="unthresholded" if threshold is None else threshold,
                sensitivity=scenario, **r) for r in report["summary"]
                if r["axis"] in ("pooled", "animal") and r["mode"] == "retained")
    spread = []
    for q in quantiles:
        for name in ("ILM", "RNFL_GCL", "GCL_IPL", "IPL_INL", "RNFL", "GCL", "IPL", "INNER_RETINA"):
            for scenario in ("with_b0510", "without_b0510"):
                selected = [r for r in transfer_metrics if r["calibration_quantile"] == q
                            and r["name"] == name and r["sensitivity"] == scenario and r["n_eligible"]]
                coverage = [r["coverage"] for r in selected if r["coverage"] is not None]
                tails = [r["p95_abs_um"] for r in selected if r["p95_abs_um"] is not None]
                spread.append(dict(calibration_quantile=q, name=name, sensitivity=scenario,
                    n_animals=len(selected), coverage_min=min(coverage) if coverage else None,
                    coverage_max=max(coverage) if coverage else None,
                    coverage_mean=float(np.mean(coverage)) if coverage else None,
                    n_animals_with_retained_p95=len(tails),
                    retained_p95_min_um=min(tails) if tails else None,
                    retained_p95_max_um=max(tails) if tails else None))
    write_csv(out / "transferred_thresholds.csv", transferred)
    write_csv(out / "held_animal_curves.csv", transfer_metrics)
    write_csv(out / "fixed_threshold_curves.csv", curves)
    write_csv(out / "per_animal_spread.csv", spread)
    write_json(out / "calibration_summary.json", dict(decoder=args.decoder,
        n_held_animals=len(protocol["folds"]), protocol=fingerprint(args.models / "protocol.json"),
        checkpoints=checkpoints, implementation=fingerprint(Path(__file__)),
        held_animals=[f["held_animal"] for f in protocol["folds"]],
        roles=f"{len(protocol['folds'][0]['training_animals'])} train; one distinct calibration animal supplies entropy quantiles; another animal supplies held-out coverage and error. Roles rotate deterministically. The separate all-label model never supplies held-animal accuracy predictions.",
        evidence=("Development cross-validation of the specified workflow. "
            + ("The user released former test animals into this new cohort; no untouched test set remains. " if released else "Final-test animals remain locked. ")
            + "Legacy surface-wide annotations and the small animal count limit generalisation."),
        quote_policy=f"Quote only measured per-animal coverage/error ranges for this {len(protocol['folds'])}-animal study with b0510 sensitivity; no promised deployment coverage or universal quality score.",
        deployment_threshold=None, recommendation="Inspect animal spread before proposing a scientific error/coverage criterion. The review queue may use an explicitly experimental per-volume quantile for triage.",
        thresholds_selected_on_held_animal=False, validated=False, final_test_used=released,
        former_test_animals_released=released))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, default=DEFAULT)
    p.add_argument("--models", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--decoder", choices=("soft", "dp_project", "graph_cut"), default="soft")
    p.add_argument("--device")
    run(p.parse_args())
