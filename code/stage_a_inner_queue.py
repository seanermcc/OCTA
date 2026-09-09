"""Inference and experimental triage queue; writes GUI packs, never labels."""
import argparse
import json
from pathlib import Path

import numpy as np

from stage_a.common import DEFAULT, output_dir, write_csv, write_json, fingerprint, verify, digest


def longest_run(mask):
    edge = np.diff(np.r_[False, np.asarray(mask, bool), False].astype(np.int8))
    starts, ends = np.flatnonzero(edge == 1), np.flatnonzero(edge == -1)
    return int((ends - starts).max()) if len(starts) else 0


def triage(rows, entropy, reasons, scope, shadow, quantile):
    available = np.broadcast_to(scope[:, None, :] & ~shadow[:, None, :], entropy.shape)
    finite = available & np.isfinite(entropy)
    if not finite.any():
        raise ValueError("Volume has no in-scope, unshadowed evidence for triage")
    cutoff = float(np.quantile(entropy[finite], quantile))
    reasons = reasons.copy()
    reasons[~np.isfinite(entropy) | (entropy > cutoff)] |= 16
    retained = reasons == 0
    result = []
    for b in range(len(rows)):
        denom = int(available[b].sum())
        fraction = float((retained[b] & available[b]).sum() / denom) if denom else None
        suspect = available[b].any(0) & ((reasons[b] & (4 | 8 | 16)) != 0).any(0)
        run = longest_run(suspect)
        # A review priority heuristic, not a measured human-time or quality score.
        score = (1 - fraction) + run / rows.shape[2] if fraction is not None else -1.
        result.append(dict(bscan=b, retained_boundary_fraction=fraction,
            available_boundary_columns=denom, longest_flagged_run_alines=run,
            priority_heuristic=score, shadow_fraction=float(shadow[b].mean()),
            crossing_alines=int(np.any(rows[b, :-1] > rows[b, 1:], axis=0).sum())))
    return retained, reasons, cutoff, result


