"""Outer-anchor-free hybrid control: held-animal U-Net endpoints + inner DP.

This is separate from the matched-endpoint classical prior ablation. It uses
only ILM/IPL_INL predictions from an animal-excluded network, never PR_RPE.
The classical IPL_INL prior is not refit. Both the endpoint change and the
inner-cost change are disclosed, and the full held-animal U-Net is the control.
"""
from collections import defaultdict
import json
from pathlib import Path
import time

import numpy as np
import torch

from octa.volio import ProcessedVolume
from eight_surface.segment import detect_orientation, prepare_bscan
from eight_surface.volume import average_bscans
from eight_surface.labels import load_label
from stage_a.common import output_dir, verify, write_json, write_csv, digest, fingerprint
from stage_a.geometry import preprocess, label_offset
from stage_a.model import decode
from stage_a_inner_train import load
from stage_a_inner_retina_audit import permitted_records, manual_valid, spread_parts, prior_summary
from stage_a_inner_retina import evaluate, sensitivity
from .inner_band import solve_inner


def solve_with_missing_endpoints(images, anchors, fractions, shadow):
    """Keep infeasible endpoint columns missing without NaNs poisoning a DP.

    Temporary lateral fills supply computational bounds only. Original endpoint
    predictions are restored, and both internal boundaries remain NaN wherever
    the original endpoints could not support the classical solver's three gaps.
    """
    invalid = (~np.isfinite(anchors).all(1) | (anchors[:, 1] - anchors[:, 0] < 6)
               | (anchors[:, 0] < 0) | (anchors[:, 1] > images.shape[1]-1))
    work = anchors.copy()
    x = np.arange(anchors.shape[2])
    for b in range(len(work)):
        good = ~invalid[b]
        for k in range(2):
            if good.any():
                work[b, k, ~good] = np.interp(x[~good], x[good], work[b, k, good])
            else:
                work[b, k] = 0 if k == 0 else images.shape[1] - 1
    result = solve_inner(images, work, fractions, shadow)
    result[:, [0, 3]] = anchors
    for k in (1, 2):
        result[:, k][invalid] = np.nan
    return result


