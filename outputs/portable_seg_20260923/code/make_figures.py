#!/usr/bin/env python3
"""
Rebuild the presentation figures from a segmented scan.

The four figures this project shows people were originally produced by ad-hoc
code that no longer exists, which meant every re-segmentation left them stale
with no way to refresh them. This script is the replacement: given a
`batch_segment.py` output `.npz` it regenerates all of them, and given a second
`.npz` from an earlier cascade it also draws the before/after comparison that
makes a segmentation change visible.

    overview     en-face + TOTAL/RNFL/ONL thickness           (--figs overview)
    maps         en-face + shadow mask + 8 layer thickness maps      (maps)
    bscans       3 B-scans with all 10 surfaces overlaid            (bscans)
    compare      the same 3 B-scans, old surfaces vs new            (compare)

`compare` is the only one that needs `--before`; the rest ignore it.

Usage
-----
    python make_figures.py --seg ../outputs/segment_v3/<sid>.npz \
                           --before ../outputs/segment_v2/<sid>.npz \
                           --out-dir ../outputs/figures/v3

    # all three of a session's scans, picking the B-scans automatically
    python make_figures.py --seg-dir ../outputs/segment_v3 \
                           --before-dir ../outputs/segment_v2 \
                           --out-dir ../outputs/figures/v3

Reading the volume
------------------
The en-face projection and the B-scan images are not in the segmentation
output -- they need the original `processedVolumes.mat`, whose path each
`.npz` records in `source`. That read is a single bulk read
(`ProcessedVolume.read_volume`), never a per-B-scan loop: this dataset's HDF5
chunks span the whole B-scan axis, so slicing out three B-scans costs the same
as reading all 512 and doing it in a loop costs ~1500x more (see octa/volio.py).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from octa.volio import ProcessedVolume  # noqa: E402
from octa.segment import (  # noqa: E402
    SURFACE_NAMES, CASCADE_VERSION, prepare_bscan, detect_orientation,
)
from octa.volume import thickness_maps  # noqa: E402

# Nominal retinal extent of the 500 um galvo drive, both axes. The `X500um` in
# the filenames is drive amplitude, not retinal extent -- see CLAUDE.md.
FIELD_UM = 1460.0

# Panels for the `maps` figure. GCL and IPL are shown separately as well as
# combined because GCL_IPL is what this project could report before the
# cascade could separate them, and keeping it visible makes old and new
# figures comparable.
MAP_LAYERS = ["TOTAL", "RNFL", "GCL_IPL", "INL", "OPL", "ONL", "IS", "OS"]
OVERVIEW_LAYERS = ["TOTAL", "RNFL", "ONL"]


# --------------------------------------------------------------------------
# loading
# --------------------------------------------------------------------------

def load_seg(path: Path) -> dict:
    """Read a batch output .npz.

    Fields are unpacked defensively because the older outputs this script is
    asked to draw as the "before" column predate several of them --
    `cascade_version` in particular was only added when the cascade started
    changing. A missing stamp is reported as unknown; it is not a reason to
    refuse to draw the comparison, which is the whole point of the figure.
    """
    d = np.load(path, allow_pickle=False)
    out = {k: d[k] for k in d.files}
    out["path"] = path
    out["scan_id"] = str(out["scan_id"][0]) if "scan_id" in d else path.stem
    out["source"] = Path(str(out["source"][0])) if "source" in d else None
    out["surface_names"] = ([str(s) for s in out["surface_names"]]
                            if "surface_names" in d else list(SURFACE_NAMES))
    out["cascade_version"] = (str(out["cascade_version"][0])
                              if "cascade_version" in d else "unstamped")
    out["px_um"] = float(out["px_um"][0]) if "px_um" in d else 1.12
    out["retina_band"] = (tuple(int(v) for v in out["retina_band"])
                          if "retina_band" in d else None)
    out["vitreous_at_high_index"] = (bool(out["vitreous_at_high_index"][0])
                                     if "vitreous_at_high_index" in d else None)
    out["bscan_avg"] = int(out["bscan_avg"][0]) if "bscan_avg" in d else 0
    out["surfaces"] = out["surfaces"].astype(np.float64)
    return out


def read_volume_for(seg: dict) -> np.ndarray:
    """Bulk-read the source volume, cropped to the same band the segmentation
    used, so surface depths index straight into it."""
    src = seg["source"]
    if src is None or seg["retina_band"] is None:
        raise ValueError(f"{seg['path'].name} does not record its source "
                         f"volume or retina band; re-run batch_segment.py")
    if not src.exists():
        raise FileNotFoundError(f"source volume not found: {src}")
    lo, hi = seg["retina_band"]
    with ProcessedVolume(src) as v:
        full = v.read_volume(channel="struct")        # [nb, na, nd]
    return full[:, :, lo:hi]


def enface_from(bscans: np.ndarray) -> np.ndarray:
    """Depth-averaged structural en-face, [B-scan, A-line], in dB."""
    m = bscans.mean(axis=2)
    return 20.0 * np.log10(np.maximum(m, 1e-3))


def surface_index(seg: dict) -> dict:
    return {n: i for i, n in enumerate(seg["surface_names"])}


# --------------------------------------------------------------------------
# B-scan selection
# --------------------------------------------------------------------------

def usable_bscans(seg: dict, edge_frac: float = 0.10) -> np.ndarray:
    """Boolean mask of B-scans worth putting in a figure at all.

    Three ways a B-scan is not worth showing, none of which say anything is
    wrong with the segmentation:

    * it is near either end of the slow axis, where the retina tilts out of
      the recorded depth range and every surface piles up against the frame;
    * most of its A-lines are shadowed, so there is nothing to look at;
    * its total thickness is nowhere near a retina, which means the band
      detection, not the cascade, is what the panel would be showing.

    Without this, "the B-scan that departs most from the median" reliably
    picks B-scan 0 -- an edge artefact -- instead of a lesion.
    """
    tm = thickness_maps(seg["surfaces"], seg["shadow"], seg["px_um"])["TOTAL"]
    nb = tm.shape[0]
    finite = np.isfinite(tm)
    with np.errstate(invalid="ignore"):
        per_bscan = np.nanmedian(np.where(finite, tm, np.nan), axis=1)
    ok = (finite.mean(axis=1) >= 0.7)
    ok &= np.isfinite(per_bscan) & (per_bscan > 120.0) & (per_bscan < 400.0)
    lo, hi = int(edge_frac * nb), int((1 - edge_frac) * nb)
    ok[:lo] = False
    ok[hi:] = False
    return ok


def pick_bscans(seg: dict, n: int = 3) -> list[int]:
    """
    Choose B-scans worth showing.

    Evenly spaced would show the typical case and miss the reason anyone looks
    at a CNV scan at all. Instead take the usable B-scan whose total-retina
    thickness departs most from the scan's own median (a lesion is precisely a
    localised departure), then fill the rest evenly from the usable ones,
    keeping the picks separated so three views of one lesion don't crowd out
    the rest of the volume.
    """
    tm = thickness_maps(seg["surfaces"], seg["shadow"], seg["px_um"])["TOTAL"]
    nb = tm.shape[0]
    ok = usable_bscans(seg)
    if not ok.any():                       # nothing passed; fall back to even
        return [int(round((k + 1) * nb / (n + 1))) for k in range(n)]

    with np.errstate(invalid="ignore"):
        per_bscan = np.nanmedian(tm, axis=1)
    dev = np.abs(per_bscan - np.nanmedian(per_bscan[ok]))
    dev[~ok] = -1.0
    dev[~np.isfinite(dev)] = -1.0

    usable = np.flatnonzero(ok)
    min_sep = max(nb // (n + 2), 1)
    picks = [int(np.argmax(dev))]
    for cand in [int(round((k + 1) * nb / (n + 1))) for k in range(n)]:
        # snap an evenly spaced target onto the nearest usable B-scan
        cand = int(usable[np.argmin(np.abs(usable - cand))])
        if len(picks) < n and all(abs(cand - p) >= min_sep for p in picks):
            picks.append(cand)
    for cand in usable:                    # back-fill rather than return < n
        if len(picks) >= n:
            break
        if all(abs(int(cand) - p) >= min_sep for p in picks):
            picks.append(int(cand))
    return sorted(picks[:n])


# --------------------------------------------------------------------------
# shared drawing helpers
# --------------------------------------------------------------------------

def _imshow_um(ax, img, **kw):
    kw.setdefault("extent", [0, FIELD_UM, FIELD_UM, 0])
    kw.setdefault("aspect", "equal")
    return ax.imshow(img, **kw)


def _thickness_panel(ax, m: np.ndarray, title: str):
    """One thickness map. Colour limits are robust percentiles: a handful of
    A-lines at a lesion edge otherwise take the whole colour range and flatten
    every real difference in the rest of the field."""
    finite = m[np.isfinite(m)]
    if finite.size:
        vmin, vmax = np.percentile(finite, [2, 98])
        if vmax <= vmin:
            vmin, vmax = float(finite.min()), float(finite.max()) + 1e-6
    else:
        vmin, vmax = 0.0, 1.0
    im = _imshow_um(ax, m, cmap="viridis", vmin=vmin, vmax=vmax,
                    interpolation="nearest")
    med = np.nanmedian(m) if finite.size else float("nan")
    ax.set_title(f"{title}   median {med:.0f} µm", fontsize=11)
    ax.set_xlabel("µm", fontsize=9)
    ax.set_ylabel("µm", fontsize=9)
    ax.tick_params(labelsize=8)
    cb = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
    cb.ax.tick_params(labelsize=8)
    return im


def _enface_panel(ax, enface: np.ndarray, title: str = "structural en-face"):
    lo, hi = np.percentile(enface, [1, 99])
    _imshow_um(ax, enface, cmap="gray", vmin=lo, vmax=hi,
               interpolation="nearest")
    ax.set_title(title, fontsize=11)
    ax.set_xlabel("µm", fontsize=9)
    ax.set_ylabel("µm", fontsize=9)
    ax.tick_params(labelsize=8)


def _title_for(seg: dict, what: str) -> str:
    nb = seg["surfaces"].shape[0]
    avg = seg["bscan_avg"]
    avg_txt = f"{avg}-B-scan averaging, " if avg else ""
    return (f"{seg['scan_id']} — {what}   (all {nb} B-scans, {avg_txt}"
            f"cascade {seg['cascade_version']})")


# --------------------------------------------------------------------------
# figures
# --------------------------------------------------------------------------

def fig_overview(seg, enface, out_path: Path):
    tm = thickness_maps(seg["surfaces"], seg["shadow"], seg["px_um"])
    fig, axes = plt.subplots(1, 1 + len(OVERVIEW_LAYERS),
                             figsize=(4.6 * (1 + len(OVERVIEW_LAYERS)), 5.0))
    _enface_panel(axes[0], enface, "structural en-face\n(for orientation)")
    for ax, layer in zip(axes[1:], OVERVIEW_LAYERS):
        name = "Total retina (ILM-BM)" if layer == "TOTAL" else layer
        _thickness_panel(ax, tm[layer], name)
    fig.suptitle(_title_for(seg, "layer thickness maps"), fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def fig_maps(seg, enface, out_path: Path):
    tm = thickness_maps(seg["surfaces"], seg["shadow"], seg["px_um"])
    shadow = seg["shadow"].astype(bool)
    fig, axes = plt.subplots(2, 5, figsize=(24, 11))

    _enface_panel(axes[0, 0], enface)
    _imshow_um(axes[1, 0], shadow.astype(float), cmap="gray_r",
               interpolation="nearest")
    axes[1, 0].set_title(
        f"excluded vessel-shadow A-lines\n({100 * shadow.mean():.0f}% of the field)",
        fontsize=11)
    axes[1, 0].set_xlabel("µm", fontsize=9)
    axes[1, 0].set_ylabel("µm", fontsize=9)
    axes[1, 0].tick_params(labelsize=8)

    panels = [axes[0, 1], axes[0, 2], axes[0, 3], axes[0, 4],
              axes[1, 1], axes[1, 2], axes[1, 3], axes[1, 4]]
    for ax, layer in zip(panels, MAP_LAYERS):
        name = {"TOTAL": "Total retina (ILM-BM)", "GCL_IPL": "GCL + IPL"}.get(layer, layer)
        _thickness_panel(ax, tm[layer], name)

    fig.suptitle(_title_for(seg, "full-resolution layer thickness maps"),
                 fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out_path, dpi=110)
    plt.close(fig)


def _draw_surfaces(ax, seg, bi: int, colors, lw=1.1, ls="-", alpha=1.0):
    surf = seg["surfaces"][bi]
    for k, name in enumerate(seg["surface_names"]):
        ax.plot(surf[k], color=colors[name], lw=lw, ls=ls, alpha=alpha)


def _bscan_image(bscans, seg, bi: int) -> np.ndarray:
    return prepare_bscan(bscans[bi], seg["vitreous_at_high_index"])


def _colors_for(names):
    cmap = plt.get_cmap("turbo")
    return {n: cmap(0.05 + 0.9 * i / max(len(names) - 1, 1))
            for i, n in enumerate(names)}


def _show_bscan(ax, img):
    lo, hi = np.percentile(img, [5, 99.5])
    ax.imshow(img, cmap="gray", aspect="auto", vmin=lo, vmax=hi,
              interpolation="nearest")
    ax.tick_params(labelsize=8)


def fig_bscans(seg, bscans, picks, out_path: Path):
    colors = _colors_for(seg["surface_names"])
    fig, axes = plt.subplots(len(picks), 1, figsize=(15, 4.2 * len(picks)))
    axes = np.atleast_1d(axes)
    for ax, bi in zip(axes, picks):
        _show_bscan(ax, _bscan_image(bscans, seg, bi))
        _draw_surfaces(ax, seg, bi, colors)
        ax.set_title(f"{seg['scan_id']} — B-scan {bi}", fontsize=11)
    handles = [Line2D([], [], color=colors[n], lw=2, label=n)
               for n in seg["surface_names"]]
    # Legend above the panels, not inside them: at this aspect ratio an
    # in-axes legend covers the nasal edge of the first B-scan, which is
    # exactly where edge artefacts show up.
    fig.legend(handles=handles, fontsize=9, ncol=10, loc="upper center",
               bbox_to_anchor=(0.5, 0.955), frameon=False)
    fig.suptitle(_title_for(seg, "automatic layer surfaces"), fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.945))
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def fig_compare(seg, before, bscans, picks, out_path: Path):
    """Old surfaces and new surfaces on identical B-scans, side by side.

    Both panels show the same image, so every visible difference is the
    cascade's, not the display's. Surfaces the two versions do not share (the
    retired IPL sublaminae, for instance) are drawn only where they exist
    rather than silently dropped from the older column.
    """
    colors = _colors_for(seg["surface_names"])
    for n in before["surface_names"]:
        colors.setdefault(n, (0.6, 0.6, 0.6, 1.0))

    fig, axes = plt.subplots(len(picks), 2, figsize=(22, 4.2 * len(picks)),
                             squeeze=False)
    for r, bi in enumerate(picks):
        img = _bscan_image(bscans, seg, bi)
        for c, (which, s) in enumerate((("before", before), ("after", seg))):
            ax = axes[r, c]
            _show_bscan(ax, img)
            _draw_surfaces(ax, s, bi, colors)
            ax.set_title(f"B-scan {bi} — {which} "
                         f"(cascade {s['cascade_version']})", fontsize=11)
    handles = [Line2D([], [], color=colors[n], lw=2, label=n)
               for n in seg["surface_names"]]
    # Legend above the panels, not inside them: at this aspect ratio an
    # in-axes legend covers the nasal edge of the first B-scan, which is
    # exactly where edge artefacts show up.
    extra = [n for n in before["surface_names"] if n not in seg["surface_names"]]
    handles += [Line2D([], [], color=colors[n], lw=2, label=f"{n} (retired)")
                for n in extra]
    fig.legend(handles=handles, fontsize=9, ncol=len(handles), loc="upper center",
               bbox_to_anchor=(0.5, 0.955), frameon=False)
    fig.suptitle(f"{seg['scan_id']} — automatic surfaces before vs after "
                 f"({before['cascade_version']} → {seg['cascade_version']})",
                 fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.945))
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


# --------------------------------------------------------------------------

def run_one(seg_path: Path, before_path: Path | None, out_dir: Path,
            figs: list[str], bscans_arg: list[int] | None) -> int:
    seg = load_seg(seg_path)
    if seg["cascade_version"] != CASCADE_VERSION:
        print(f"  note: this file is cascade {seg['cascade_version']}, "
              f"current is {CASCADE_VERSION}")
    before = load_seg(before_path) if before_path else None

    need_volume = bool({"overview", "maps", "bscans", "compare"} & set(figs))
    bscans = enface = None
    if need_volume:
        print("  reading source volume (one bulk read) ...", flush=True)
        bscans = read_volume_for(seg)
        enface = enface_from(bscans)

    picks = bscans_arg or pick_bscans(seg)
    out_dir.mkdir(parents=True, exist_ok=True)
    sid = seg["scan_id"]

    if "overview" in figs:
        p = out_dir / f"{sid}_overview.png"
        fig_overview(seg, enface, p); print(f"  wrote {p.name}")
    if "maps" in figs:
        p = out_dir / f"{sid}_thickness_maps.png"
        fig_maps(seg, enface, p); print(f"  wrote {p.name}")
    if "bscans" in figs:
        p = out_dir / f"{sid}_bscans.png"
        fig_bscans(seg, bscans, picks, p)
        print(f"  wrote {p.name}  (B-scans {picks})")
    if "compare" in figs:
        if before is None:
            print("  skipped compare: no --before file for this scan")
        else:
            p = out_dir / f"{sid}_before_after.png"
            fig_compare(seg, before, bscans, picks, p)
            print(f"  wrote {p.name}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--seg", help="one segmented .npz")
    src.add_argument("--seg-dir", help="every .npz in this directory")
    ap.add_argument("--before", help="earlier .npz for the same scan")
    ap.add_argument("--before-dir",
                    help="directory holding earlier .npz, matched by filename")
    ap.add_argument("--out-dir", default="../outputs/figures")
    ap.add_argument("--figs", default="overview,maps,bscans,compare",
                    help="comma-separated: overview, maps, bscans, compare")
    ap.add_argument("--bscans", default=None,
                    help="comma-separated B-scan indices; default picks them")
    args = ap.parse_args()

    figs = [f.strip() for f in args.figs.split(",") if f.strip()]
    picks = ([int(b) for b in args.bscans.split(",")] if args.bscans else None)
    out_dir = Path(args.out_dir)

    if args.seg:
        jobs = [(Path(args.seg), Path(args.before) if args.before else None)]
    else:
        seg_dir = Path(args.seg_dir)
        bdir = Path(args.before_dir) if args.before_dir else None
        jobs = []
        for p in sorted(seg_dir.glob("*.npz")):
            b = (bdir / p.name) if bdir and (bdir / p.name).exists() else None
            jobs.append((p, b))

    rc = 0
    for i, (p, b) in enumerate(jobs, 1):
        print(f"[{i}/{len(jobs)}] {p.name}", flush=True)
        try:
            rc |= run_one(p, b, out_dir, figs, picks)
        except Exception as e:                                   # noqa: BLE001
            print(f"  FAILED: {type(e).__name__}: {e}")
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
