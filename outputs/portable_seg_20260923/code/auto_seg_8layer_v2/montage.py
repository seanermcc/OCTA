#!/usr/bin/env python3
"""Contact sheet of the 20 QC-decile example figures, in decile order."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.image as mpimg
import matplotlib.pyplot as plt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fig-dir",
                        default="../outputs/auto_seg_8layer_v2/figures/qc_examples")
    parser.add_argument("--out",
                        default="../outputs/auto_seg_8layer_v2/figures/qc_examples_contact_sheet.png")
    parser.add_argument("--mode", choices=("qc", "manual"), default="qc")
    parser.add_argument("--cols", type=int, default=2)
    parser.add_argument("--title", default=None)
    args = parser.parse_args()

    fig_dir = Path(args.fig_dir)
    if args.mode == "qc":
        with (fig_dir / "examples_manifest.csv").open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        rows.sort(key=lambda r: (int(r["held_out_decile"]), r["kind"] != "median"))
        titles = [
            f"decile {r['held_out_decile']} ({r['kind']}) | "
            f"qc {float(r['qc_score']):.1f} "
            f"(dataset pct {float(r['qc_score_percentile_dataset']):.1f}) | "
            f"{r['scan_id']} b{int(r['bscan']):04d}"
            for r in rows]
        files = [fig_dir / r["figure"] for r in rows]
        default_title = ("Revision-2 automatic eight-boundary segmentation, 16 "
                         "held-out volumes, spread over acquisition QC score")
    else:
        files = sorted(fig_dir.glob("*_manual_vs_v2.png"))
        titles = [p.stem.replace("_manual_vs_v2", "") for p in files]
        default_title = ("Human hand-drawn labels (left) vs revision-2 automatic "
                         "(right), all corrected B-scans")

    n = len(files)
    rows_n = -(-n // args.cols)
    fig, axes = plt.subplots(rows_n, args.cols, figsize=(15 * args.cols, 5.2 * rows_n),
                             constrained_layout=True, squeeze=False)
    for ax, path, title in zip(axes.ravel(), files, titles):
        ax.imshow(mpimg.imread(path))
        ax.set_axis_off()
        ax.set_title(title, fontsize=11)
    for ax in axes.ravel()[len(files):]:
        ax.set_axis_off()
    fig.suptitle(args.title or default_title, fontsize=20)
    fig.savefig(args.out, dpi=50, facecolor="white")
    plt.close(fig)
    print(f"wrote {args.out}  ({n} panels)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
