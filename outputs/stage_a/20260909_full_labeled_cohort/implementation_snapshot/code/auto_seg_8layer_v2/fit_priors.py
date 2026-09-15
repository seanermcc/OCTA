#!/usr/bin/env python3
"""Fit the five inner relative priors from human-drawn eight-boundary labels.

Evidence rules follow ``eight_surface/review.py refit``: only boundaries that a
human actually drew, marked visible, left reliable, and outside excluded
A-lines are used, and only from B-scans whose verdict is ``corrected``.

Two things differ from that script, both deliberate:

* The estimate is expressed against a chosen anchor pair.  With
  ``--anchors human`` the human ILM and PR_RPE define the span; with
  ``--anchors auto`` a re-segmented volume supplies them, which is what the
  cascade will actually have at run time.
* A leave-one-animal-out report is printed, because a prior fitted and scored
  on the same animals says nothing about the 16 unlabelled volumes.

Run from ``code`` with ``octa`` activated::

    python auto_seg_8layer_v2/fit_priors.py --out auto_seg_8layer_v2/priors_v2.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np

CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR))

from eight_surface import labels as L  # noqa: E402
from eight_surface.config import (  # noqa: E402
    INNER_SURFACES, RELATIVE_PRIORS, SURFACE_NAMES,
)

IDX = {name: i for i, name in enumerate(SURFACE_NAMES)}
MIN_SPAN_PX = 40.0
MIN_GOOD_ALINES = 20


def animal_of(scan_id: str) -> str:
    """Animal identity is the number only; sex letters conflict across sessions."""
    return scan_id.split("_", 1)[0]


def usable_records(label_dir) -> list[dict]:
    return [r for r in L.load_labels(label_dir) if r["verdict"] == "corrected"]


def relative_observations(records, anchors: dict | None = None):
    """Per-B-scan human relative depth for each inner surface.

    ``anchors`` maps ``(scan_id, bscan)`` to an ``[8, A-line]`` automatic
    surface array whose ILM and PR_RPE define the span.  Without it the human
    ILM and PR_RPE are used.
    """
    out: dict[str, list[tuple[str, float]]] = {n: [] for n in INNER_SURFACES}
    skipped = 0
    for record in records:
        if anchors is None:
            ilm = record["surfaces"][IDX["ILM"]]
            pr = record["surfaces"][IDX["PR_RPE"]]
        else:
            auto = anchors.get((record["scan_id"], record["bscan"]))
            if auto is None:
                skipped += 1
                continue
            ilm, pr = auto[IDX["ILM"]], auto[IDX["PR_RPE"]]
        span = np.asarray(pr, float) - np.asarray(ilm, float)
        good = (span > MIN_SPAN_PX) & ~record["region_excluded"]
        if good.sum() < MIN_GOOD_ALINES:
            skipped += 1
            continue
        for name in INNER_SURFACES:
            k = IDX[name]
            if not (record["surface_edited"][k] and record["surface_visible"][k]
                    and record["surface_reliable"][k]):
                continue
            value = (record["surfaces"][k] - ilm) / span
            out[name].append((animal_of(record["scan_id"]),
                              float(np.median(value[good]))))
    return out, skipped


def estimate(observations) -> dict[str, float]:
    """Median of per-B-scan medians, the same estimator review.py refit uses."""
    return {name: float(np.median([v for _animal, v in rows]))
            for name, rows in observations.items() if rows}


def enforce_monotone(priors: dict[str, float], min_gap: float = 0.004) -> dict[str, float]:
    """Inner priors must stay strictly ordered for validate_priors to accept."""
    out = dict(priors)
    previous = None
    for name in INNER_SURFACES:
        if name not in out:
            continue
        if previous is not None and out[name] <= previous + min_gap:
            out[name] = previous + min_gap
        previous = out[name]
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", default="../outputs/eight_surface/labels")
    parser.add_argument("--anchor-npz",
                        help="NPZ of re-segmented labelled B-scans for --anchors auto")
    parser.add_argument("--anchors", choices=("human", "auto"), default="human")
    parser.add_argument("--out", default="auto_seg_8layer_v2/priors_v2.json")
    parser.add_argument("--min-edits", type=int, default=8)
    args = parser.parse_args()

    records = usable_records(args.labels)
    if not records:
        print("no corrected eight-boundary labels")
        return 1

    anchors = None
    if args.anchors == "auto":
        if not args.anchor_npz:
            parser.error("--anchors auto needs --anchor-npz")
        with np.load(args.anchor_npz, allow_pickle=False) as data:
            anchors = {(str(s), int(b)): surf for s, b, surf in zip(
                data["scan_id"], data["bscan"], data["surfaces"].astype(float))}

    observations, skipped = relative_observations(records, anchors)
    priors = estimate(observations)
    animals = sorted({animal_of(r["scan_id"]) for r in records})

    print(f"{len(records)} corrected labels from {len(animals)} animals "
          f"({', '.join(animals)}); {skipped} skipped for anchor/A-line reasons")
    print(f"anchors: {args.anchors}\n")
    header = (f"  {'surface':10s} {'shipped':>8s} {'refit':>8s} {'delta':>8s} "
              f"{'n':>4s} {'IQR':>15s} {'LOAO spread':>12s}")
    print(header)
    details = {}
    for name in INNER_SURFACES:
        rows = observations.get(name) or []
        if len(rows) < args.min_edits:
            print(f"  {name:10s} too few drawn examples ({len(rows)}); keeping shipped value")
            priors.pop(name, None)
            continue
        values = np.array([v for _a, v in rows])
        # Leave-one-animal-out: refit without each animal in turn.  A prior that
        # swings when one animal is removed is not a dataset-wide constant.
        loao = []
        for animal in animals:
            rest = [v for a, v in rows if a != animal]
            if rest:
                loao.append(float(np.median(rest)))
        spread = (max(loao) - min(loao)) if loao else float("nan")
        print(f"  {name:10s} {RELATIVE_PRIORS[name]:8.3f} {priors[name]:8.3f} "
              f"{priors[name] - RELATIVE_PRIORS[name]:+8.3f} {len(rows):4d} "
              f"[{np.percentile(values, 25):.3f},{np.percentile(values, 75):.3f}]"
              f" {spread:12.3f}")
        details[name] = {
            "n_bscans": len(rows),
            "n_animals": len({a for a, _v in rows}),
            "iqr": [float(np.percentile(values, 25)), float(np.percentile(values, 75))],
            "leave_one_animal_out_range": [float(min(loao)), float(max(loao))],
            "leave_one_animal_out_spread": float(spread),
        }

    merged = enforce_monotone({**RELATIVE_PRIORS, **priors})
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "generated": dt.datetime.now().isoformat(timespec="seconds"),
        "anchors": args.anchors,
        "n_corrected_labels": len(records),
        "animals": animals,
        "shipped_priors": RELATIVE_PRIORS,
        "priors": merged,
        "surface_details": details,
        "note": ("Median of per-B-scan medians over human-drawn, visible, reliable "
                 "boundaries outside excluded A-lines."),
    }, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
