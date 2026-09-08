#!/usr/bin/env python3
"""Build eight-boundary manual-review packs and refit from drawn labels.

Run from ``code`` after activating ``octa``::

    python eight_surface/review.py pack --all ../outputs/eight_surface/segmented --total 160
    python eight_surface/label_gui.py ../outputs/eight_surface/review
    python eight_surface/review.py refit --labels ../outputs/eight_surface/labels

``pack`` deliberately does not select from raw scans.  It receives the new
eight-boundary segmentation outputs and produces small, resumable packs.  A
directory of packs can contain far more than 100 B-scans; the GUI opens on the
first undecided item and ``n`` jumps through the remaining queue.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np

CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR))

from octa import reference  # noqa: E402
from octa.volio import ProcessedVolume, find_retina_band  # noqa: E402

from eight_surface import labels as L  # noqa: E402
from eight_surface import provenance as P
from eight_surface.config import (  # noqa: E402
    CASCADE_VERSION, INNER_SURFACES, LAYER_DEFS, N_SURFACES, RELATIVE_PRIORS,
    SURFACE_NAMES,
)
from eight_surface.segment import detect_orientation, prepare_bscan  # noqa: E402
from eight_surface.volume import segment_volume, thickness_maps  # noqa: E402


PX_UM = 1.12
CONF_FLOOR = 0.5
DEFAULT_REVIEW_DIR = Path("../outputs/eight_surface/review")
DEFAULT_LABEL_DIR = Path("../outputs/eight_surface/labels")


def _rank01(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, float)
    if values.size <= 1 or np.allclose(values, values.flat[0]):
        return np.full(values.shape, 0.5)
    return np.argsort(np.argsort(values)).astype(float) / (values.size - 1.0)


def _slow_axis_roughness(surfaces: np.ndarray, k: int = 5) -> np.ndarray:
    n_b = surfaces.shape[0]
    if n_b < 3:
        return np.zeros(n_b)
    out = np.zeros(n_b)
    half = max(1, k // 2)
    for b in range(n_b):
        other = [j for j in range(max(0, b - half), min(n_b, b + half + 1)) if j != b]
        if other:
            out[b] = float(np.nanmedian(np.abs(surfaces[b] - np.median(surfaces[other], axis=0))))
    return out


def _suspect_score(surfaces, confidence, shadow, px_um):
    """Rank B-scans on four distinct segmentation-review signals."""
    maps = thickness_maps(surfaces, shadow, px_um=px_um)
    unsupported = np.mean(confidence < CONF_FLOOR, axis=(1, 2))
    shadow_frac = np.mean(shadow, axis=1)
    roughness = _slow_axis_roughness(surfaces)
    implausible = np.zeros(surfaces.shape[0])
    checked = 0
    # Only compare published layer quantities.  The new composite PR and RPE
    # bands deliberately have no fabricated reference interval.
    for name in ("RNFL", "GCL", "IPL", "INL", "TOTAL"):
        lo, hi = reference.plausible_range(name)
        band = maps[name]
        bad = (band < lo) | (band > hi)
        implausible += np.nanmean(np.where(np.isfinite(band), bad, np.nan), axis=1)
        checked += 1
    if checked:
        implausible /= checked
    parts = {
        "unsupported": unsupported,
        "implausible": implausible,
        "shadow_frac": shadow_frac,
        "roughness": roughness,
    }
    return np.mean([_rank01(x) for x in parts.values()], axis=0), parts


def _spread_pick(score: np.ndarray, n: int, min_sep: int, exclude=()) -> np.ndarray:
    n = min(int(n), score.size)
    blocked = np.zeros(score.size, bool)
    for item in exclude:
        blocked[max(0, item - min_sep):min(score.size, item + min_sep + 1)] = True
    picked = []
    for item in np.argsort(-score):
        if len(picked) >= n:
            break
        if not blocked[item]:
            picked.append(int(item))
            blocked[max(0, item - min_sep):min(score.size, item + min_sep + 1)] = True
    # Do not silently return fewer examples if an aggressive separation is
    # impossible in a small volume.
    for item in np.argsort(-score):
        if len(picked) >= n:
            break
        if int(item) not in picked and int(item) not in exclude:
            picked.append(int(item))
    return np.array(sorted(picked), dtype=int)


def _read_images_from_output(seg_path: Path):
    """Bulk-read exactly once; never fetch B-scans one at a time."""
    with np.load(seg_path, allow_pickle=False) as data:
        source = Path(str(data["source"][0]))
    if not source.exists():
        raise FileNotFoundError(f"source volume not found: {source}")
    with ProcessedVolume(source) as volume:
        full = volume.read_volume(channel="struct")
        profile = full.mean(axis=(0, 1))
        lo, hi, _ = find_retina_band(profile)
        vitreous_at_high_index = detect_orientation(profile)
        band = full[:, :, lo:hi]
    images = np.stack([prepare_bscan(b, vitreous_at_high_index) for b in band])
    return band, images, vitreous_at_high_index


def _load_or_fresh(seg_path: Path, fresh: bool):
    with np.load(seg_path, allow_pickle=False) as data:
        names = [str(x) for x in data["surface_names"]]
        exact = names == SURFACE_NAMES
        if exact and not fresh:
            surfaces = data["surfaces"].astype(np.float32)
            confidence = (data["confidence"].astype(np.float32)
                          if "confidence" in data.files
                          else np.full(surfaces.shape, np.nan, np.float32))
            shadow = data["shadow"].astype(bool)
            scan_id = str(data["scan_id"][0])
        else:
            surfaces = confidence = shadow = None
            scan_id = str(data["scan_id"][0])
    band, images, vhi = _read_images_from_output(seg_path)
    if surfaces is None:
        if not fresh:
            raise ValueError(
                f"{seg_path.name} is not an eight-boundary output. Re-run the "
                "new batch, or use --fresh to resegment this source volume.")
        print(f"  --fresh: resegmenting {seg_path.name} with {CASCADE_VERSION}")
        surfaces, confidence, shadow, _notes = segment_volume(
            band, vhi, bscan_avg=3, refine=True, smooth_bscans=5, px_um=PX_UM,
            attract=0.05, progress=True)
    if surfaces.shape[0] != images.shape[0]:
        raise ValueError("stored B-scan count does not match its source volume")
    return scan_id, images, surfaces, confidence, shadow


def _pack_one(seg_path: Path, args, out_dir: Path, target_n: int | None = None) -> int:
    scan_id, images, surfaces, confidence, shadow = _load_or_fresh(seg_path, args.fresh)
    score, parts = _suspect_score(surfaces, confidence, shadow, PX_UM)
    n_worst = args.n if target_n is None else target_n
    worst = _spread_pick(score, n_worst, args.min_sep)
    # One median-ranked control per scan is enough to keep the first 160-item
    # pass from learning only its own failures.  Requiring two per scan would
    # silently turn a 160-item target across 32 scans into 192 labels.
    n_control = min(max(1, round(n_worst * args.control_fraction)), max(0, score.size - worst.size))
    middle = _spread_pick(-np.abs(score - np.median(score)), n_control, args.min_sep, exclude=worst)
    picked = np.unique(np.concatenate([worst, middle]))
    out = out_dir / f"{scan_id}_pack.npz"
    np.savez_compressed(
        out,
        images=images[picked].astype(np.float32),
        surfaces=surfaces[picked].astype(np.float32),
        confidence=confidence[picked].astype(np.float16),
        shadow=shadow[picked].astype(bool),
        picked=picked.astype(np.int32),
        bscan_index=picked.astype(np.int32),
        is_control=np.isin(picked, middle),
        suspect_score=score[picked].astype(np.float32),
        surface_names=np.array(SURFACE_NAMES),
        cascade_version=np.array([CASCADE_VERSION]),
        scan_id=np.array([scan_id]),
        px_um=np.array([PX_UM], np.float32),
    )
    print(f"  {scan_id}: {picked.size} B-scans ({worst.size} suspect + "
          f"{picked.size - worst.size} controls) -> {out.name}")
    for item in sorted(picked, key=lambda x: -score[x])[:5]:
        print(f"    b{item:04d} score={score[item]:.2f} "
              f"unsup={parts['unsupported'][item]:.2f} "
              f"implaus={parts['implausible'][item]:.2f}")
    return int(picked.size)


def cmd_pack(args) -> int:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.npz:
        jobs = [Path(args.npz)]
    else:
        jobs = sorted(Path(args.all).glob("*.npz"))
    if args.selection:
        with Path(args.selection).open(newline="", encoding="utf-8") as handle:
            selected_rows = list(csv.DictReader(handle))
        if args.group:
            selected_rows = [row for row in selected_rows
                             if row.get("quality_group") == args.group]
        wanted = {row["scan_id"] for row in selected_rows if row.get("scan_id")}
        filtered = []
        for path in jobs:
            try:
                with np.load(path, allow_pickle=False) as data:
                    if str(data["scan_id"][0]) in wanted:
                        filtered.append(path)
            except Exception as exc:  # noqa: BLE001
                print(f"skipping unreadable output {path.name}: {exc}")
        jobs = filtered
    if not jobs:
        print("no segmentation outputs found")
        return 1

    # --total distributes review work across scans before it adds depth to any
    # one scan, which is the useful shape for a 160-B-scan first pass.
    per_scan = args.n
    if args.total is not None:
        per_scan = max(1, args.total // len(jobs))
    written = 0
    for number, path in enumerate(jobs, 1):
        if args.total is not None:
            remaining = args.total - written
            remaining_jobs = len(jobs) - number + 1
            per_scan = max(1, int(np.ceil(remaining / remaining_jobs)))
        print(f"[{number}/{len(jobs)}] {path.name}")
        written += _pack_one(path, args, out_dir, per_scan)
    print(f"\nqueued {written} B-scans; start/resume with:")
    print(f"  python eight_surface/label_gui.py {out_dir}")
    return 0


def cmd_refit(args) -> int:
    records = L.load_labels(args.labels)
    if not records:
        print(f"no eight-boundary label files in {args.labels}")
        return 1
    usable, rejected, accepted, stale = [], 0, 0, 0
    per_surface: dict[str, list[tuple[float, float]]] = {name: [] for name in INNER_SURFACES}
    # tuple = (human relative depth, per-B-scan median correction)
    for record in records:
        if record["verdict"] == "rejected":
            rejected += 1
            continue
        if record["verdict"] != "corrected":
            accepted += 1
            continue
        if record.get("cascade_version") != CASCADE_VERSION:
            stale += 1
            continue
        idx = {name: i for i, name in enumerate(record["surface_names"])}
        ilm = record["surfaces"][idx["ILM"]]
        pr_rpe = record["surfaces"][idx["PR_RPE"]]
        span = pr_rpe - ilm
        good = (span > 40) & ~record["region_excluded"]
        if good.sum() < 20:
            continue
        usable.append(record)
        # Per A-line, not per boundary: a stroke over 40 of 512 columns is
        # evidence about 40 columns.  On a label written before per-A-line
        # provenance existed this reduces to the old whole-boundary rule, so
        # the priors refit from those files are unchanged -- see
        # eight_surface/provenance.py for the policy.
        valid = P.local_position_valid(record)
        for name in INNER_SURFACES:
            k = idx[name]
            drawn = good & valid[k]
            if drawn.sum() < 20:
                continue
            human = (record["surfaces"][k] - ilm) / span
            auto = (record["auto_surfaces"][k] - ilm) / span
            per_surface[name].append((
                float(np.median(human[drawn])),
                float(np.median((human - auto)[drawn])),
            ))
    if not usable:
        print(f"no usable corrected labels ({rejected} rejected, {accepted} accepted, {stale} stale)")
        return 1

    refit_all, refit_trusted, details = {}, {}, {}
    print(f"{len(usable)} corrected label files used; accepted files are not evidence.\n")
    print(f"  {'surface':10s} {'prior':>8s} {'human':>8s} {'delta':>8s} {'edits':>6s} {'bias':>7s}  decision")
    for name in INNER_SURFACES:
        values = per_surface[name]
        if not values:
            continue
        human = np.array([row[0] for row in values])
        correction = np.array([row[1] for row in values])
        estimate = float(np.median(human))
        total_abs = float(np.median(np.abs(correction)))
        systematic = abs(float(np.median(correction)))
        bias_share = 0.0 if total_abs <= 1e-8 else min(1.0, systematic / total_abs)
        n_edits = len(values)
        refit_all[name] = estimate
        trusted = n_edits >= args.min_edits and bias_share >= args.min_bias_share
        if trusted:
            refit_trusted[name] = estimate
        decision = ("trusted" if trusted else
                    f"hold: need {args.min_edits} edits and bias >= {args.min_bias_share:.2f}")
        print(f"  {name:10s} {RELATIVE_PRIORS[name]:8.3f} {estimate:8.3f} "
              f"{estimate - RELATIVE_PRIORS[name]:+8.3f} {n_edits:6d} "
              f"{bias_share:7.2f}  {decision}")
        details[name] = {"n_edited": n_edits, "bias_share": bias_share,
                         "median_relative_correction": float(np.median(correction))}

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "generated": dt.datetime.now().isoformat(timespec="seconds"),
        "cascade_version": CASCADE_VERSION,
        "n_corrected_labels": len(usable),
        "n_rejected": rejected,
        "n_accepted_skipped": accepted,
        "n_stale": stale,
        "min_edits": args.min_edits,
        "min_bias_share": args.min_bias_share,
        "published_priors": RELATIVE_PRIORS,
        "refit_all": refit_all,
        "refit_trusted": refit_trusted,
        "prior_overrides": refit_trusted,
        "surface_details": details,
        "note": "Only human-edited, visible, reliable boundaries outside excluded regions are evidence.",
    }, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")
    if refit_trusted:
        print("Apply only after inspecting the held-out check, e.g.:")
        print(f"  python eight_surface/batch_segment.py --priors {out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    pack = sub.add_parser("pack", help="write resumable manual-review packs")
    group = pack.add_mutually_exclusive_group(required=True)
    group.add_argument("--npz", help="one eight-boundary batch output")
    group.add_argument("--all", help="directory of eight-boundary batch outputs")
    pack.add_argument("--n", type=int, default=12, help="suspect B-scans per scan")
    pack.add_argument("--total", type=int, help="total suspect B-scans, distributed across scans")
    pack.add_argument("--control-fraction", type=float, default=0.20)
    pack.add_argument("--min-sep", type=int, default=15)
    pack.add_argument("--fresh", action="store_true", help="resegment source volumes before packing")
    pack.add_argument("--selection", help="group CSV from select_review_scans.py")
    pack.add_argument("--group", choices=("low", "medium", "high"),
                      help="with --selection, pack only one quality group")
    pack.add_argument("--out-dir", default=str(DEFAULT_REVIEW_DIR))
    pack.set_defaults(func=cmd_pack)
    refit = sub.add_parser("refit", help="estimate trusted inner-prior overrides")
    refit.add_argument("--labels", default=str(DEFAULT_LABEL_DIR))
    refit.add_argument("--out", default="../outputs/eight_surface/priors_refit.json")
    refit.add_argument("--min-edits", type=int, default=8)
    refit.add_argument("--min-bias-share", type=float, default=0.50)
    refit.set_defaults(func=cmd_refit)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
