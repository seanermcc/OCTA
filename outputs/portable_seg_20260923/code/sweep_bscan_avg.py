#!/usr/bin/env python3
"""
Choose the B-scan averaging width, by measurement rather than by taste.

Averaging N adjacent B-scans before segmenting raises SNR, but blurs real
structure along the slow axis. The optimum is where noise has stopped falling
appreciably and before the map starts to distort. Three numbers per setting:

  noise_um   RMS of the thickness map minus its own slow-axis-smoothed version.
             Pure jitter. Falls with N. Lower is better.

  drift_um   RMS change in the SMOOTHED thickness map relative to N=1. This is
             the blurring/bias term: if N=7 moves the underlying structure
             relative to no averaging at all, averaging has started rewriting
             the anatomy rather than just cleaning it up. Lower is better.

  vessel_r   Correlation between the thickness map and per-A-line signal
             attenuation -- the negative control. A retinal vessel is not a
             layer-thickness feature, so a correct map must be uncorrelated with
             where the vessels are. A large |r| means vessel shadows are leaking
             into the thickness estimate. Closer to zero is better.

Usage:
    python sweep_bscan_avg.py --sample octa_sample_XXX.npz --out sweep.csv

    # from a real scan rather than a dev sample .npz, and draw the figure
    python sweep_bscan_avg.py --seg ../outputs/segment_v3/<sid>.npz \
        --n-bscans 320 --out ../outputs/sweep_<sid>.csv \
        --plot ../outputs/figures/<sid>_sweep.png

`--seg` takes a `batch_segment.py` output only to find the source volume, its
retina band and its orientation -- none of the surfaces in it are used, since
the whole point is to re-segment at each averaging width. A contiguous centre
block of `--n-bscans` is swept rather than the whole volume: the measurement is
a jitter statistic that converges long before 512 B-scans, and the cost is
2 x len(widths) full segmentations of whatever is passed in.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from octa.segment import prepare_bscan, tissue_bounds, banded_dp, shadow_score, build_costs  # noqa: E402
from octa.surfaces import gradient_cost, median_filter1d  # noqa: E402
from octa.volume import segment_volume, thickness_maps  # noqa: E402

LAYERS = ["TOTAL", "RNFL", "GCL_IPL", "INL", "OPL", "ONL", "IS", "OS"]


def smooth_slow(m: np.ndarray, k: int = 9) -> np.ndarray:
    """Median smooth along the B-scan (slow) axis, NaN-tolerant."""
    x = m.T                                    # [col, bscan]
    filled = np.array([_fill(row) for row in x])
    return median_filter1d(filled, k).T


def _fill(row: np.ndarray) -> np.ndarray:
    r = row.astype(np.float64).copy()
    bad = ~np.isfinite(r)
    if bad.all():
        return np.zeros_like(r)
    if bad.any():
        good = np.flatnonzero(~bad)
        r[bad] = np.interp(np.flatnonzero(bad), good, r[good])
    return r


def vessel_map(bscans, vit_high) -> np.ndarray:
    """Per-A-line attenuation score for every B-scan, [n_bscan, n_col]."""
    out = []
    for b in bscans:
        img = prepare_bscan(b, vit_high)
        first, last = tissue_bounds(img)
        c = gradient_cost(img, "dark_to_bright", 5, 11)
        ilm = median_filter1d(banded_dp(c, first, 18, 2).astype(float), 11)
        out.append(shadow_score(img, ilm, np.minimum(ilm + 200, img.shape[0] - 1)))
    return np.array(out)


def load_from_seg(seg_path: str, n_bscans: int):
    """Pull the image block for a sweep out of a real scan.

    One bulk read, cropped to the band the segmentation used, orientation
    re-derived from the volume's own profile -- never from a stored flag, which
    older files got wrong (see CLAUDE.md).
    """
    from octa.volio import ProcessedVolume
    from octa.segment import detect_orientation

    d = np.load(seg_path, allow_pickle=False)
    src = Path(str(d["source"][0]))
    lo, hi = (int(v) for v in d["retina_band"])
    if not src.exists():
        raise FileNotFoundError(f"source volume not found: {src}")
    with ProcessedVolume(src) as v:
        full = v.read_volume(channel="struct")
    profile = full.mean(axis=(0, 1))
    vit = detect_orientation(profile)

    nb = full.shape[0]
    n = min(n_bscans, nb)
    start = (nb - n) // 2
    # Copy the block and drop the volume. Slicing gives a *view*, which keeps
    # the whole 1 GiB read alive for the rest of the sweep -- on top of the
    # twelve segmentation runs that follow, that is enough to fail with
    # ArrayMemoryError on a machine doing anything else at the same time.
    blk = np.ascontiguousarray(full[start:start + n, :, lo:hi])
    del full
    return blk, vit, str(d["scan_id"][0]), start


def plot_sweep(rows, out_png: str, title: str):
    """Jitter vs averaging width, one panel per layer, both refinement modes.

    The circle marks the lowest-jitter width for the refined curve only -- the
    unrefined curve is shown for contrast, not as a candidate setting.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    widths = sorted({r["n_bscan_avg"] for r in rows})
    ncol = 4
    nrow = int(np.ceil(len(LAYERS) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(4.4 * ncol, 3.6 * nrow),
                             squeeze=False)
    for k, layer in enumerate(LAYERS):
        ax = axes[k // ncol][k % ncol]
        for refine, colour, label in ((False, "#d95f02", "averaging only"),
                                      (True, "#1f77b4", "+ slow-axis refinement")):
            y = [next(r["noise_um"] for r in rows
                      if r["layer"] == layer and r["n_bscan_avg"] == w
                      and r["refine"] == refine) for w in widths]
            ax.plot(widths, y, "o-", color=colour, label=label)
            if refine:
                best = int(np.argmin(y))
                ax.plot(widths[best], y[best], "o", ms=13, mfc="none",
                        mec=colour, mew=2)
        ax.set_title(layer, fontsize=12)
        ax.set_xticks(widths)          # N is a count; fractional ticks are noise
        ax.set_xlabel("B-scans averaged (N)", fontsize=9)
        ax.set_ylabel("thickness jitter (µm RMS)\nlower is better", fontsize=9)
        ax.grid(alpha=0.3)
        ax.tick_params(labelsize=8)
        if k == 0:
            ax.legend(fontsize=8)
    for k in range(len(LAYERS), nrow * ncol):
        axes[k // ncol][k % ncol].axis("off")
    fig.suptitle(title, fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out_png, dpi=120)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--sample", help="dev sample .npz holding `block`")
    src.add_argument("--seg", help="segmented .npz; its source volume is read")
    ap.add_argument("--n-bscans", type=int, default=320,
                    help="with --seg, how many centre B-scans to sweep")
    ap.add_argument("--out", default="sweep_bscan_avg.csv")
    ap.add_argument("--plot", default=None, help="also write this .png")
    ap.add_argument("--widths", default="1,3,4,5,6,7")
    ap.add_argument("--px-um", type=float, default=1.12)
    args = ap.parse_args()

    if args.seg:
        blk, vit, label, start = load_from_seg(args.seg, args.n_bscans)
        label = (f"{label} — B-scans {start}-{start + blk.shape[0] - 1} "
                 f"({blk.shape[0] * 1460.0 / 512:.0f} µm of slow axis)")
    else:
        d = np.load(args.sample)
        blk = d["block"]
        # The stored flag was written by an earlier, buggy orientation test;
        # re-derive it.
        from octa.segment import detect_orientation
        vit = detect_orientation(d["profile"])
        label = (f"{Path(args.sample).stem} — {blk.shape[0]} B-scans "
                 f"({blk.shape[0] * 1460.0 / 512:.0f} µm of slow axis)")

    vmap = vessel_map(blk, vit)
    widths = [int(w) for w in args.widths.split(",")]

    baseline = {}
    rows = []
    for refine in (False, True):
        for n in widths:
            surf, _conf, sh, _notes = segment_volume(
                blk, vit, bscan_avg=n, refine=refine, px_um=args.px_um)
            tm_raw = thickness_maps(surf, sh, args.px_um, mask_shadow=False)
            tm = thickness_maps(surf, sh, args.px_um, mask_shadow=True)
            for layer in LAYERS:
                m = tm[layer]
                sm = smooth_slow(m)
                noise = float(np.sqrt(np.nanmean((m - sm) ** 2)))

                med = float(np.nanmedian(m))
                key = (refine, layer)
                if n == widths[0]:
                    baseline[key] = med
                bias = med - baseline[key]

                # Negative control. Two versions, because they answer different
                # questions: `all` includes the shadowed A-lines and measures how
                # badly vessels corrupt the map overall; `clean` excludes them and
                # measures whether the corruption is leaking sideways into
                # A-lines we are keeping. Only `clean` should be near zero -- part
                # of the `all` correlation is genuine anatomy, since a vessel
                # really does sit inside the retina and bulge the ILM.
                raw = tm_raw[layer]
                ok = np.isfinite(raw) & np.isfinite(vmap)
                r_all = float(np.corrcoef(raw[ok].ravel(), vmap[ok].ravel())[0, 1])
                ok2 = ok & ~sh
                r_clean = (float(np.corrcoef(raw[ok2].ravel(), vmap[ok2].ravel())[0, 1])
                           if ok2.sum() > 100 else float("nan"))

                rows.append({"refine": refine, "n_bscan_avg": n, "layer": layer,
                             "median_um": round(med, 2),
                             "bias_um": round(bias, 2),
                             "noise_um": round(noise, 3),
                             "vessel_r_all": round(r_all, 3),
                             "vessel_r_clean": round(r_clean, 3)})
            print(f"  refine={refine} n={n} done", flush=True)

    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"wrote {args.out}  ({len(rows)} rows)")

    if args.plot:
        Path(args.plot).parent.mkdir(parents=True, exist_ok=True)
        plot_sweep(rows, args.plot,
                   f"which B-scan averaging width?  {label}, "
                   f"circles mark the best refined setting")
        print(f"wrote {args.plot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