def run(args):
    import torch
    from eight_surface.config import SURFACE_NAMES, LAYER_DEFS
    from eight_surface.review import write_review_pack, _spread_pick
    from eight_surface.segment import detect_orientation, prepare_bscan
    from octa.volio import ProcessedVolume
    from stage_a.geometry import PREPROCESS, preprocess, label_offset
    from stage_a_inner_calibrate import predicted
    from stage_a.train import load_checkpoint
    from stage_a_inner_train import load
    from stage_a_decoder import dp_project, graph_cut
    torch.set_num_threads(2)
    m = json.loads((args.data / "manifest.json").read_text())
    partitions = json.loads((args.data / "partitions.json").read_text())
    permitted = set(partitions["animals"]["train"] + partitions["animals"]["validation"])
    # Resolve and check the whole job before loading any volume or model output.
    if any(s not in m["sources"] or m["sources"][s]["metadata"]["animal"] not in permitted for s in args.scan_ids):
        raise ValueError("Unknown or final-test scan: queue access denied")
    out = output_dir(args.out)
    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    ck = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    loader = load if ck.get("format") == "inner-retina-experiment-v1" else load_checkpoint
    model, ck = loader(args.checkpoint, device)
    model.eval()
    if ck["identity"]["dataset_id"] != m["dataset_id"] or ck["identity"]["preprocessing"] != PREPROCESS:
        raise ValueError("Model and frozen volume preprocessing differ")
    bounds = json.loads(args.constraints.read_text()) if args.constraints else None
    if args.decoder != "soft" and bounds is None:
        raise ValueError("Measured training-only bounds required")
    all_rows, summaries = [], []
    for sid in args.scan_ids:
        src = m["sources"][sid]
        for key in ("source", "scope_hash", "segmentation"):
            verify(src[key])
        directory = output_dir(out / sid)
        job = dict(scan_id=sid, checkpoint=fingerprint(args.checkpoint), source=src["source"],
            scope=src["scope_hash"], segmentation=src["segmentation"], decoder=args.decoder,
            constraints=None if args.constraints is None else fingerprint(args.constraints),
            preprocessing=PREPROCESS, code=fingerprint(Path(__file__)),
            prediction_code=fingerprint(Path(__file__).with_name("stage_a_inner_calibrate.py")),
            decoder_code=fingerprint(Path(__file__).with_name("stage_a_decoder.py")))
        job_id = digest(job)
        job_file = directory / "job.json"
        if job_file.exists() and json.loads(job_file.read_text())["job_id"] != job_id:
            raise ValueError("Queue inference job changed; use a new output directory")
        write_json(job_file, dict(job=job, job_id=job_id))
        with np.load(src["scope_path"], allow_pickle=False) as d:
            scope = d["allowed"].astype(bool)
        with np.load(src["segmentation"]["path"], allow_pickle=False) as d:
            shadow = d["shadow"].astype(bool)
            candidates = d["surfaces"].astype(np.float32)
        with ProcessedVolume(src["source"]["path"]) as volume:
            full = volume.read_volume(channel="struct")
        if list(full.shape) != src["native_shape"] or scope.shape != full.shape[:2] or shadow.shape != scope.shape:
            raise ValueError("Volume, scope, and shadow geometry differ")
        vhi = bool(detect_orientation(full.mean(axis=(0, 1))))
        offset = label_offset(src["label_band"], full.shape[2], vhi)
        chunks = output_dir(directory / "predictions")
        rows, raw_rows, entropy, reason = [], [], [], []
        for b in range(len(full)):
            path = chunks / f"b{b:04d}.npz"
            if path.exists():
                with np.load(path, allow_pickle=False) as d:
                    p = {k: d[k].copy() for k in d.files}
                if str(p["job_id"]) != job_id:
                    raise ValueError("Stale inference chunk")
            else:
                x, _, _ = preprocess(full[b], vhi)
                p = predicted(model, x, scope[b], shadow[b], args.decoder, bounds, device)
                candidate = p["full_raw_rows"].copy()
                candidate[:4] = p["rows"]
                p = dict(rows=p["rows"], entropy=p["entropy"], reason_bits=p["reason_bits"],
                    raw_rows=p["raw_rows"], candidate_rows=candidate, job_id=np.array(job_id))
                np.savez_compressed(path, **p)
            candidates[b, :len(p["candidate_rows"])] = p["candidate_rows"] - offset
            rows.append(p["rows"][:4]); entropy.append(p["entropy"][:4]); reason.append(p["reason_bits"][:4])
            raw_rows.append(p["raw_rows"][:4])
            if b % 32 == 0:
                print(f"{sid}: {b+1}/{len(full)} inference", flush=True)
        rows, entropy, reason = map(np.stack, (rows, entropy, reason))
        raw_rows = np.stack(raw_rows)
        retained, reasons, cutoff, rankings = triage(rows, entropy, reason, scope, shadow, args.quantile)
        experimental = np.full((len(full), len(LAYER_DEFS) + 1, full.shape[1]), np.nan, np.float32)
        for k, (top, bottom) in enumerate(((0, 1), (1, 2), (2, 3), (0, 3))):
            valid = retained[:, top] & retained[:, bottom] & (rows[:, bottom] >= rows[:, top])
            column = k if k < 3 else len(LAYER_DEFS)
            experimental[:, column] = np.where(valid, (rows[:, bottom] - rows[:, top]) * 1.12, np.nan)
        if np.any(np.isfinite(experimental.transpose(0, 2, 1)[shadow])):
            raise AssertionError("Shadowed thickness must stay NaN")
        np.savez_compressed(directory / "experimental_measurements.npz", canonical_rows=rows,
            entropy=entropy, retained=retained, reason_bits=reasons, shadow=shadow, scope=scope,
            thickness_names=np.array([a[0] for a in LAYER_DEFS] + ["INNER_RETINA"]),
            experimental_thickness_um=experimental, validated=np.array(False))
        reviewed = {r["bscan"] for r in m["records"] if r["scan_id"] == sid}
        # Also avoid labels created since the frozen manifest without reading their contents.
        reviewed.update(int(p.stem.rsplit("_b", 1)[1]) for p in args.labels.glob(f"{sid}_b[0-9][0-9][0-9][0-9].npz"))
        score = np.array([r["priority_heuristic"] for r in rankings])
        excluded = reviewed | {r["bscan"] for r in rankings if r["available_boundary_columns"] == 0}
        n = min(args.per_volume, len(score) - len(excluded))
        worst = _spread_pick(score, n, args.min_sep, exclude=excluded) if n else np.array([], int)
        remaining = len(score) - len(excluded | set(worst))
        controls = (_spread_pick(-np.abs(score - np.median(score)), 1, args.min_sep,
                    exclude=excluded | set(worst)) if remaining else np.array([], int))
        picked = np.unique(np.r_[worst, controls])
        if set(picked) & excluded:
            raise AssertionError("Queue selected a previously reviewed or unavailable B-scan")
        lo, hi = src["label_band"]
        images = np.stack([prepare_bscan(b[:, lo:hi], vhi) for b in full])
        del full
        confidence = np.full(candidates.shape, np.nan, np.float32)
        pack = write_review_pack(out / "packs" / f"{sid}_pack.npz", sid, images, candidates,
            confidence, shadow, picked, controls, score, extra=dict(
                candidate_source=np.array(["Automatic suggestions; none are human ground truth"]),
                triage_signal=np.array(["Segmentation uncertainty and flagged runs; acquisition QC separate"]),
                inner_retained=retained[picked], inner_entropy=entropy[picked],
                entropy_threshold=np.array(cutoff), prediction_checkpoint=np.array(str(args.checkpoint))))
        del images
        for r in rankings:
            r.update(scan_id=sid, selected=r["bscan"] in picked, is_control=r["bscan"] in controls,
                     previously_reviewed=r["bscan"] in reviewed, pack=str(pack) if r["bscan"] in picked else "")
        all_rows.extend(rankings)
        summary = dict(scan_id=sid, n_bscans=len(rows), entropy_quantile=args.quantile,
            entropy_cutoff=cutoff, selected_bscans=picked.tolist(), controls=controls.tolist(),
            crossing_alines=sum(r["crossing_alines"] for r in rankings), n_alines=int(scope.size),
            raw_crossing_alines=int(np.any(raw_rows[:, :-1] > raw_rows[:, 1:], axis=1).sum()),
            raw_bscans_with_crossings=int(np.any(raw_rows[:, :-1] > raw_rows[:, 1:], axis=(1, 2)).sum()),
            decoded_bscans_with_crossings=sum(r["crossing_alines"] > 0 for r in rankings),
            orientation_detected=vhi, label_offset=offset, pack=fingerprint(pack),
            unreliable_layers=[a[0] for a in LAYER_DEFS[3:]], shadow_thickness_all_nan=True)
        summaries.append(summary)
        write_json(directory / "volume_summary.json", summary)
        # Preserve the independent acquisition measurements, without legacy quality labels.
        qc_keys = ("retina_cnr", "low_signal_frac", "adjacent_bscan_corr_median", "bscan_discontinuity_p95",
                   "brightness_stripe_power_frac", "repeat_comparable", "repeat_disagreement")
        write_json(directory / "acquisition_qc_separate.json", {k: src.get("qc", {}).get(k) for k in qc_keys})
    all_rows.sort(key=lambda r: -r["priority_heuristic"])
    write_csv(out / "review_queue.csv", all_rows)
    write_csv(out / "selected_review_queue.csv", [r for r in all_rows if r["selected"]])
    write_json(out / "queue_summary.json", dict(volumes=summaries, decoder=args.decoder,
        rank_evidence="Experimental heuristic: withheld fraction plus longest flagged run / width. Human time saved has not been measured.",
        gross_run_policy="True gross-error runs require manual reference and cannot be computed on unlabelled images. This queue reports flagged-run proxies explicitly.",
        threshold_policy="Per-volume entropy quantile for triage only; no calibrated deployment coverage claim.",
        pack_policy="Automatic candidate packs only; existing reviewed B-scans excluded. No label files written.",
        final_test_used=bool(partitions.get("authorization", {}).get("former_test_animals_released")),
        published_anatomy_used_for_scoring=False, validated=False))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, default=DEFAULT)
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--scan-ids", nargs="+", required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--labels", type=Path, default=Path("outputs/eight_surface/labels"))
    p.add_argument("--decoder", choices=("soft", "dp_project", "graph_cut"), default="soft")
    p.add_argument("--constraints", type=Path)
    p.add_argument("--quantile", type=float, default=.9)
    p.add_argument("--per-volume", type=int, default=8)
    p.add_argument("--min-sep", type=int, default=16)
    p.add_argument("--device")
    a = p.parse_args()
    if not 0 < a.quantile <= 1 or a.per_volume < 1:
        p.error("Quantile must lie in (0,1] and per-volume count must be positive")
    run(a)
