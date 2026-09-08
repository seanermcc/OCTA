#!/usr/bin/env python3
"""
Build a normalised index of every OCT-A acquisition in the tree shrew dataset.

Walks the raw-data root, parses each day folder and each RAW/processed
acquisition, and writes one row per acquisition to CSV. This is the layer that
lets everything downstream address a scan by (animal, eye, day) instead of by a
3-different-spellings filename.

Usage
-----
    python index_scans.py --root "G:/OCT_TreeShrew/OCTA_RawData" \
                          --out  "G:/OCT_TreeShrew/derived/scan_index.csv"

Reads nothing but directory entries, so it takes seconds even on an external
drive and touches no image data.

Columns
-------
    animal, sex, eye, scan_no, session_date, day, day_label, timepoint_kind
    session_folder, raw_stem
    raw_path, raw_gb, processed_dir
    has_volumes, volumes_gb, has_layers, has_enface_oct, has_enface_octa,
    n_laser_spots, n_sample_bscans
    status          -> 'complete' | 'unprocessed' | 'raw_missing' | 'partial'
    scan_notes      -> parsing problems specific to THIS acquisition
    session_notes   -> parsing problems with the day folder (shared by all its scans)

Optionally supply real laser-induction dates so elapsed time can be computed
exactly instead of trusting the nominal 'D42' in a folder name:

    python index_scans.py --root ... --laser-dates laser_dates.csv

where laser_dates.csv is:

    animal,laser_date
    TS267,2025-02-19
    TS325,2025-11-20

That adds a `days_post_laser` column. Run with `--write-laser-template` to get a
starter file pre-filled with the baselines that are inferable from the folder
names themselves.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from octa.naming import (  # noqa: E402
    parse_session_folder,
    parse_scan_name,
    processed_dir_name,
    volumes_mat_name,
)

GB = 1024 ** 3

# Products written by newOCTA_processing_unbalance_batch.m for a complete run.
REQUIRED_PRODUCTS = ("volumes", "layers", "enface_oct")


def _size_gb(p: Path) -> float:
    try:
        return round(p.stat().st_size / GB, 2)
    except OSError:
        return 0.0


def scan_processed_dir(pdir: Path, raw_stem: str) -> dict:
    """Inspect a *_Processed folder and report which products are present."""
    out = {
        "processed_dir": pdir.name if pdir.is_dir() else "",
        "has_volumes": False, "volumes_gb": 0.0,
        "has_layers": False,
        "has_enface_oct": False, "has_enface_octa": False,
        "n_laser_spots": 0, "n_sample_bscans": 0,
    }
    if not pdir.is_dir():
        return out

    vol = pdir / volumes_mat_name(raw_stem)
    if vol.is_file():
        out["has_volumes"] = True
        out["volumes_gb"] = _size_gb(vol)
    else:
        # Fall back to a glob: a few folders were renamed by hand.
        cand = list(pdir.glob("*_processedVolumes.mat"))
        if cand:
            out["has_volumes"] = True
            out["volumes_gb"] = _size_gb(cand[0])

    out["has_layers"] = (pdir / "layers_refined_auto.mat").is_file()
    out["has_enface_oct"] = (pdir / "enface_OCT_mean.tiff").is_file()
    out["has_enface_octa"] = (pdir / "enface_OCTA_mean.tif").is_file()
    out["n_laser_spots"] = sum(1 for d in pdir.glob("laserSpot_*") if d.is_dir())

    ab = pdir / "Averaged_Bscans"
    if ab.is_dir():
        out["n_sample_bscans"] = sum(1 for f in ab.glob("Bscan_*.tiff"))
    return out


def _walk_scan_dirs(root: Path, max_depth: int = 3):
    """
    Yield every RAW file and every *_Processed directory under `root`.

    Descends into ordinary subfolders but never into a *_Processed directory -
    those hold outputs (laserSpot_N, Averaged_Bscans) and can contain thousands
    of files with nothing acquisition-like in them.
    """
    stack = [(root, 0)]
    while stack:
        d, depth = stack.pop()
        try:
            entries = list(d.iterdir())
        except OSError:
            continue
        for f in entries:
            if f.is_dir():
                if f.name.endswith("_Processed"):
                    yield f
                elif depth < max_depth:
                    stack.append((f, depth + 1))
            elif f.is_file() and f.suffix.upper() == ".RAW":
                yield f


def load_laser_dates(path: Path | None) -> dict[str, "date"]:
    from datetime import date
    if not path:
        return {}
    out = {}
    for r in csv.DictReader(Path(path).open(encoding="utf-8")):
        a = (r.get("animal") or "").strip().upper()
        d = (r.get("laser_date") or "").strip()
        if a and d:
            try:
                out[a] = date.fromisoformat(d)
            except ValueError:
                print(f"WARNING: bad laser_date {d!r} for {a}; expected YYYY-MM-DD",
                      file=sys.stderr)
    return out


def index_root(root: Path, laser_dates: dict | None = None) -> list[dict]:
    from datetime import date
    laser_dates = laser_dates or {}
    rows: list[dict] = []

    session_dirs = sorted(d for d in root.iterdir() if d.is_dir())
    for sdir in session_dirs:
        sess = parse_session_folder(sdir.name)

        # An acquisition is identified by either a RAW file or a _Processed dir;
        # three scans have a _Processed folder whose RAW was deleted.
        #
        # Acquisitions are NOT all at the top level of a session folder. Plenty
        # live one or two levels down in hand-made subfolders named 'analysis',
        # 'New folder', 'Reanalysis', 'TS328 re', 'other' and so on. Walking only
        # the top level silently loses them, so recurse - but stop descending
        # into a *_Processed directory, whose contents are outputs, not scans.
        #
        # Keying by stem rather than by full path is deliberate: in at least one
        # session the RAW sits in a subfolder while its _Processed folder is at
        # the top level, and keying by stem reunites them. The cost is that two
        # genuine copies of the same acquisition would collapse into one row, so
        # duplicates are counted and flagged rather than silently dropped.
        stems: dict[str, dict] = {}
        dup_notes: dict[str, list] = {}
        for f in _walk_scan_dirs(sdir, max_depth=3):
            if f.is_file() and f.suffix.upper() == ".RAW":
                slot = stems.setdefault(f.stem, {})
                if "raw" in slot:
                    dup_notes.setdefault(f.stem, []).append(
                        f"duplicate RAW also at {f.parent.name!r}")
                else:
                    slot["raw"] = f
            elif f.is_dir() and f.name.endswith("_Processed"):
                stem = f.name[: -len("_Processed")]
                slot = stems.setdefault(stem, {})
                if "proc" in slot:
                    dup_notes.setdefault(stem, []).append(
                        f"duplicate _Processed also at {f.parent.name!r}")
                else:
                    slot["proc"] = f

        for stem in sorted(stems):
            raw = stems[stem].get("raw")
            proc = stems[stem].get("proc")
            anchor = raw.parent if raw is not None else proc.parent
            try:
                subpath = str(anchor.relative_to(sdir))
            except ValueError:
                subpath = ""
            if subpath == ".":
                subpath = ""
            si = parse_scan_name(stem)

            animal = si.animal or "__unnamed__"
            tp = sess.timepoint_for(animal)
            if animal == "__unnamed__" and si.animal is None:
                si.needs_review.append("animal not in filename or folder")

            prod = scan_processed_dir(proc if proc else Path("/nonexistent"), stem)

            if raw is None:
                status = "raw_missing"
            elif not prod["processed_dir"]:
                status = "unprocessed"
            elif all(prod[f"has_{k}"] for k in REQUIRED_PRODUCTS):
                status = "complete"
            else:
                status = "partial"

            scan_notes = list(si.needs_review) + dup_notes.get(stem, [])
            if raw is not None and proc is not None and raw.parent != proc.parent:
                scan_notes.append(
                    f"RAW in {raw.parent.name!r} but _Processed in {proc.parent.name!r}")
            if tp.kind == "unknown":
                scan_notes.append("timepoint unknown")

            # Exact elapsed days, when a real laser date is known for this animal.
            days_post = ""
            day_drift = ""
            if si.animal and si.animal.upper() in laser_dates and sess.date:
                ld = laser_dates[si.animal.upper()]
                days_post = (date.fromisoformat(sess.date) - ld).days
                if tp.days is not None:
                    day_drift = days_post - tp.days
                    if abs(day_drift) > 3:
                        scan_notes.append(
                            f"nominal {tp.label} but {days_post} d post-laser "
                            f"({day_drift:+d})")

            rows.append({
                "animal": si.animal or "",
                "sex": si.sex_letter or "",
                "eye": si.eye or "",
                "scan_no": si.scan_no if si.scan_no is not None else "",
                "session_date": sess.date or "",
                "day": tp.days if tp.days is not None else "",
                "days_post_laser": days_post,
                "day_drift": day_drift,
                "day_label": tp.label,
                "timepoint_kind": tp.kind,
                "session_folder": sdir.name,
                "subfolder": subpath,
                "raw_stem": stem,
                "raw_path": str(raw) if raw else "",
                "raw_gb": _size_gb(raw) if raw else 0.0,
                "acq_time": si.acq_time or "",
                "n_fast": si.n_fast or "",
                "n_slow": si.n_slow or "",
                "x_drive_um": si.x_drive_um or "",
                "y_drive_um": si.y_drive_um or "",
                "status": status,
                **prod,
                "scan_notes": "; ".join(dict.fromkeys(scan_notes)),
                "session_notes": "; ".join(dict.fromkeys(sess.needs_review)),
            })
    return rows


FIELDS = [
    "animal", "sex", "eye", "scan_no", "session_date", "day",
    "days_post_laser", "day_drift", "day_label",
    "timepoint_kind", "session_folder", "subfolder", "raw_stem", "raw_path", "raw_gb",
    "acq_time", "n_fast", "n_slow", "x_drive_um", "y_drive_um",
    "status", "processed_dir", "has_volumes", "volumes_gb", "has_layers",
    "has_enface_oct", "has_enface_octa", "n_laser_spots", "n_sample_bscans",
    "scan_notes", "session_notes",
]


def write_laser_template(rows: list[dict], out: Path) -> None:
    """
    Emit a starter laser_dates.csv, pre-filled where a baseline session exists.

    A baseline is a session the folder itself calls day 0 -- 'DAY0', 'CNV D0',
    'LASER DAY', or 'before laser'. Animals with no such session are listed with
    a blank date for you to fill in from lab records.
    """
    baselines: dict[str, str] = {}
    animals: set[str] = set()
    for r in rows:
        a = r["animal"]
        if not a:
            continue
        animals.add(a)
        if r["timepoint_kind"] in ("laser_day", "pre_laser") or str(r["day"]) == "0":
            baselines.setdefault(a, r["session_date"])

    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["animal", "laser_date", "source"])
        for a in sorted(animals):
            if a in baselines:
                w.writerow([a, baselines[a], "inferred from a day-0 session folder - please confirm"])
            else:
                w.writerow([a, "", "NO day-0 session in the dataset - fill in from lab records"])
    print(f"wrote laser-date template {out}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, help="OCTA_RawData directory")
    ap.add_argument("--out", default=None, help="output CSV (default: <root>/../derived/scan_index.csv)")
    ap.add_argument("--laser-dates", default=None,
                    help="CSV with animal,laser_date columns; adds exact days_post_laser")
    ap.add_argument("--write-laser-template", action="store_true",
                    help="also write a starter laser_dates.csv next to the index")
    args = ap.parse_args()

    root = Path(args.root)
    if not root.is_dir():
        print(f"ERROR: {root} is not a directory", file=sys.stderr)
        return 2

    out = Path(args.out) if args.out else root.parent / "derived" / "scan_index.csv"
    out.parent.mkdir(parents=True, exist_ok=True)

    laser = load_laser_dates(Path(args.laser_dates) if args.laser_dates else None)
    rows = index_root(root, laser)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    if args.write_laser_template:
        write_laser_template(rows, out.parent / "laser_dates.csv")

    # ---- summary to the console -----------------------------------------
    from collections import Counter
    st = Counter(r["status"] for r in rows)
    animals = sorted({r["animal"] for r in rows if r["animal"]})
    tot_raw = sum(r["raw_gb"] for r in rows)
    tot_vol = sum(r["volumes_gb"] for r in rows)
    review = [r for r in rows if r["scan_notes"]]
    sess_notes = {r["session_folder"]: r["session_notes"]
                  for r in rows if r["session_notes"]}

    print(f"indexed {len(rows)} acquisitions across "
          f"{len({r['session_folder'] for r in rows})} sessions")
    print(f"animals ({len(animals)}): {', '.join(animals)}")
    for k in ("complete", "partial", "unprocessed", "raw_missing"):
        if st[k]:
            print(f"  {k:12s} {st[k]:4d}")
    print(f"RAW on disk      {tot_raw:8.1f} GB")
    print(f"processedVolumes {tot_vol:8.1f} GB")
    if sess_notes:
        print(f"\n{len(sess_notes)} session folder(s) with naming issues:")
        for folder, note in sorted(sess_notes.items()):
            print(f"  {folder}\n      -> {note}")
    if review:
        print(f"\n{len(review)} acquisition(s) flagged:")
        for r in review[:25]:
            print(f"  {r['animal']} {r['eye']} {r['day_label']} "
                  f"({r['session_date']})  -> {r['scan_notes']}")
        if len(review) > 25:
            print(f"  ... and {len(review) - 25} more (see the CSV)")
    if not sess_notes and not review:
        print("\nno naming or timepoint issues flagged")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