def run(args):
    if not args.loao:
        raise ValueError("The learned-endpoint control requires --loao")
    torch.set_num_threads(2)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    root, models = Path(args.data), Path(args.inner_anchor_models)
    m = json.loads((root / "manifest.json").read_text())
    partitions = json.loads((root / "partitions.json").read_text())
    verify(partitions["manifest"])
    protocol = json.loads((models / "protocol.json").read_text())
    completion = models / "training_complete.json"
    if not completion.exists(): completion = models / "fold_evaluation_ready.json"
    if not completion.exists():
        raise ValueError("Finish and verify every independent evaluation fold before this control")
    metadata = permitted_records(m, partitions)
    permitted = {r["animal"] for r in metadata}
    complete = json.loads(completion.read_text())
    if complete["protocol_digest"] != digest(protocol) or protocol["dataset_identity"]["dataset_id"] != m["dataset_id"]:
        raise ValueError("Independent-model protocol does not match this frozen dataset")
    if any(not set(f["training_animals"] + [f["held_animal"], f["calibration_animal"]]).issubset(permitted)
           for f in protocol["folds"]):
        raise ValueError("Endpoint model includes an unknown or final-test animal")
    records = []
    for r in metadata:
        verify(r["label"])
        lab = load_label(r["label"]["path"])
        records.append((r, lab, manual_valid(lab)))
    folds = {f["held_animal"]: f for f in protocol["folds"]}
    priors = {}
    for animal in sorted({r["animal"] for r in metadata}):
        if animal not in folds or animal in folds[animal]["training_animals"]:
            raise ValueError("Endpoint model was not trained without the evaluation animal")
        training = [item for item in records if item[0]["animal"] != animal]
        fitted = [prior_summary(spread_parts(training, k, 3)) for k in (1, 2)]
        fractions = [f["fraction"] for f in fitted]
        if not 0 < fractions[0] < fractions[1] < 1:
            raise ValueError("Manual inner fractions are not ordered")
        priors[animal] = dict(fractions=fractions,
            training_animals=sorted({r["animal"] for r, _, _ in training}))
    out = output_dir(args.out)
    by_scan = defaultdict(list)
    for r in metadata:
        by_scan[r["scan_id"]].append(r)
    baseline, predictions, targets = {}, {}, {}
    started = time.monotonic()
    for number, (sid, scan_records) in enumerate(sorted(by_scan.items()), 1):
        animal = scan_records[0]["animal"]; src = m["sources"][sid]
        checkpoint = models / animal / "last.pt"
        config = dict(checkpoint=fingerprint(checkpoint), source=src["source"], priors=priors[animal],
            bscan_avg=3, attract=.05, code=fingerprint(Path(__file__)),
            solver=fingerprint(Path(__file__).with_name("inner_band.py")),
            endpoints="held-animal U-Net ILM/IPL_INL only; no PR_RPE coordinate consumed")
        job_id = digest(config)
        saved = out / f"{sid}_predictions.npz"
        if saved.exists():
            with np.load(saved, allow_pickle=False) as d:
                if str(d["job_id"]) != job_id:
                    raise ValueError("Hybrid inference configuration changed")
                raw, candidate, bscans = d["baseline"], d["candidate"], d["bscans"]
        else:
            model, ck = load(checkpoint, device); model.eval()
            if (ck["config"]["held_animal"] != animal or animal in ck["config"]["training_animals"]
                    or ck["protocol_digest"] != digest(protocol) or ck["epoch"] != protocol["epochs"]):
                raise ValueError("Held-animal endpoint checkpoint mismatch")
            verify(src["source"]); verify(src["segmentation"])
            with ProcessedVolume(src["source"]["path"]) as volume:
                full = volume.read_volume(channel="struct")
            vhi = detect_orientation(full.mean(axis=(0, 1)))
            offset = label_offset(src["label_band"], full.shape[2], vhi)
            with np.load(src["segmentation"]["path"], allow_pickle=False) as d:
                shadow = d["shadow"].astype(bool)
            # Use the original label crop only as a coordinate frame for the
            # image costs. Endpoint estimates themselves use full native depth.
            lo, hi = src["label_band"]
            raw, candidate, bscans = [], [], []
            predicted = {}
            for r in scan_records:
                b = r["bscan"]
                start, end = max(0, b-6), min(len(full), b+7)
                for j in range(start, end):
                    if j not in predicted:
                        x, _, _ = preprocess(full[j], vhi)
                        with torch.no_grad():
                            logits, _ = model(torch.from_numpy(x).unsqueeze(0).to(device))
                            native, _ = decode(logits[:, :4])
                        predicted[j] = native[0].cpu().numpy() - offset
                original = np.stack([predicted[j] for j in range(start, end)])
                images = average_bscans(np.stack([prepare_bscan(full[j, :, lo:hi], vhi)
                                                  for j in range(start, end)]), 3)
                changed = solve_with_missing_endpoints(images, original[:, [0, 3]],
                    priors[animal]["fractions"], shadow[start:end])
                np.testing.assert_array_equal(changed[:, [0, 3]], original[:, [0, 3]])
                raw.append(original[b-start]); candidate.append(changed[b-start]); bscans.append(b)
            raw, candidate, bscans = map(np.asarray, (raw, candidate, bscans))
            np.savez_compressed(saved, baseline=raw, candidate=candidate, bscans=bscans, job_id=np.array(job_id))
            del full, model
        for r in scan_records:
            index = int(np.flatnonzero(bscans == r["bscan"])[0])
            with np.load(r["targets"], allow_pickle=False) as d:
                t = {k: d[k].copy() for k in d.files}
            targets[r["key"]] = t
            for store, rows in ((baseline, raw[index]), (predictions, candidate[index])):
                keep = np.broadcast_to(t["scope"] & ~t["shadow"], rows.shape).copy() & np.isfinite(rows)
                crossing = rows[:-1] > rows[1:]
                keep[:-1][crossing] = False; keep[1:][crossing] = False
                store[r["key"]] = dict(rows=rows, retained=keep)
        print(f"Outer-free hybrid {number}/{len(by_scan)}: {sid} ({time.monotonic()-started:.1f}s)", flush=True)
    metrics = []
    for name, pred in (("held_animal_unet_inner", baseline), ("held_animal_anchors_inner_classical", predictions)):
        for scenario, selected in sensitivity(metadata):
            report = evaluate(selected, targets, pred, m["sources"])
            metrics.extend(dict(predictor=name, sensitivity=scenario, **r) for r in report["summary"])
            write_json(out / f"{name}_{scenario}.json", report)
    write_csv(out / "metrics.csv", metrics)
    write_json(out / "experiment.json", dict(priors=priors, protocol=fingerprint(models / "protocol.json"),
        leave_one_animal_out=True, n_manual_bscans=len(metadata), outer_anchor_used=False,
        IPL_INL_classical_prior_refit=False, endpoint_arrays_unchanged=True, bscan_avg=3, attract=.05,
        comparison="Both methods share held-animal learned ILM/IPL_INL estimates. The hybrid replaces only the two middle boundary estimates with classical image costs and manually fitted inner fractions.",
        limitation="A hybrid control, not a claim that the original classical endpoint provider became independent of PR_RPE. The eight-head endpoint network was trained with outer auxiliary labels, but inference consumes no outer-surface coordinates.",
        final_test_used=bool(partitions.get("authorization", {}).get("former_test_animals_released")), production_adopted=False))
