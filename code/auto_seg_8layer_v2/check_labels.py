#!/usr/bin/env python3
"""Render human-corrected eight-boundary labels beside their automatic lines.

This exists to answer one question before any prior is refitted: are the large
median human corrections to RNFL_GCL and GCL_IPL real, or an artefact of how
the correction is measured?  Run from ``code`` with ``octa`` activated.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR))

from eight_surface import labels as L  # noqa: E402
from eight_surface.config import SURFACE_NAMES  # noqa: E402

COLOURS = ["#e6194b", "#3cb44b", "#ffe119", "#4363d8",
           "#f58231", "#911eb4", "#46f0f0", "#f032e6"]


def pack_images(pack_dir: Path) -> dict[tuple[str, int], np.ndarray]:
    """Index every packed B-scan image by (scan_id, B-scan index)."""
    out = {}
    for path in sorted(pack_dir.glob("*_pack.npz")):
        with np.load(path, allow_pickle=False) as pack:
            scan_id = str(pack["scan_id"][0])
            for k, bscan in enumerate(pack["bscan_index"].astype(int)):
                out[(scan_id, int(bscan))] = pack["images"][k].astype(np.float32)
    return out


def render(record, image, out_path: Path) -> None:
    finite = image[np.isfinite(image)]
    lo, hi = np.percentile(finite, [2, 99.5]) if finite.size else (0.0, 1.0)
    fig, axes = plt.subplots(1, 2, figsize=(17, 5.6), constrained_layout=True,
                             sharex=True, sharey=True)
    x = np.arange(image.shape[1])
    excluded = record["region_excluded"]
    for ax, key, what in ((axes[0], "auto_surfaces", "automatic"),
                          (axes[1], "surfaces", "human")):
        ax.imshow(image, cmap="gray", aspect="auto", vmin=lo, vmax=hi)
        for k, name in enumerate(SURFACE_NAMES):
            y = np.array(record[key][k], dtype=float)
            if what == "human":
                # An excluded A-line has no human answer; do not draw one.
                y = np.where(excluded, np.nan, y)
            ax.plot(x, y, color=COLOURS[k], lw=1.1, label=name)
        flags = ""
        if what == "human":
            drawn = [n for k, n in enumerate(SURFACE_NAMES)
                     if record["surface_edited"][k]]
            flags = f"\ndrawn: {', '.join(drawn) if drawn else 'none'}"
        ax.set(title=f"{what}{flags}", xlabel="A-line")
    if excluded.any():
        for ax in axes:
            ax.fill_between(x, 0, image.shape[0] - 1, where=excluded,
                            color="red", alpha=0.13, step="mid")
    axes[0].set_ylabel("Depth (px)")
    axes[1].legend(loc="upper right", ncol=2, fontsize=7, framealpha=0.85)
    fig.suptitle(f"{record['scan_id']}  b{record['bscan']:04d}  "
                 f"verdict={record['verdict']}  "
                 f"{record['seconds_active']:.0f}s  "
                 f"{record['n_strokes']} strokes"
                 + ("  [control]" if record.get("is_control") else ""))
    fig.savefig(out_path, dpi=140, facecolor="white")
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", default="../outputs/eight_surface/labels")
    parser.add_argument("--packs", default="../outputs/eight_surface/review")
    parser.add_argument("--out-dir",
                        default="../outputs/auto_seg_8layer_v2/figures/label_check")
    parser.add_argument("--n", type=int, default=12)
    args = parser.parse_args()

    records = [r for r in L.load_labels(args.labels) if r["verdict"] == "corrected"]
    if not records:
        print("no corrected labels")
        return 1
    images = pack_images(Path(args.packs))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Spread the sample over scans rather than over one heavily reviewed volume.
    by_scan: dict[str, list] = {}
    for record in records:
        by_scan.setdefault(record["scan_id"], []).append(record)
    chosen, round_number = [], 0
    while len(chosen) < min(args.n, len(records)):
        added = False
        for scan_id in sorted(by_scan):
            if round_number < len(by_scan[scan_id]) and len(chosen) < args.n:
                chosen.append(by_scan[scan_id][round_number])
                added = True
        if not added:
            break
        round_number += 1

    for record in chosen:
        key = (record["scan_id"], record["bscan"])
        if key not in images:
            print(f"  no packed image for {key}; skipping")
            continue
        out = out_dir / f"{record['scan_id']}_b{record['bscan']:04d}_check.png"
        render(record, images[key], out)
        print(f"  wrote {out.name}")
    print(f"{len(chosen)} comparison figures in {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
