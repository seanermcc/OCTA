#!/usr/bin/env python3
"""
Run the validated segmentation pipeline over every analysable scan in
`scan_index.csv` and save a compact per-scan surface file.

This is stage-2 of the project: `octa/segment.py` and `octa/volume.py` are
already measured and validated (see README.md), but until now they had only
ever been run in memory against one WT sample and one CNV sample to produce
figures. Nothing was persisted. This script is what actually produces analysis
output for the 314 scans that have a `processedVolumes.mat`.

What it does, per scan
-----------------------
1. Resolve the scan's `processedVolumes.mat` from its scan_index.csv row.
2. Read every B-scan at full A-line resolution, cropped to the detected
   retina+choroid band (NOT the half-stride "slab" used for dev samples --
   that was a size compromise for the earlier develop-on-a-sample-file step;
   the real analysis output should be full resolution).
3. Detect orientation fresh with `detect_orientation()`. Never trust a stored
   `vitreous_at_high_index` flag from anywhere else -- see CLAUDE.md.
4. `segment_volume(bscan_avg=3, refine=True, attract=0.05)` -- the settings
   chosen by measurement in the README. Do not change these without rerunning
   the sweep that justified them.
5. Save surfaces + shadow mask + notes + metadata to a ~5-10 MB .npz per scan.
   Thickness maps are NOT stored -- they're a cheap deterministic function of
   surfaces (`octa.volume.thickness_maps`), so storing them too would just
   double the file size for nothing.

Resumable: a scan whose output file already exists is skipped unless
--overwrite. Failures are logged per-scan (traceback in the log CSV) and do
not stop the batch -- with 314 real scans across three years of acquisition
settings, at least one will not fit the shape this pipeline assumes.

Usage
-----
    # see what would run, without touching any data
    python batch_segment.py --dry-run

    # smoke-test on a couple of real scans before committing to all 314
    python batch_segment.py --limit 2

    # the real run
    python batch_segment.py
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
import traceback
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from octa.volio import ProcessedVolume, find_retina_band, VolumeReadError  # noqa: E402
from octa.segment import (  # noqa: E402
    detect_orientation, SURFACE_NAMES, N_SURFACES, CASCADE_VERSION,
)
from octa.volume import segment_volume  # noqa: E402

PX_UM = 1.12
BSCAN_AVG = 3          # measured -- see README "Settings chosen by measurement"
ATTRACT = 0.05         # measured -- do not raise above ~0.4, see CLAUDE.md
ATTRACT_WARN = 0.4


def resolve_volumes_path(row: dict) -> Path | None:
    """
    Find this row's processedVolumes.mat.

    Usually the `_Processed` dir sits next to the .RAW file. But some rows'
    own `scan_notes` flag a mismatch: the .RAW lives in a hand-made subfolder
    (`New folder`, `TS328 re`, ...) while its `_Processed` output was written
    a level up, in the session folder itself (index_scans.py records this
    verbatim, e.g. "RAW in 'New folder' but _Processed in '<session>'"). So
    check the RAW's own folder first, then its parent, before giving up.
    """
    raw_path = row.get("raw_path")
    pdir_name = row.get("processed_dir")
    if not raw_path or not pdir_name:
        return None
    raw_path = Path(raw_path)
    roots = [raw_path.parent]
    if raw_path.parent.parent not in roots:
        roots.append(raw_path.parent.parent)
    for root in roots:
        pdir = root / pdir_name
        if pdir.is_dir():
            hits = list(pdir.glob("*_processedVolumes.mat"))
            if hits:
                return hits[0]
    return None


def scan_id_for(row: dict) -> str:
    """
    Unique, traceable id for one acquisition.

    scan_no alone is NOT enough to disambiguate: 4 of the 314 candidates are
    genuine repeat/redo acquisitions with the same (animal, eye, date,
    day_label, scan_no) but a different acq_time, living in different
    hand-made subfolders (e.g. `TS328 re`, `New folder` next to the original).
    Without acq_time in the id, the second one silently collides with the
    first -- either overwriting its output or, with --resume behaviour,
    getting skipped as "already done" and dropped entirely.
    """
    animal = row.get("animal", "UNK")
    eye = row.get("eye", "UN")
    day_label = (row.get("day_label") or "Dx").replace(" ", "")
    date = (row.get("session_date") or "nodate")
    scan_no = row.get("scan_no") or "0"
    acq_time = (row.get("acq_time") or "").replace(":", "")
    return f"{animal}_{eye}_{date}_{day_label}_s{int(scan_no):02d}_{acq_time}"


def load_candidates(index_csv: Path, animal_filter: str | None) -> list[dict]:
    rows = list(csv.DictReader(index_csv.open(encoding="utf-8")))
    cand = [r for r in rows if r.get("has_volumes") == "True"]
    if animal_filter:
        cand = [r for r in cand if r["animal"].upper() == animal_filter.upper()]
    return cand


def process_one(row: dict, out_dir: Path, bscan_avg: int, attract: float,
                progress: bool) -> dict:
    sid = scan_id_for(row)
    vpath = resolve_volumes_path(row)
    result = {"scan_id": sid, "animal": row.get("animal"), "eye": row.get("eye"),
              "day_label": row.get("day_label"), "status": "failed",
              "n_bscan": "", "n_aline": "", "elapsed_s": "", "notes_count": 0,
              "out_path": "", "out_mb": "", "error": ""}

    if vpath is None:
        result["error"] = "could not resolve processedVolumes.mat from index row"
        return result

    t0 = time.time()
    try:
        with ProcessedVolume(vpath) as v:
            nb, na, nd = v.shape
            if progress:
                print(f"    reading volume (one bulk read, not per-B-scan -- "
                      f"see octa/volio.py) ...", flush=True)
            # One bulk read for the whole scan. Looping v.bscan(i) 512 times
            # measured at ~78 minutes for a single volume, because this
            # dataset's HDF5 chunks span the full B-scan axis: a "cheap"
            # single-B-scan slice decompresses the exact same chunks as
            # reading everything. One bulk call measured at ~13s for the
            # same data -- do the profile/band detection from the same
            # in-memory array instead of triggering a second full read.
            full = v.read_volume(channel="struct")   # [nb, na, nd] float32
            profile = full.mean(axis=(0, 1))
            lo, hi, _stale_flag = find_retina_band(profile)
            vitreous_at_high_index = detect_orientation(profile)
            bscans = full[:, :, lo:hi]

        surfaces, confidence, shadow, notes = segment_volume(
            bscans, vitreous_at_high_index,
            bscan_avg=bscan_avg, refine=True, smooth_bscans=5,
            px_um=PX_UM, attract=attract, progress=progress,
        )

        out_path = out_dir / f"{sid}.npz"
        np.savez_compressed(
            out_path,
            surfaces=surfaces.astype(np.float32),
            # Stored as float16: this is a per-A-line diagnostic used for
            # thresholding and ranking, not a measurement, and float32 would
            # double the size of every output file to record precision the
            # number does not carry. Confidence was previously computed and
            # discarded entirely, which left no way to tell a surface the image
            # found from one the prior invented.
            confidence=confidence.astype(np.float16),
            shadow=shadow.astype(bool),
            surface_names=np.array(SURFACE_NAMES),
            # Which cascade wrote this. Consumers compare against the current
            # value rather than counting surfaces, so a file holding a superset
            # of today's surfaces can still be scored on the ones it shares.
            cascade_version=np.array([CASCADE_VERSION]),
            notes=np.array(notes if notes else [""]),
            scan_id=np.array([sid]),
            source=np.array([str(vpath)]),
            animal=np.array([row.get("animal", "")]),
            eye=np.array([row.get("eye", "")]),
            day_label=np.array([row.get("day_label", "")]),
            days_post_laser=np.array([row.get("days_post_laser", "")]),
            session_date=np.array([row.get("session_date", "")]),
            shape=np.array([nb, na, nd], dtype=np.int32),
            retina_band=np.array([lo, hi], dtype=np.int32),
            vitreous_at_high_index=np.array([vitreous_at_high_index]),
            px_um=np.array([PX_UM], dtype=np.float32),
            bscan_avg=np.array([bscan_avg], dtype=np.int32),
            attract=np.array([attract], dtype=np.float32),
        )

        result.update({
            "status": "ok", "n_bscan": nb, "n_aline": na,
            "elapsed_s": round(time.time() - t0, 1),
            "notes_count": len(notes),
            "out_path": str(out_path),
            "out_mb": round(out_path.stat().st_size / 1024**2, 2),
        })
    except VolumeReadError as e:
        result["error"] = f"VolumeReadError: {e}"
    except Exception:
        result["error"] = traceback.format_exc(limit=6)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--index", default="../outputs/scan_index.csv")
    ap.add_argument("--out-dir", default="../outputs/segmented")
    ap.add_argument("--animal", default=None, help="restrict to one animal, e.g. TS267")
    ap.add_argument("--scan-id", action="append", default=None, metavar="ID",
                    help="restrict to scans whose id contains ID (repeatable). "
                         "A substring, not an exact match, so a partial id "
                         "like TS267_OD_2025-04-16 is enough to pick one scan "
                         "without typing its acquisition time.")
    ap.add_argument("--limit", type=int, default=None,
                    help="process at most N scans (for smoke-testing)")
    ap.add_argument("--overwrite", action="store_true",
                    help="reprocess scans that already have output")
    ap.add_argument("--dry-run", action="store_true",
                    help="print what would run, touch no volume data")
    ap.add_argument("--bscan-avg", type=int, default=BSCAN_AVG)
    ap.add_argument("--attract", type=float, default=ATTRACT)
    ap.add_argument("--quiet", action="store_true", help="suppress per-scan progress")
    args = ap.parse_args()

    if args.attract > ATTRACT_WARN:
        print(f"WARNING: attract={args.attract} is above ~{ATTRACT_WARN}, where slow-axis "
              f"refinement degenerates into a median filter and erases CNV lesions "
              f"(see CLAUDE.md). Proceeding anyway since you asked explicitly.")

    index_csv = Path(args.index)
    out_dir = Path(args.out_dir)
    candidates = load_candidates(index_csv, args.animal)
    if args.scan_id:
        wanted = [s.lower() for s in args.scan_id]
        candidates = [r for r in candidates
                      if any(w in scan_id_for(r).lower() for w in wanted)]
        for w in args.scan_id:
            if not any(w.lower() in scan_id_for(r).lower() for r in candidates):
                print(f"WARNING: --scan-id {w!r} matched nothing")
    if args.limit:
        candidates = candidates[:args.limit]

    print(f"{len(candidates)} scan(s) match (has_volumes=True"
          f"{f', animal={args.animal}' if args.animal else ''}"
          f"{f', scan-id~{args.scan_id}' if args.scan_id else ''})")

    if args.dry_run:
        for r in candidates:
            sid = scan_id_for(r)
            vpath = resolve_volumes_path(r)
            done = (out_dir / f"{sid}.npz").exists()
            flag = "SKIP (exists)" if done and not args.overwrite else ("MISSING .mat" if vpath is None else "would run")
            print(f"  {sid:40s} {flag}")
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "batch_log.csv"
    log_rows = []
    if log_path.exists():
        log_rows = list(csv.DictReader(log_path.open(encoding="utf-8")))

    fieldnames = ["scan_id", "animal", "eye", "day_label", "status", "n_bscan",
                 "n_aline", "elapsed_s", "notes_count", "out_path", "out_mb", "error"]

    n_ok = n_skip = n_fail = 0
    for i, row in enumerate(candidates, 1):
        sid = scan_id_for(row)
        out_path = out_dir / f"{sid}.npz"
        print(f"[{i}/{len(candidates)}] {sid}", flush=True)

        if out_path.exists() and not args.overwrite:
            print("  skipped (output exists)")
            n_skip += 1
            continue

        result = process_one(row, out_dir, args.bscan_avg, args.attract,
                             progress=not args.quiet)
        log_rows.append(result)

        # flush the log after every scan -- this is a multi-hour disk-bound
        # run and a crash on scan 250 should not lose scans 1-249's log.
        with log_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(log_rows)

        if result["status"] == "ok":
            print(f"  ok  {result['n_bscan']}x{result['n_aline']}  "
                  f"{result['elapsed_s']}s  {result['out_mb']} MB  "
                  f"{result['notes_count']} note(s)")
            n_ok += 1
        else:
            print(f"  FAILED: {result['error'].splitlines()[-1] if result['error'] else 'unknown'}")
            n_fail += 1

    print(f"\ndone: {n_ok} ok, {n_skip} skipped, {n_fail} failed "
          f"(log: {log_path})")
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
