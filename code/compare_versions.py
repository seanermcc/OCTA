#!/usr/bin/env python3
"""
Before/after table for a segmentation change, scored against the paper.

`qc_vs_reference.py` answers "is this one output any good". This answers the
different question you have after changing a prior or a cascade: "did that
change help, and where". It scores two directories of `batch_segment.py`
output with the same code `qc_vs_reference.py` uses, pairs them by filename,
and prints the median thickness of every layer side by side with the published
tree shrew value.

The `->paper` column is what to read: distance from the published value,
before and after, in micrometres. A layer that moved a long way while its
distance stayed flat has not improved -- it has moved.

Usage
-----
    python compare_versions.py --before ../outputs/segment_v2 \
                               --after  ../outputs/segment_v3
    python compare_versions.py --before ... --after ... --csv out.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from qc_vs_reference import load_segmented, score, StaleSegmentation  # noqa: E402
from octa import reference as ref  # noqa: E402

# The layers the eNeuro 2024 paper actually gives a number for, in anatomical
# order. Layers with no published value are still segmented and still matter
# (per Xiaorong) -- they just cannot be scored this way, so they are printed
# without a distance rather than dropped.
ORDER = ["RNFL", "GCL", "IPL", "GCL_IPL", "INL", "OPL", "ONL", "IS", "OS",
         "RPE_BM", "TOTAL"]


def medians(path: Path) -> tuple[dict, str]:
    seg = load_segmented(path)
    rows, _support = score(seg)
    # load_segmented deliberately keeps only what scoring needs, so read the
    # cascade stamp straight off the file rather than widening its contract.
    d = np.load(path, allow_pickle=False)
    ver = str(d["cascade_version"][0]) if "cascade_version" in d else "?"
    return {r["layer"]: r for r in rows}, ver


def paper_distance(layer: str, med: float) -> float | None:
    """Distance to the nearer of the paper's central and peripheral values.

    Nearer of the two rather than one of them, because our ~1460 µm field
    usually cannot be assigned to either regime -- the ONH is outside it in
    many scans -- and picking one would manufacture an error that is really
    just an unknown eccentricity.
    """
    r = ref.TREE_SHREW.get(layer)
    if r is None:
        return None
    return min(abs(med - r.central), abs(med - r.peripheral))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--csv", default=None)
    args = ap.parse_args()

    bdir, adir = Path(args.before), Path(args.after)
    pairs = [(bdir / p.name, p) for p in sorted(adir.glob("*.npz"))
             if (bdir / p.name).exists()]
    orphans = [p.name for p in sorted(adir.glob("*.npz"))
               if not (bdir / p.name).exists()]
    if not pairs:
        print(f"no scans present in both {bdir} and {adir}")
        return 1
    for o in orphans:
        print(f"note: {o} has no counterpart in {bdir}; not compared")

    out_rows = []
    for bpath, apath in pairs:
        print(f"\n=== {apath.stem} ===")
        try:
            bmed, bver = medians(bpath)
        except StaleSegmentation as e:
            print(f"  before file unscoreable: {e}")
            continue
        amed, aver = medians(apath)
        print(f"  {bver}  ->  {aver}")
        print(f"  {'layer':9s} {'before':>8s} {'after':>8s} {'change':>8s}   "
              f"{'paper C/P':>13s}  {'->paper before':>14s} {'->paper after':>13s}")
        print("  " + "-" * 88)
        for layer in ORDER:
            if layer not in amed or layer not in bmed:
                continue
            b, a = bmed[layer]["median_um"], amed[layer]["median_um"]
            r = ref.TREE_SHREW.get(layer)
            pc = f"{r.central:.1f}/{r.peripheral:.1f}" if r is not None else "-"
            db, da = paper_distance(layer, b), paper_distance(layer, a)
            ds = (f"{db:14.1f} {da:13.1f}" if db is not None
                  else f"{'-':>14s} {'-':>13s}")
            print(f"  {layer:9s} {b:8.1f} {a:8.1f} {a - b:+8.1f}   "
                  f"{pc:>13s}  {ds}")
            out_rows.append({"scan_id": apath.stem, "layer": layer,
                             "before_um": b, "after_um": a,
                             "change_um": round(a - b, 1),
                             "dist_before_um": None if db is None else round(db, 1),
                             "dist_after_um": None if da is None else round(da, 1),
                             "version_before": bver, "version_after": aver})

    scored = [r for r in out_rows if r["dist_before_um"] is not None]
    if scored:
        db = np.mean([r["dist_before_um"] for r in scored])
        da = np.mean([r["dist_after_um"] for r in scored])
        print(f"\nmean distance to the published value, over "
              f"{len(scored)} scored layer-scans: {db:.1f} µm -> {da:.1f} µm")

    if args.csv and out_rows:
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()))
            w.writeheader(); w.writerows(out_rows)
        print(f"wrote {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
