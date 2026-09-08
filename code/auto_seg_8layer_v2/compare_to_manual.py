#!/usr/bin/env python3
"""Render revision-2 automatic lines beside the human hand-drawn lines.

This is the direct check: for every corrected B-scan in the 16 labelled review
packs, re-segment it with revision 2 through the real pipeline (a slab wide
enough for 3-B-scan averaging and the 5-B-scan slow-axis median, matching what
``eval_variants.py`` scores), and draw the human line and the v2 line on the
same image so they can be compared by eye, not just by summary statistic.

Run from ``code`` with ``octa`` activated::

    python auto_seg_8layer_v2/compare_to_manual.py
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR))

from octa.volio import ProcessedVolume, find_retina_band  # noqa: E402

from eight_surface import labels as L  # noqa: E402
from eight_surface.config import SURFACE_NAMES  # noqa: E402
from eight_surface.segment import detect_orientation  # noqa: E402

from auto_seg_8layer_v2.eval_variants import segmented_source  # noqa: E402
from auto_seg_8layer_v2.segment_v2 import load_priors_v2  # noqa: E402
from auto_seg_8layer_v2.volume_v2 import segment_volume  # noqa: E402

PX_UM = 1.12
SLAB_HALF = 6
COLOURS = ["#e6194b", "#3cb44b", "#ffe119", "#4363d8",
           "#f58231", "#911eb4", "#46f0f0", "#f032e6"]


def run_v2_on_labelled(records_by_scan, seg_dir: Path, priors):
    """Re-segment a slab around every labelled B-scan with revision 2."""
    out = {}
    started = time.time()
    for number, (scan_id, records) in enumerate(sorted(records_by_scan.items()), 1):
        source = segmented_source(seg_dir, scan_id)
        with ProcessedVolume(source) as volume:
            full = volume.read_volume(channel="struct")
            profile = full.mean(axis=(0, 1))
            lo, hi, _stale = find_retina_band(profile)
            vitreous_at_high_index = detect_orientation(profile)
            band = full[:, :, lo:hi]
        n_b = band.shape[0]
        wanted = sorted({r["bscan"] for r in records})
        print(f"  [{number}/{len(records_by_scan)}] {scan_id}: "
              f"{len(wanted)} labelled B-scans", flush=True)
        for bscan in wanted:
            start = max(0, bscan - SLAB_HALF)
            stop = min(n_b, bscan + SLAB_HALF + 1)
            surfaces, confidence, shadow, _notes = segment_volume(
                band[start:stop], vitreous_at_high_index, bscan_avg=3,
                refine=True, smooth_bscans=5, px_um=PX_UM, attract=0.05,
                progress=False, prior_overrides=priors)
            i = bscan - start
            out[(scan_id, bscan)] = (surfaces[i].astype(float),
                                     confidence[i].astype(float),
                                     shadow[i].astype(bool))
    print(f"  {len(out)} B-scans re-segmented with revision 2 in "
          f"{time.time() - started:.0f}s")
    return out


def pack_images(pack_dir: Path) -> dict[tuple[str, int], np.ndarray]:
    out = {}
    for path in sorted(pack_dir.glob("*_pack.npz")):
        with np.load(path, allow_pickle=False) as pack:
            scan_id = str(pack["scan_id"][0])
            for k, bscan in enumerate(pack["bscan_index"].astype(int)):
                out[(scan_id, int(bscan))] = pack["images"][k].astype(np.float32)
    return out


def render(record, image, v2_surfaces, out_path: Path) -> None:
    finite = image[np.isfinite(image)]
    lo, hi = np.percentile(finite, [2, 99.5]) if finite.size else (0.0, 1.0)
    fig, axes = plt.subplots(1, 2, figsize=(17, 5.8), constrained_layout=True,
                             sharex=True, sharey=True)
    x = np.arange(image.shape[1])
    excluded = record["region_excluded"]
    for ax, surf, what in ((axes[0], record["surfaces"], "human (hand-drawn)"),
                           (axes[1], v2_surfaces, "revision-2 automatic")):
        ax.imshow(image, cmap="gray", aspect="auto", vmin=lo, vmax=hi)
        for k, name in enumerate(SURFACE_NAMES):
            y = np.array(surf[k], dtype=float)
            if what.startswith("human"):
                y = np.where(excluded, np.nan, y)
            ax.plot(x, y, color=COLOURS[k], lw=1.1, label=name)
        ax.set(title=what, xlabel="A-line")
    if excluded.any():
        for ax in axes:
            ax.fill_between(x, 0, image.shape[0] - 1, where=excluded,
                            color="red", alpha=0.13, step="mid")
    axes[0].set_ylabel("Depth (px)")
    axes[1].legend(loc="upper right", ncol=2, fontsize=7, framealpha=0.85)
    idx = {n: i for i, n in enumerate(SURFACE_NAMES)}
    good = ~excluded
    parts = []
    for name in SURFACE_NAMES:
        k = idx[name]
        if not (record["surface_edited"][k] and record["surface_visible"][k]
                and record["surface_reliable"][k]):
            continue
        d = float(np.median((v2_surfaces[k] - record["surfaces"][k])[good]) * record["px_um"])
        parts.append(f"{name} {d:+.0f}")
    fig.suptitle(f"{record['scan_id']}  b{record['bscan']:04d}  "
                 f"verdict={record['verdict']}\n"
                 f"revision-2 minus human, median um (drawn boundaries only): "
                 + "  ".join(parts))
    fig.savefig(out_path, dpi=140, facecolor="white")
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", default="../outputs/eight_surface/labels")
    parser.add_argument("--packs", default="../outputs/eight_surface/review")
    parser.add_argument("--segmented", default="../outputs/eight_surface/segmented")
    parser.add_argument("--priors", default="auto_seg_8layer_v2/priors_v2.json")
    parser.add_argument("--out-dir",
                        default="../outputs/auto_seg_8layer_v2/figures/manual_vs_v2")
    parser.add_argument("--verdict", default="corrected",
                        choices=("corrected", "all"))
    args = parser.parse_args()

    records = L.load_labels(args.labels)
    if args.verdict == "corrected":
        records = [r for r in records if r["verdict"] == "corrected"]
    by_scan = defaultdict(list)
    for record in records:
        by_scan[record["scan_id"]].append(record)

    priors = load_priors_v2(Path(args.priors))
    print("priors: " + ", ".join(f"{k}={v:.4f}" for k, v in priors.items()))
    predictions = run_v2_on_labelled(by_scan, Path(args.segmented), priors)

    images = pack_images(Path(args.packs))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for record in records:
        key = (record["scan_id"], record["bscan"])
        if key not in predictions:
            continue
        v2_surf, _conf, _shadow = predictions[key]
        image = images.get(key)
        if image is None:
            print(f"  no packed image for {key}; skipping render")
            continue
        name = f"{record['scan_id']}_b{record['bscan']:04d}_manual_vs_v2.png"
        render(record, image, v2_surf, out_dir / name)
        written.append(name)
        print(f"  wrote {name}")
    print(f"\n{len(written)} side-by-side figures in {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
