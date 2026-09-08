#!/usr/bin/env python3
"""Export five representative raw B-scans for each selected scan-QC tier."""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from octa.volio import ProcessedVolume, find_retina_band  # noqa: E402
from octa.segment import detect_orientation, prepare_bscan  # noqa: E402


def export_one(row: dict, out_dir: Path) -> None:
    sid, tier = row["scan_id"], row["example_group"]
    source = Path(row["source"])
    with ProcessedVolume(source) as v:
        full = v.read_volume(channel="struct")
    profile = full.mean(axis=(0, 1))
    orient = detect_orientation(profile)
    lo, hi, _ = find_retina_band(profile)
    picks = np.linspace(round(.1 * (full.shape[0] - 1)), round(.9 * (full.shape[0] - 1)), 5).astype(int)
    imgs = np.stack([prepare_bscan(full[i, :, lo:hi], orient) for i in picks])
    view = np.log1p(np.maximum(imgs, 0))
    vmin, vmax = np.percentile(view, (1, 99.5))
    tier_dir = out_dir / tier
    tier_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(tier_dir / f"{sid}_five_bscans.npz", bscans=imgs, bscan_indices=picks,
                        scan_id=np.array([sid]), qc_score=np.array([float(row["qc_score"])]),
                        qc_percentile=np.array([float(row["qc_score_percentile"])]))
    fig, axes = plt.subplots(5, 1, figsize=(12, 12), constrained_layout=True)
    for ax, img, idx in zip(axes, view, picks):
        ax.imshow(img, cmap="gray", aspect="auto", vmin=vmin, vmax=vmax)
        ax.set_ylabel(f"B {idx}")
        ax.set_xticks([]); ax.set_yticks([])
    fig.suptitle(f"{tier} — {sid}\nQC score {float(row['qc_score']):.1f}/100; percentile {float(row['qc_score_percentile']):.1f}")
    fig.savefig(tier_dir / f"{sid}_five_bscans.png", dpi=150)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--examples", default="../outputs/scan_quality_examples.csv")
    ap.add_argument("--out-dir", default="../outputs/qc_score_examples")
    args = ap.parse_args()
    with Path(args.examples).open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        print(f"exporting {row['example_group']}: {row['scan_id']}", flush=True)
        export_one(row, Path(args.out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
