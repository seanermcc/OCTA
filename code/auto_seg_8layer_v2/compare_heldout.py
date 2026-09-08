#!/usr/bin/env python3
"""Compare shipped and revision-2 segmentation on the unlabelled volumes.

There is no human ground truth on the held-out 16, so the only check available
is anatomical: how far each cascade's median layer thickness sits outside the
published tree shrew interval (eNeuro 2024, central-to-peripheral union).

This is a weaker test than the labelled comparison and is treated as such.
Agreeing with a normative table is not the same as being right on any one
B-scan, and CNV eyes are expected to leave the interval in places.  It is
reported because it is the one measurement on these volumes that does not
reuse the data the priors were fitted from.

Run from ``code`` with ``octa`` activated::

    python auto_seg_8layer_v2/compare_heldout.py
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR))

from octa import reference  # noqa: E402

from eight_surface.config import LAYER_DEFS  # noqa: E402
from eight_surface.volume import thickness_maps  # noqa: E402

PX_UM = 1.12
# Only layers the paper actually reports.  The composite PHOTORECEPTOR and the
# RPE band have no published interval and get no invented one.
CHECKED = ["RNFL", "GCL", "IPL", "INL", "TOTAL"]


def medians(path: Path) -> dict[str, float]:
    with np.load(path, allow_pickle=False) as data:
        surfaces = data["surfaces"].astype(np.float32)
        shadow = data["shadow"].astype(bool)
    maps = thickness_maps(surfaces, shadow, px_um=PX_UM)
    return {name: (float(np.nanmedian(maps[name]))
                   if np.isfinite(maps[name]).any() else float("nan"))
            for name, _t, _b in LAYER_DEFS}


def outside(name: str, value: float) -> float:
    """Micrometres outside the published plausible interval; 0 if inside.

    ``plausible_range`` is the union of both retinal regimes widened by their
    SDs, so it is a screen for nonsense, not a measure of accuracy.  Almost
    anything ordinary passes it -- see ``distance_to_published``.
    """
    lo, hi = reference.plausible_range(name)
    if not np.isfinite(value):
        return float("nan")
    return float(max(0.0, lo - value, value - hi))


def distance_to_published(name: str, value: float) -> float:
    """Distance to the nearer of the two published point values.

    Our scans usually cannot be assigned to the central or peripheral regime,
    so the nearer of the two is the fairest single number.
    """
    ref = reference.TREE_SHREW.get(name)
    if ref is None or not np.isfinite(value):
        return float("nan")
    return float(min(abs(value - ref.central), abs(value - ref.peripheral)))


def human_medians(label_dir: Path) -> dict[str, float]:
    """Median hand-drawn layer thickness over the corrected labels.

    This is the better yardstick of the two: same instrument, same animals,
    same drawing convention.  It says nothing about any individual held-out
    B-scan -- only whether the automatic output has the same central tendency
    as the boundaries a human drew.
    """
    from eight_surface import labels as L
    from eight_surface.config import SURFACE_NAMES

    idx = {name: i for i, name in enumerate(SURFACE_NAMES)}
    records = [r for r in L.load_labels(label_dir) if r["verdict"] == "corrected"]
    out = {}
    for name, top, bottom in LAYER_DEFS:
        values = []
        for record in records:
            if not (record["surface_reliable"][idx[top]]
                    and record["surface_reliable"][idx[bottom]]):
                continue
            good = ~record["region_excluded"]
            values.append(np.median(
                (record["surfaces"][idx[bottom]] - record["surfaces"][idx[top]])[good])
                * record["px_um"])
        if values:
            out[name] = float(np.median(values))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old", default="../outputs/eight_surface/segmented")
    parser.add_argument("--new", default="../outputs/auto_seg_8layer_v2/segmented")
    parser.add_argument("--labels", default="../outputs/eight_surface/labels")
    parser.add_argument("--out", default="../outputs/auto_seg_8layer_v2/qc/heldout_vs_reference.csv")
    args = parser.parse_args()
    human = human_medians(Path(args.labels))

    new_paths = {p.stem: p for p in Path(args.new).glob("*.npz")}
    old_dir = Path(args.old)
    rows = []
    for scan_id in sorted(new_paths):
        old_path = old_dir / f"{scan_id}.npz"
        if not old_path.exists():
            print(f"  no shipped output for {scan_id}; skipping")
            continue
        old, new = medians(old_path), medians(new_paths[scan_id])
        row = {"scan_id": scan_id}
        for name in CHECKED:
            row[f"{name}_old_um"] = f"{old[name]:.1f}"
            row[f"{name}_new_um"] = f"{new[name]:.1f}"
            row[f"{name}_old_outside_um"] = f"{outside(name, old[name]):.1f}"
            row[f"{name}_new_outside_um"] = f"{outside(name, new[name]):.1f}"
        row["total_outside_old_um"] = f"{sum(outside(n, old[n]) for n in CHECKED):.1f}"
        row["total_outside_new_um"] = f"{sum(outside(n, new[n]) for n in CHECKED):.1f}"
        rows.append(row)
    if not rows:
        print("nothing to compare")
        return 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(f"{len(rows)} held-out volumes; median over volumes of the "
          f"per-volume median layer thickness\n")
    print(f"  {'layer':8s} {'shipped':>8s} {'v2':>8s} {'hand':>8s} "
          f"{'paper C/P':>13s} | {'d(paper)':>18s} | {'d(hand)':>16s}")
    print(f"  {'':8s} {'um':>8s} {'um':>8s} {'um':>8s} {'um':>13s} | "
          f"{'shipped':>8s} {'v2':>8s} | {'shipped':>7s} {'v2':>7s}")
    for name in CHECKED:
        ref = reference.TREE_SHREW[name]
        old_v = np.median([float(r[f"{name}_old_um"]) for r in rows])
        new_v = np.median([float(r[f"{name}_new_um"]) for r in rows])
        hand = human.get(name, float("nan"))
        print(f"  {name:8s} {old_v:8.1f} {new_v:8.1f} {hand:8.1f} "
              f"{ref.central:6.1f}/{ref.peripheral:-6.1f} | "
              f"{distance_to_published(name, old_v):8.1f} "
              f"{distance_to_published(name, new_v):8.1f} | "
              f"{abs(old_v - hand):7.1f} {abs(new_v - hand):7.1f}")
    old_t = np.array([float(r["total_outside_old_um"]) for r in rows])
    new_t = np.array([float(r["total_outside_new_um"]) for r in rows])
    print(f"\n  volumes with every checked layer inside the published plausible range:"
          f"  shipped {int((old_t == 0).sum())}/{len(rows)}, "
          f"v2 {int((new_t == 0).sum())}/{len(rows)}")
    print("  (that range is a nonsense screen, not an accuracy measure -- read "
          "the d(hand) columns)")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
