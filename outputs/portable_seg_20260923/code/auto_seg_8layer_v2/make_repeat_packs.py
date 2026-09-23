#!/usr/bin/env python3
"""Build a blind re-label round to measure human labelling repeatability.

"Almost exactly like the manual" has no defined target until we know how close
the labeller is to *themselves*.  This selects a representative subset of
already-corrected B-scans and rebuilds them as fresh review packs, presenting
exactly the same starting automatic lines as the first round, so the task is
identical rather than merely similar.

The second round must be written to a **different** label directory, so ground
truth cannot be overwritten::

    python eight_surface/label_gui.py ..\\outputs\\auto_seg_8layer_v2\\repeatability\\packs `
      --labels ..\\outputs\\auto_seg_8layer_v2\\repeatability\\labels

Selection is stratified over the volumes' acquisition QC group and spread over
animals, and the flagged CNV volume is forced in, because agreement on a
lesion is the number that matters most and is likely the worst.

Run from ``code`` with ``octa`` activated.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR))

from eight_surface import labels as L  # noqa: E402

from auto_seg_8layer_v2.fit_priors import animal_of  # noqa: E402


def load_groups(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["scan_id"]: row.get("quality_group", "")
                for row in csv.DictReader(handle) if row.get("scan_id")}


def cnv_scans(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["scan_id"] for row in csv.DictReader(handle)
                if row.get("scan_id") and row.get("status") == "potential_cnv"}


def choose(records, groups, cnv, n_target: int) -> list[tuple[str, int]]:
    """Spread the sample over QC group, animal and lesion status."""
    by_key = defaultdict(list)
    for record in records:
        key = (groups.get(record["scan_id"], "unknown"),
               animal_of(record["scan_id"]))
        by_key[key].append(record)
    for rows in by_key.values():
        # Prefer the B-scans that took real work; a fast one is a weak test of
        # repeatability because there was little judgement to repeat.
        rows.sort(key=lambda r: -r["seconds_active"])

    chosen: list = []
    forced = [r for r in records if r["scan_id"] in cnv]
    if forced:
        forced.sort(key=lambda r: -r["seconds_active"])
        chosen.append(forced[0])

    round_number = 0
    while len(chosen) < n_target:
        added = False
        for key in sorted(by_key):
            if len(chosen) >= n_target:
                break
            rows = by_key[key]
            if round_number < len(rows):
                candidate = rows[round_number]
                if not any(c["scan_id"] == candidate["scan_id"]
                           and c["bscan"] == candidate["bscan"] for c in chosen):
                    chosen.append(candidate)
                    added = True
        if not added:
            break
        round_number += 1
    return chosen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", default="../outputs/eight_surface/labels")
    parser.add_argument("--packs", default="../outputs/eight_surface/review")
    parser.add_argument("--groups", default="../outputs/eight_surface/qc_review_groups.csv")
    parser.add_argument("--cnv-flags", default="../outputs/eight_surface/potential_cnv_flags.csv")
    parser.add_argument("--out-dir", default="../outputs/auto_seg_8layer_v2/repeatability")
    parser.add_argument("--n", type=int, default=10)
    args = parser.parse_args()

    records = [r for r in L.load_labels(args.labels) if r["verdict"] == "corrected"]
    if not records:
        print("no corrected labels to re-measure")
        return 1
    groups = load_groups(Path(args.groups))
    chosen = choose(records, groups, cnv_scans(Path(args.cnv_flags)), args.n)

    out_dir = Path(args.out_dir)
    pack_dir = out_dir / "packs"
    pack_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "labels").mkdir(parents=True, exist_ok=True)

    wanted = defaultdict(set)
    for record in chosen:
        wanted[record["scan_id"]].add(record["bscan"])

    manifest, written = [], 0
    for scan_id, bscans in sorted(wanted.items()):
        source = Path(args.packs) / f"{scan_id}_pack.npz"
        if not source.exists():
            print(f"  no original pack for {scan_id}; skipping")
            continue
        with np.load(source, allow_pickle=False) as pack:
            index = pack["bscan_index"].astype(int)
            keep = np.array([i for i, b in enumerate(index) if int(b) in bscans], int)
            if not keep.size:
                print(f"  {scan_id}: none of {sorted(bscans)} present in its pack")
                continue
            out = pack_dir / f"{scan_id}_pack.npz"
            np.savez_compressed(
                out,
                # The starting automatic lines are copied verbatim from the
                # first round.  A different starting point would make this a
                # different task and the comparison meaningless.
                images=pack["images"][keep],
                surfaces=pack["surfaces"][keep],
                confidence=pack["confidence"][keep],
                shadow=pack["shadow"][keep],
                picked=pack["picked"][keep],
                bscan_index=index[keep].astype(np.int32),
                is_control=pack["is_control"][keep],
                suspect_score=pack["suspect_score"][keep],
                surface_names=pack["surface_names"],
                cascade_version=pack["cascade_version"],
                scan_id=pack["scan_id"],
                px_um=pack["px_um"],
            )
        written += keep.size
        for b in sorted(index[keep].astype(int)):
            first = next(r for r in records
                         if r["scan_id"] == scan_id and r["bscan"] == int(b))
            manifest.append({
                "scan_id": scan_id, "bscan": int(b),
                "quality_group": groups.get(scan_id, ""),
                "animal": animal_of(scan_id),
                "round1_seconds_active": round(first["seconds_active"], 1),
                "round1_n_strokes": first["n_strokes"],
                "round1_labelled_at": first.get("labelled_at", ""),
            })
        print(f"  {scan_id}: {keep.size} B-scan(s) -> {out.name}")

    (out_dir / "repeat_manifest.csv").write_text(
        "\n".join([",".join(manifest[0])] +
                  [",".join(str(row[k]) for k in manifest[0]) for row in manifest]),
        encoding="utf-8")
    (out_dir / "README.json").write_text(json.dumps({
        "purpose": "blind second labelling round to measure human repeatability",
        "n_bscans": written,
        "round1_label_dir": str(Path(args.labels)),
        "round2_label_dir": str(out_dir / "labels"),
        "warning": "Round 2 MUST be written to round2_label_dir. Never point the "
                   "GUI's --labels at the ground-truth directory for this round.",
    }, indent=2), encoding="utf-8")

    print(f"\n{written} B-scans queued for a blind second pass in {pack_dir}")
    print("\nRun the SECOND round with a separate label directory:\n")
    print(f"  python eight_surface/label_gui.py {pack_dir} --labels {out_dir / 'labels'}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
