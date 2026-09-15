#!/usr/bin/env python3
"""Score the blind second labelling round against the first.

This produces the number that defines the training target: how close the
labeller is to themselves.  No model can be expected to beat it, and a model
that reaches it is finished.

Only A-lines that **neither** round excluded are compared, and only surfaces
that both rounds drew, marked visible and left reliable.  A surface one round
called invisible and the other drew is reported separately as a disagreement
about visibility, which is a different failure from a disagreement about depth.

Run from ``code`` with ``octa`` activated::

    python auto_seg_8layer_v2/score_repeatability.py
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR))

from eight_surface import labels as L  # noqa: E402
from eight_surface.config import LAYER_DEFS, SURFACE_NAMES  # noqa: E402

IDX = {name: i for i, name in enumerate(SURFACE_NAMES)}


def drawn(record, k: int) -> bool:
    return bool(record["surface_edited"][k] and record["surface_visible"][k]
                and record["surface_reliable"][k])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--round1", default="../outputs/eight_surface/labels")
    parser.add_argument("--round2",
                        default="../outputs/auto_seg_8layer_v2/repeatability/labels")
    parser.add_argument("--out",
                        default="../outputs/auto_seg_8layer_v2/repeatability/repeatability.json")
    args = parser.parse_args()

    first = {(r["scan_id"], r["bscan"]): r for r in L.load_labels(args.round1)}
    second = L.load_labels(args.round2)
    if not second:
        print(f"no second-round labels yet in {args.round2}")
        print("Run the blind round first:")
        print("  python eight_surface/label_gui.py "
              "..\\outputs\\auto_seg_8layer_v2\\repeatability\\packs "
              "--labels ..\\outputs\\auto_seg_8layer_v2\\repeatability\\labels")
        return 1

    per_surface: dict[str, list[float]] = {n: [] for n in SURFACE_NAMES}
    visibility_disagreements, verdict_flips, pairs = [], [], 0
    for r2 in second:
        key = (r2["scan_id"], r2["bscan"])
        r1 = first.get(key)
        if r1 is None:
            print(f"  {key} has no first-round label; skipping")
            continue
        pairs += 1
        if r1["verdict"] != r2["verdict"]:
            verdict_flips.append({"scan_id": key[0], "bscan": key[1],
                                  "round1": r1["verdict"], "round2": r2["verdict"]})
        if r1["verdict"] != "corrected" or r2["verdict"] != "corrected":
            continue
        good = ~(r1["region_excluded"] | r2["region_excluded"])
        if good.sum() < 20:
            continue
        for name in SURFACE_NAMES:
            k = IDX[name]
            if drawn(r1, k) != drawn(r2, k):
                visibility_disagreements.append({
                    "scan_id": key[0], "bscan": key[1], "surface": name,
                    "round1_drawn": drawn(r1, k), "round2_drawn": drawn(r2, k)})
                continue
            if not drawn(r1, k):
                continue
            delta = (r2["surfaces"][k] - r1["surfaces"][k])[good] * r1["px_um"]
            per_surface[name].append(float(np.median(np.abs(delta))))

    print(f"{pairs} B-scans labelled twice\n")
    print(f"  {'surface':10s} {'median um':>10s} {'p90 um':>8s} {'n':>4s}")
    summary = {}
    for name in SURFACE_NAMES:
        values = np.array(per_surface[name])
        if not values.size:
            continue
        summary[name] = {
            "median_abs_um": float(np.median(values)),
            "p90_abs_um": float(np.percentile(values, 90)),
            "n_bscans": int(values.size),
        }
        print(f"  {name:10s} {np.median(values):10.1f} "
              f"{np.percentile(values, 90):8.1f} {values.size:4d}")

    # Layer thickness repeatability matters more than boundary repeatability for
    # the biology: two boundaries can both shift and leave the layer unchanged.
    layer_summary = {}
    print(f"\n  {'layer':14s} {'median um':>10s}  (thickness, round2 - round1)")
    for name, top, bottom in LAYER_DEFS:
        values = []
        for r2 in second:
            r1 = first.get((r2["scan_id"], r2["bscan"]))
            if r1 is None or r1["verdict"] != "corrected" or r2["verdict"] != "corrected":
                continue
            if not (drawn(r1, IDX[top]) and drawn(r1, IDX[bottom])
                    and drawn(r2, IDX[top]) and drawn(r2, IDX[bottom])):
                continue
            good = ~(r1["region_excluded"] | r2["region_excluded"])
            if good.sum() < 20:
                continue
            t1 = (r1["surfaces"][IDX[bottom]] - r1["surfaces"][IDX[top]])[good]
            t2 = (r2["surfaces"][IDX[bottom]] - r2["surfaces"][IDX[top]])[good]
            values.append(float(np.median(t2 - t1) * r1["px_um"]))
        if values:
            layer_summary[name] = {
                "median_signed_um": float(np.median(values)),
                "median_abs_um": float(np.median(np.abs(values))),
                "n_bscans": len(values),
            }
            print(f"  {name:14s} {np.median(np.abs(values)):10.1f}")

    if visibility_disagreements:
        print(f"\n  {len(visibility_disagreements)} visibility/reliability "
              f"disagreements (a different kind of error from a depth error):")
        for row in visibility_disagreements[:10]:
            print(f"    {row['scan_id']} b{row['bscan']:04d} {row['surface']}: "
                  f"round1 drawn={row['round1_drawn']} round2 drawn={row['round2_drawn']}")
    if verdict_flips:
        print(f"\n  {len(verdict_flips)} verdict changes between rounds:")
        for row in verdict_flips:
            print(f"    {row['scan_id']} b{row['bscan']:04d}: "
                  f"{row['round1']} -> {row['round2']}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "n_bscans_labelled_twice": pairs,
        "surface_repeatability_um": summary,
        "layer_thickness_repeatability_um": layer_summary,
        "visibility_disagreements": visibility_disagreements,
        "verdict_flips": verdict_flips,
        "note": ("Human-vs-self agreement. This is the floor for any automatic "
                 "method: a model at this level is as good as the ground truth "
                 "it was trained on."),
    }, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
