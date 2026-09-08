#!/usr/bin/env python3
"""Run the isolated eight-boundary cascade over indexed OCT volumes.

Run from ``code`` after activating ``octa``::

    python eight_surface/batch_segment.py --limit 2
    python eight_surface/batch_segment.py

Outputs are intentionally written below ``outputs/eight_surface`` and cannot
overwrite the ten-surface batch files.  ``--priors`` accepts the trusted JSON
written by ``review.py refit`` after manual corrections are available.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
import traceback
from pathlib import Path

import numpy as np

CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR))

import batch_segment as base  # noqa: E402
from octa.volio import ProcessedVolume, VolumeReadError, find_retina_band  # noqa: E402

from eight_surface.config import CASCADE_VERSION, SURFACE_NAMES, load_priors  # noqa: E402
from eight_surface.segment import detect_orientation  # noqa: E402
from eight_surface.volume import segment_volume  # noqa: E402


PX_UM = 1.12
BSCAN_AVG = 3
ATTRACT = 0.05
ATTRACT_WARN = 0.4


def process_one(row, out_dir: Path, bscan_avg: int, attract: float,
                priors: dict[str, float], progress: bool) -> dict:
    sid = base.scan_id_for(row)
    volume_path = base.resolve_volumes_path(row)
    result = {
        "scan_id": sid, "animal": row.get("animal"), "eye": row.get("eye"),
        "day_label": row.get("day_label"), "status": "failed", "n_bscan": "",
        "n_aline": "", "elapsed_s": "", "notes_count": 0, "out_path": "",
        "out_mb": "", "error": "",
    }
    if volume_path is None:
        result["error"] = "could not resolve processedVolumes.mat from index row"
        return result

    started = time.time()
    try:
        with ProcessedVolume(volume_path) as volume:
            n_bscan, n_aline, n_depth = volume.shape
            if progress:
                print("    reading one cropped structural volume ...", flush=True)
            full = volume.read_volume(channel="struct")
            profile = full.mean(axis=(0, 1))
            lo, hi, _stale = find_retina_band(profile)
            vitreous_at_high_index = detect_orientation(profile)
            bscans = full[:, :, lo:hi]

        surfaces, confidence, shadow, notes = segment_volume(
            bscans, vitreous_at_high_index, bscan_avg=bscan_avg, refine=True,
            smooth_bscans=5, px_um=PX_UM, attract=attract, progress=progress,
            prior_overrides=priors,
        )
        out_path = out_dir / f"{sid}.npz"
        np.savez_compressed(
            out_path,
            surfaces=surfaces.astype(np.float32),
            confidence=confidence.astype(np.float16),
            shadow=shadow.astype(bool),
            surface_names=np.array(SURFACE_NAMES),
            cascade_version=np.array([CASCADE_VERSION]),
            notes=np.array(notes if notes else [""]),
            scan_id=np.array([sid]),
            source=np.array([str(volume_path)]),
            animal=np.array([row.get("animal", "")]),
            eye=np.array([row.get("eye", "")]),
            day_label=np.array([row.get("day_label", "")]),
            days_post_laser=np.array([row.get("days_post_laser", "")]),
            session_date=np.array([row.get("session_date", "")]),
            shape=np.array([n_bscan, n_aline, n_depth], np.int32),
            retina_band=np.array([lo, hi], np.int32),
            vitreous_at_high_index=np.array([vitreous_at_high_index]),
            px_um=np.array([PX_UM], np.float32),
            bscan_avg=np.array([bscan_avg], np.int32),
            attract=np.array([attract], np.float32),
            relative_priors=np.array([priors[name] for name in priors], np.float32),
            prior_names=np.array(list(priors)),
        )
        result.update({
            "status": "ok", "n_bscan": n_bscan, "n_aline": n_aline,
            "elapsed_s": round(time.time() - started, 1),
            "notes_count": len(notes), "out_path": str(out_path),
            "out_mb": round(out_path.stat().st_size / 1024**2, 2),
        })
    except VolumeReadError as exc:
        result["error"] = f"VolumeReadError: {exc}"
    except Exception:
        result["error"] = traceback.format_exc(limit=6)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", default="../outputs/scan_index.csv")
    parser.add_argument("--out-dir", default="../outputs/eight_surface/segmented")
    parser.add_argument("--animal")
    parser.add_argument("--scan-id", action="append", default=[], metavar="ID")
    parser.add_argument("--selection", help="CSV from select_review_scans.py; process its scan_id rows")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--bscan-avg", type=int, default=BSCAN_AVG)
    parser.add_argument("--attract", type=float, default=ATTRACT)
    parser.add_argument("--priors", help="trusted refit JSON from review.py")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if args.attract > ATTRACT_WARN:
        print(f"WARNING: attract={args.attract} can erase local CNV lesions.")
    priors = load_priors(args.priors)
    candidates = base.load_candidates(Path(args.index), args.animal)
    if args.scan_id:
        wanted = [text.lower() for text in args.scan_id]
        candidates = [row for row in candidates if any(
            text in base.scan_id_for(row).lower() for text in wanted)]
    if args.selection:
        with Path(args.selection).open(newline="", encoding="utf-8") as handle:
            chosen = {row["scan_id"] for row in csv.DictReader(handle) if row.get("scan_id")}
        candidates = [row for row in candidates if base.scan_id_for(row) in chosen]
        absent = chosen - {base.scan_id_for(row) for row in candidates}
        if absent:
            print(f"WARNING: {len(absent)} selected scan ID(s) were not found in scan_index.csv")
    if args.limit:
        candidates = candidates[:args.limit]
    out_dir = Path(args.out_dir)
    print(f"{len(candidates)} scan(s) match; cascade={CASCADE_VERSION}")
    if args.dry_run:
        for row in candidates:
            sid = base.scan_id_for(row)
            state = "SKIP (exists)" if (out_dir / f"{sid}.npz").exists() and not args.overwrite else "would run"
            print(f"  {sid}  {state}")
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "batch_log.csv"
    old_rows = (list(csv.DictReader(log_path.open(encoding="utf-8")))
                if log_path.exists() else [])
    fields = ["scan_id", "animal", "eye", "day_label", "status", "n_bscan",
              "n_aline", "elapsed_s", "notes_count", "out_path", "out_mb", "error"]
    ok = skipped = failed = 0
    for number, row in enumerate(candidates, 1):
        sid = base.scan_id_for(row)
        out_path = out_dir / f"{sid}.npz"
        print(f"[{number}/{len(candidates)}] {sid}", flush=True)
        if out_path.exists() and not args.overwrite:
            print("  skipped (output exists)")
            skipped += 1
            continue
        result = process_one(row, out_dir, args.bscan_avg, args.attract, priors,
                             progress=not args.quiet)
        old_rows.append(result)
        with log_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(old_rows)
        if result["status"] == "ok":
            print(f"  ok  {result['n_bscan']}x{result['n_aline']}  {result['elapsed_s']}s")
            ok += 1
        else:
            print(f"  FAILED: {result['error'].splitlines()[-1]}")
            failed += 1
    print(f"done: {ok} ok, {skipped} skipped, {failed} failed ({log_path})")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
