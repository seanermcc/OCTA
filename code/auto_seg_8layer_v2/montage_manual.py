#!/usr/bin/env python3
"""Split the 53 manual-vs-v2 comparison figures into a few contact sheets."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.image as mpimg
import matplotlib.pyplot as plt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fig-dir",
                        default="../outputs/auto_seg_8layer_v2/figures/manual_vs_v2")
    parser.add_argument("--out-prefix",
                        default="../outputs/auto_seg_8layer_v2/figures/manual_vs_v2_sheet")
    parser.add_argument("--per-sheet", type=int, default=18)
    args = parser.parse_args()

    fig_dir = Path(args.fig_dir)
    files = sorted(fig_dir.glob("*_manual_vs_v2.png"))
    n_sheets = -(-len(files) // args.per_sheet)
    for sheet_i in range(n_sheets):
        chunk = files[sheet_i * args.per_sheet: (sheet_i + 1) * args.per_sheet]
        fig, axes = plt.subplots(len(chunk), 1, figsize=(17, 5.9 * len(chunk)),
                                 constrained_layout=True, squeeze=False)
        for ax, path in zip(axes.ravel(), chunk):
            ax.imshow(mpimg.imread(path))
            ax.set_axis_off()
            ax.set_title(path.stem.replace("_manual_vs_v2", ""), fontsize=11)
        fig.suptitle(f"Human labels (left) vs revision-2 automatic (right) "
                     f"-- sheet {sheet_i + 1}/{n_sheets}", fontsize=18)
        out = Path(f"{args.out_prefix}_{sheet_i + 1}of{n_sheets}.png")
        fig.savefig(out, dpi=48, facecolor="white")
        plt.close(fig)
        print(f"wrote {out}  ({len(chunk)} panels)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
