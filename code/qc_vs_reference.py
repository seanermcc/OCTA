#!/usr/bin/env python3
"""
Score a segmentation against the published tree shrew layer thicknesses, and
say for each surface whether the image or the prior decided where it went.

Two different questions, deliberately reported side by side:

**Is the answer plausible?**  Each layer's median thickness is compared with
the eNeuro 2024 tree shrew table (`octa/reference.py`). This catches a
mislabelled cascade -- the failure that made the previous priors put ELM 33 um
too shallow and report a 47 um "IS" layer.

**Is the answer supported?**  Per-A-line confidence says how much better the
chosen depth was than the best alternative elsewhere in the column. Near zero
means the smoothness prior and the search window decided, not the image.

Plausible-and-supported is a result. Plausible-but-unsupported is the dangerous
case, because it looks exactly like a result: a surface pinned by its prior is
smooth, correctly ordered, anatomically sensible, and completely uninformative.
That is the failure this project already hit once, on a low-signal B-scan whose
contrast-stretched QC plot looked fine. A layer that is implausible is at least
honest about it.

Usage
-----
    conda activate octa

    # score a batch output
    python qc_vs_reference.py --npz ..\\outputs\\segmented\\TS241_OD_....npz

    # score a development sample, segmenting it on the fly
    python qc_vs_reference.py --sample ..\\outputs\\samples\\slab_TS165_WT.npz

    # every batch output, one row each, into a CSV
    python qc_vs_reference.py --all --out ..\\outputs\\qc_reference_scores.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from octa import reference as ref                                   # noqa: E402
from octa.segment import (SURFACE_NAMES, LAYER_DEFS,                # noqa: E402
                         RETIRED_SURFACES,
                          detect_orientation, RELATIVE_PRIORS)
from octa.volume import segment_volume, thickness_maps              # noqa: E402

PX_UM = 1.12


class StaleSegmentation(Exception):
    """Output written by a cascade version whose labels are known wrong."""


# Below this, the chosen depth was no better than its local neighbourhood and
# the surface is being held in place by the prior alone.
#
# The threshold is on `local_confidence`, which is a robust z-score: the cost at
# the chosen depth against the median and MAD of the surrounding +/-8 px. 0.5
# therefore means "half a MAD better than typical", which is about the weakest
# dip still distinguishable from speckle. For scale, on the TS165 wild-type slab
# the ILM measures 1.69 and BM 2.03 -- those are what a genuinely image-driven
# surface looks like.
#
# NOTE the earlier metric, `surface_confidence`, is a *global* comparison and is
# routinely negative for every banded surface including the ILM. Thresholding it
# marks the whole cascade unsupported, which is why an earlier attempt at this
# check was computed and then discarded as useless.
CONF_FLOOR = 0.5


def load_segmented(path: Path) -> dict:
    """Read a batch output .npz. Tolerates files written before confidence
    was stored, so old outputs can still be scored -- they simply report
    unknown support rather than failing."""
    d = np.load(path, allow_pickle=False)
    out = {"surfaces": d["surfaces"], "shadow": d["shadow"],
           "scan_id": str(d["scan_id"][0]) if "scan_id" in d else path.stem,
           "px_um": float(d["px_um"][0]) if "px_um" in d else PX_UM,
           "names": [str(x) for x in d["surface_names"]]
                    if "surface_names" in d else SURFACE_NAMES}
    out["confidence"] = d["confidence"].astype(np.float32) if "confidence" in d else None
    return out


def segment_sample(path: Path, stride: int = 4) -> dict:
    """Segment a development sample .npz on the fly."""
    d = np.load(path)
    slab = d["slab"][::stride]
    vhi = detect_orientation(d["profile"])
    surf, conf, shadow, notes = segment_volume(
        slab, vhi, bscan_avg=3, refine=True, smooth_bscans=5,
        px_um=PX_UM, attract=0.05, progress=True)
    if notes:
        print(f"  {len(notes)} note(s) from the cascade, first few:")
        for n in notes[:5]:
            print(f"    {n}")
    return {"surfaces": surf, "confidence": conf, "shadow": shadow,
            "scan_id": path.stem, "px_um": PX_UM, "names": SURFACE_NAMES}


def score(seg: dict) -> tuple[list[dict], list[dict]]:
    """Per-layer plausibility rows and per-surface support rows."""
    surf, shadow = seg["surfaces"], seg["shadow"]
    px_um = seg["px_um"]
    names = seg["names"]
    conf_in = seg.get("confidence")

    # Two different kinds of mismatch, and they deserve opposite treatment.
    #
    # A file carrying every surface this cascade defines, plus some it has
    # since retired, is a *superset*: the shared surfaces mean exactly what
    # they mean now, so it can be scored on those and the extras ignored. That
    # is the case for output written before the IPL sublaminae were dropped,
    # and refusing it would throw away hours of correct segmentation over two
    # columns nobody trusted anyway.
    #
    # A file *missing* a surface this cascade defines is a different animal: it
    # predates the reference-based priors, so its inner-retina labels are wrong
    # by one landmark all the way down. Every number printed for it would be a
    # confident measurement of the wrong thing -- worse than no number at all,
    # and scoring it partially would be worse still, because the layers that
    # happened to line up would look like corroboration.
    names = list(names)
    if names != list(SURFACE_NAMES):
        missing = [n for n in SURFACE_NAMES if n not in names]
        if missing:
            raise StaleSegmentation(
                f"this file has {len(names)} surfaces ({', '.join(names)}) and "
                f"is missing {', '.join(missing)},\n"
                f"  which the current cascade defines. It predates the "
                f"reference-based priors, so its\n"
                f"  inner-retina labels are the ones known to be wrong by one "
                f"landmark (the first dark\n"
                f"  band below the RNFL is the GCL, not the INL).\n"
                f"  Re-run:  python batch_segment.py --overwrite")
        extra = [n for n in names if n not in SURFACE_NAMES]
        keep = [names.index(n) for n in SURFACE_NAMES]
        surf = surf[:, keep, :]
        if conf_in is not None:
            conf_in = conf_in[:, keep, :]
        msg = (f"  note: scoring {len(SURFACE_NAMES)} of this file's "
               f"{len(names)} surfaces; ignoring retired {', '.join(extra)}")
        if not set(extra) <= set(RETIRED_SURFACES):
            msg += "\n  WARNING: not all ignored surfaces are known retired ones"
        print(msg)
        names = list(SURFACE_NAMES)

    tm = thickness_maps(surf, shadow, px_um=px_um)

    layer_rows = []
    for name, _, _ in LAYER_DEFS:
        if name not in tm:
            continue
        v = tm[name][np.isfinite(tm[name])]
        if v.size == 0:
            continue
        med = float(np.median(v))
        q1, q3 = (float(x) for x in np.percentile(v, [25, 75]))
        row = {"layer": name, "median_um": round(med, 1),
               "iqr_um": f"{q1:.1f}-{q3:.1f}", "n_alines": int(v.size)}
        try:
            r = ref.TREE_SHREW[name]
            lo, hi = ref.plausible_range(name)
            frac_in = float(np.mean((v >= lo) & (v <= hi)))
            row.update({
                "paper_central": r.central, "paper_peripheral": r.peripheral,
                "plausible_lo": round(lo, 1), "plausible_hi": round(hi, 1),
                "frac_in_range": round(frac_in, 3),
                "verdict": "OK" if lo <= med <= hi else "OUT_OF_RANGE",
                "ref_confirmed": r.confirmed,
            })
        except KeyError:
            row.update({"paper_central": "", "paper_peripheral": "",
                        "plausible_lo": "", "plausible_hi": "",
                        "frac_in_range": "", "verdict": "no_reference",
                        "ref_confirmed": ""})
        layer_rows.append(row)

    support_rows = []
    conf = conf_in
    for s, sname in enumerate(names):
        row = {"surface": sname}
        if conf is None:
            row.update({"median_conf": "", "frac_prior_driven": "",
                        "support": "unknown_old_file"})
        else:
            c = conf[:, s, :][~shadow]
            med_c = float(np.median(c))
            frac_prior = float(np.mean(c < CONF_FLOOR))
            row.update({
                "median_conf": round(med_c, 4),
                "frac_prior_driven": round(frac_prior, 3),
                "support": ("image" if frac_prior < 0.25 else
                            "mixed" if frac_prior < 0.60 else "PRIOR_ONLY"),
            })
        support_rows.append(row)
    return layer_rows, support_rows


def print_report(seg: dict, layer_rows: list[dict], support_rows: list[dict]) -> None:
    print(f"\n=== {seg['scan_id']} ===")
    print("\nplausibility vs eNeuro 2024 tree shrew "
          "(central / peripheral; [fig] = read off a figure, not stated in text)")
    print(f"  {'layer':9s} {'median':>8s} {'IQR':>14s} {'paper C':>9s} {'paper P':>9s} "
          f"{'in range':>9s}  verdict")
    print("  " + "-" * 76)
    for r in layer_rows:
        mark = "" if r["ref_confirmed"] in (True, "") else " [fig]"
        pc = f"{r['paper_central']}" if r["paper_central"] != "" else "-"
        pp = f"{r['paper_peripheral']}" if r["paper_peripheral"] != "" else "-"
        fr = f"{r['frac_in_range']*100:.0f}%" if r["frac_in_range"] != "" else "-"
        print(f"  {r['layer']:9s} {r['median_um']:8.1f} {r['iqr_um']:>14s} "
              f"{pc:>9s} {pp:>9s} {fr:>9s}  {r['verdict']}{mark}")

    print("\nsupport: did the image decide, or the prior?")
    print(f"  {'surface':10s} {'median conf':>12s} {'prior-driven':>13s}  support")
    print("  " + "-" * 50)
    for r in support_rows:
        mc = r["median_conf"]
        fp = r["frac_prior_driven"]
        mcs = f"{mc:.4f}" if mc != "" else "-"
        fps = f"{fp*100:.0f}%" if fp != "" else "-"
        print(f"  {r['surface']:10s} {mcs:>12s} {fps:>13s}  {r['support']}")

    bad = [r["layer"] for r in layer_rows if r["verdict"] == "OUT_OF_RANGE"]
    weak = [r["surface"] for r in support_rows if r["support"] == "PRIOR_ONLY"]
    print()
    if bad:
        print(f"  IMPLAUSIBLE: {', '.join(bad)}")
    if weak:
        print(f"  UNSUPPORTED (prior placed these, the image did not): "
              f"{', '.join(weak)}")
        print("  Report these as unreliable rather than dropping them "
              "(CLAUDE.md: all layers matter).")
    if not bad and not weak:
        print("  all layers plausible and image-supported")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--npz", help="a batch output from outputs/segmented/")
    g.add_argument("--sample", help="a development sample; segmented on the fly")
    g.add_argument("--all", action="store_true",
                   help="score every .npz in --seg-dir")
    ap.add_argument("--seg-dir", default="../outputs/segmented")
    ap.add_argument("--stride", type=int, default=4,
                    help="B-scan stride when segmenting a sample (default 4)")
    ap.add_argument("--out", default=None, help="write per-layer rows to CSV")
    ap.add_argument("--show-priors", action="store_true",
                    help="print the reference table and derived priors, then exit")
    args = ap.parse_args()

    if args.show_priors:
        print(ref.summary_table())
        print("\nrelative priors (fraction of ILM -> RPE-peak), peripheral:")
        for k, v in RELATIVE_PRIORS.items():
            print(f"  {k:10s} {v:.3f}")
        return 0

    targets = []
    if args.npz:
        targets = [("seg", Path(args.npz))]
    elif args.sample:
        targets = [("sample", Path(args.sample))]
    else:
        targets = [("seg", p) for p in sorted(Path(args.seg_dir).glob("*.npz"))]
        if not targets:
            print(f"no .npz found in {args.seg_dir}")
            return 1

    all_rows, n_stale = [], 0
    for kind, path in targets:
        seg = load_segmented(path) if kind == "seg" else segment_sample(path, args.stride)
        try:
            layer_rows, support_rows = score(seg)
        except StaleSegmentation as e:
            n_stale += 1
            print(f"\n=== {seg['scan_id']} ===\n  SKIPPED: {e}")
            continue
        print_report(seg, layer_rows, support_rows)
        for r in layer_rows:
            all_rows.append({"scan_id": seg["scan_id"], **r})

    if n_stale:
        print(f"\n{n_stale} scan(s) skipped as stale. They were segmented by an "
              f"earlier cascade whose\ninner-retina labels are wrong; re-run "
              f"batch_segment.py --overwrite before scoring them.")

    if args.out and all_rows:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
            w.writeheader()
            w.writerows(all_rows)
        print(f"\nwrote {len(all_rows)} rows to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
