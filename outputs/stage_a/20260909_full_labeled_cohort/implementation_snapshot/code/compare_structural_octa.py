#!/usr/bin/env python3
"""Render paired structural-OCT and stored-OCTA projections across QC tiers.

The stored ``frame_OCTAAvg`` channel is shown exactly as it is in the linked
CNV editor: a log-domain mean through the detected retina.  It is a repeated
B-scan change-contrast product, not a calibrated flow-speed map.  The quality
tiers come from structural/acquisition QC and do not themselves rate OCTA.

Run from ``code`` with the ``octa`` environment active::

    python compare_structural_octa.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

CODE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CODE_DIR))

from octa.volio import ProcessedVolume, VolumeReadError  # noqa: E402
from octa.segment import detect_orientation, prepare_bscan  # noqa: E402


DEFAULT_QUALITY = Path("../outputs/scan_quality_ranked.csv")
DEFAULT_OUT = Path("../outputs/figures/structural_vs_octa_qc_tiers.png")
DEFAULT_BSCAN_OUT = Path("../outputs/figures/structural_vs_octa_middle_bscans_qc_tiers.png")
# Three examples at each structural/acquisition QC tier.
TARGET_PERCENTILES = (95.0, 90.0, 85.0, 55.0, 50.0, 45.0, 15.0, 10.0, 5.0)
ROW_NAMES = ("High", "Middle", "Low")


def _select_examples(frame: pd.DataFrame) -> list[pd.Series]:
    valid = frame[(frame["status"] == "ok") & frame["source"].map(
        lambda value: Path(str(value)).is_file())].copy()
    if len(valid) < len(TARGET_PERCENTILES):
        raise ValueError("fewer than nine readable processed volumes are available")
    selected: list[pd.Series] = []
    used: set[str] = set()
    for target in TARGET_PERCENTILES:
        pool = valid[~valid["scan_id"].isin(used)].copy()
        pool["distance"] = (pool["qc_score_percentile"] - target).abs()
        row = pool.sort_values(["distance", "qc_score_percentile"]).iloc[0]
        selected.append(row)
        used.add(str(row["scan_id"]))
    return selected


def _mean_db(volume: np.ndarray) -> np.ndarray:
    """The same dB projection used by the linked CNV annotation GUI."""
    return (20.0 * np.log10(np.maximum(volume, 1e-3)).mean(axis=2)).astype(np.float32)


def _limits(image: np.ndarray) -> tuple[float, float]:
    finite = image[np.isfinite(image)]
    low, high = np.percentile(finite, (1.0, 99.0))
    return float(low), float(high if high > low else low + 1.0)


def _read_pair(row: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    source = Path(str(row["source"]))
    lo, hi = int(row["retina_lo"]), int(row["retina_hi"])
    with ProcessedVolume(source) as volume:
        if volume.angio is None:
            raise VolumeReadError("no frame_OCTAAvg channel")
        if tuple(volume.struct.shape[:2]) != tuple(volume.angio.shape[:2]):
            raise VolumeReadError("structural and OCTA grids do not align")
        hi = min(hi, int(volume.struct.shape[2]), int(volume.angio.shape[2]))
        if lo < 0 or hi <= lo:
            raise ValueError(f"invalid retina band [{lo}, {hi})")
        structural = volume.read_volume("struct", depth_slice=slice(lo, hi))
        octa = volume.read_volume("angio", depth_slice=slice(lo, hi))
    return _mean_db(structural), _mean_db(octa)


def _read_middle_bscan_pair(row: pd.Series) -> tuple[np.ndarray, np.ndarray, int]:
    """Read the middle native B-scan from both aligned channels.

    A single B-scan is deliberately used here because this is a small static
    comparison (one row per volume), not a volume-processing loop.  Its
    orientation is derived afresh from structural data; the OCTA channel uses
    that same acquisition orientation.
    """
    source = Path(str(row["source"]))
    lo, hi = int(row["retina_lo"]), int(row["retina_hi"])
    with ProcessedVolume(source) as volume:
        if volume.angio is None:
            raise VolumeReadError("no frame_OCTAAvg channel")
        if tuple(volume.struct.shape[:2]) != tuple(volume.angio.shape[:2]):
            raise VolumeReadError("structural and OCTA grids do not align")
        index = int(volume.struct.shape[0]) // 2
        structural_raw = volume.bscan(index, "struct")
        octa_raw = volume.bscan(index, "angio")
        hi = min(hi, structural_raw.shape[1], octa_raw.shape[1])
        if lo < 0 or hi <= lo:
            raise ValueError(f"invalid retina band [{lo}, {hi})")
        vitreous_at_high_index = detect_orientation(structural_raw.mean(axis=0))
    return (
        prepare_bscan(structural_raw[:, lo:hi], vitreous_at_high_index),
        prepare_bscan(octa_raw[:, lo:hi], vitreous_at_high_index),
        index,
    )


def build_figure(rows: list[pd.Series], output: Path) -> Path:
    figure, axes = plt.subplots(3, 6, figsize=(18, 9.5), constrained_layout=True)
    figure.suptitle(
        "Paired structural OCT and stored OCTA across structural/acquisition QC tiers\n"
        "Each OCTA panel is a full-retina, log-domain projection; it is not a flow-speed map.",
        fontsize=14,
    )
    for index, row in enumerate(rows):
        group, within = divmod(index, 3)
        col = within * 2
        structural, octa = _read_pair(row)
        descriptor = (
            f"{row['scan_id']}\nQC {row['qc_score_percentile']:.1f}th pct | "
            f"CNR {row['retina_cnr']:.1f}")
        for axis, image, channel in (
                (axes[group, col], structural, "Structural OCT"),
                (axes[group, col + 1], octa, "Stored OCTA")):
            low, high = _limits(image)
            axis.imshow(image, cmap="gray", vmin=low, vmax=high,
                        interpolation="nearest")
            axis.set_axis_off()
            axis.set_title(f"{channel}\n{descriptor}", fontsize=7.8)
        axes[group, 0].set_ylabel(
            f"{ROW_NAMES[group]}\nQC tier", fontsize=11, rotation=0,
            labelpad=48, va="center")
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=180, facecolor="white")
    plt.close(figure)
    return output


def build_bscan_figure(rows: list[pd.Series], output: Path) -> Path:
    figure, axes = plt.subplots(3, 6, figsize=(18, 8.3), constrained_layout=True)
    figure.suptitle(
        "Middle B-scan: structural OCT and stored OCTA across structural/acquisition QC tiers\n"
        "The OCTA view is repeated-scan motion contrast, not a flow-speed map.",
        fontsize=14,
    )
    for index, row in enumerate(rows):
        group, within = divmod(index, 3)
        col = within * 2
        structural, octa, bscan_index = _read_middle_bscan_pair(row)
        descriptor = (
            f"{row['scan_id']}\nB-scan {bscan_index} | "
            f"QC {row['qc_score_percentile']:.1f}th pct")
        for axis, image, channel in (
                (axes[group, col], structural, "Structural OCT"),
                (axes[group, col + 1], octa, "Stored OCTA")):
            low, high = _limits(image)
            axis.imshow(image, cmap="gray", vmin=low, vmax=high,
                        interpolation="nearest", aspect="auto")
            axis.set_axis_off()
            axis.set_title(f"{channel}\n{descriptor}", fontsize=7.8)
        axes[group, 0].set_ylabel(
            f"{ROW_NAMES[group]}\nQC tier", fontsize=11, rotation=0,
            labelpad=48, va="center")
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=180, facecolor="white")
    plt.close(figure)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quality", default=str(DEFAULT_QUALITY))
    parser.add_argument("--out", default=None)
    parser.add_argument("--middle-bscans", action="store_true",
                        help="render the middle structural/OCTA B-scan pair per volume")
    args = parser.parse_args()
    rows = _select_examples(pd.read_csv(args.quality))
    print("Selected scans:")
    for row in rows:
        print(f"  {row['scan_id']}  QC percentile={row['qc_score_percentile']:.1f}")
    default_out = DEFAULT_BSCAN_OUT if args.middle_bscans else DEFAULT_OUT
    out = (build_bscan_figure if args.middle_bscans else build_figure)(
        rows, Path(args.out) if args.out else default_out)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
