#!/usr/bin/env python3
"""Export QC tables and the 20 review examples for the revision-2 segmentation.

Examples are spread over the **acquisition** QC score from
``outputs/scan_quality_ranked.csv`` -- the independent signal / slow-axis
continuity / repeat-agreement measurement, not a segmentation-derived score.

The 16 held-out volumes do not cover the dataset-wide percentile range: 11 sit
below the 5th percentile, 4 near the 50th and 1 near the 90th.  Requested
deciles are therefore taken *within the held-out set*, and every figure is
annotated with the dataset-wide percentile as well, so neither number is
mistaken for the other.

Two B-scans are shown per decile: the volume's median and its worst B-scan by
segmentation support, so each panel pair shows a typical case and that volume's
hardest one rather than two interchangeable slices.

Run from ``code`` with ``octa`` activated::

    python auto_seg_8layer_v2/export_examples.py
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR))

from octa.volio import ProcessedVolume, find_retina_band  # noqa: E402

from eight_surface.config import LAYER_DEFS, SURFACE_NAMES  # noqa: E402
from eight_surface.review import _suspect_score  # noqa: E402
from eight_surface.segment import detect_orientation, prepare_bscan  # noqa: E402
from eight_surface.volume import thickness_maps  # noqa: E402

PX_UM = 1.12
DECILES = [1, 10, 20, 30, 40, 50, 60, 70, 80, 90]
COLOURS = ["#e6194b", "#3cb44b", "#ffe119", "#4363d8",
           "#f58231", "#911eb4", "#46f0f0", "#f032e6"]


def load_csv(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["scan_id"]: row for row in csv.DictReader(handle)
                if row.get("scan_id")}


def load_qc(path: Path, groups_path: Path) -> dict[str, dict[str, str]]:
    """Acquisition QC rows, with the low/medium/high review stratum merged in.

    ``scan_quality_ranked.csv`` carries the score but not the stratum; the
    stratum was assigned in ``qc_review_groups.csv`` when the review queue was
    built.  Merging here keeps one source for the score and one for the group
    rather than silently reporting a blank.
    """
    qc = load_csv(path)
    if groups_path.exists():
        for scan_id, row in load_csv(groups_path).items():
            if scan_id in qc and row.get("quality_group"):
                qc[scan_id]["quality_group"] = row["quality_group"]
    return qc


def read_images(source: Path):
    """Bulk-read the structural volume once and return canonical B-scans."""
    with ProcessedVolume(source) as volume:
        full = volume.read_volume(channel="struct")
        profile = full.mean(axis=(0, 1))
        lo, hi, _stale = find_retina_band(profile)
        vitreous_at_high_index = detect_orientation(profile)
        band = full[:, :, lo:hi]
    return np.stack([prepare_bscan(b, vitreous_at_high_index) for b in band])


def render(image, surfaces, title: str, subtitle: str, out: Path) -> None:
    finite = image[np.isfinite(image)]
    lo, hi = np.percentile(finite, [2, 99.5]) if finite.size else (0.0, 1.0)
    fig, axes = plt.subplots(1, 2, figsize=(17, 5.8), constrained_layout=True,
                             sharex=True, sharey=True)
    x = np.arange(image.shape[1])
    axes[0].imshow(image, cmap="gray", aspect="auto", vmin=lo, vmax=hi)
    axes[0].set(title="B-scan", xlabel="A-line", ylabel="Depth (px)")
    axes[1].imshow(image, cmap="gray", aspect="auto", vmin=lo, vmax=hi)
    for k, name in enumerate(SURFACE_NAMES):
        axes[1].plot(x, surfaces[k], color=COLOURS[k], lw=1.1, label=name)
    axes[1].set(title="revision-2 automatic eight boundaries", xlabel="A-line")
    axes[1].legend(loc="upper right", ncol=2, fontsize=7, framealpha=0.85)
    fig.suptitle(f"{title}\n{subtitle}", fontsize=10)
    fig.savefig(out, dpi=140, facecolor="white")
    plt.close(fig)


def layer_summary(surfaces, shadow) -> dict[str, float]:
    """Median layer thickness over the whole volume; shadowed A-lines are NaN."""
    maps = thickness_maps(surfaces, shadow, px_um=PX_UM)
    return {name: (float(np.nanmedian(maps[name]))
                   if np.isfinite(maps[name]).any() else float("nan"))
            for name, _t, _b in LAYER_DEFS}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--segmented", default="../outputs/auto_seg_8layer_v2/segmented")
    parser.add_argument("--qc", default="../outputs/scan_quality_ranked.csv")
    parser.add_argument("--groups", default="../outputs/eight_surface/qc_review_groups.csv")
    parser.add_argument("--out-dir", default="../outputs/auto_seg_8layer_v2")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    fig_dir = out_dir / "figures" / "qc_examples"
    fig_dir.mkdir(parents=True, exist_ok=True)
    qc = load_qc(Path(args.qc), Path(args.groups))

    paths = sorted(Path(args.segmented).glob("*.npz"))
    paths = [p for p in paths if p.name != "batch_log.csv"]
    if not paths:
        print(f"no revision-2 outputs in {args.segmented}")
        return 1

    # Pass 1: per-volume segmentation summary and per-B-scan suspect scores.
    volumes = []
    for path in paths:
        with np.load(path, allow_pickle=False) as data:
            scan_id = str(data["scan_id"][0])
            surfaces = data["surfaces"].astype(np.float32)
            confidence = data["confidence"].astype(np.float32)
            shadow = data["shadow"].astype(bool)
            source = Path(str(data["source"][0]))
            notes = [str(x) for x in data["notes"] if str(x)]
        score, parts = _suspect_score(surfaces, confidence, shadow, PX_UM)
        row = qc.get(scan_id, {})
        volumes.append({
            "scan_id": scan_id, "path": path, "source": source,
            "surfaces": surfaces, "shadow": shadow, "score": score,
            "parts": parts, "notes": notes,
            "qc_score": float(row["qc_score"]) if row.get("qc_score") else float("nan"),
            "qc_pct_dataset": (float(row["qc_score_percentile"])
                               if row.get("qc_score_percentile") else float("nan")),
            "quality_group": row.get("quality_group", ""),
        })
    volumes.sort(key=lambda v: v["qc_score"])

    # Per-volume QC/thickness table.
    table_path = out_dir / "qc" / "volume_summary.csv"
    table_path.parent.mkdir(parents=True, exist_ok=True)
    layer_names = [name for name, _t, _b in LAYER_DEFS]
    with table_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["scan_id", "qc_score", "qc_score_percentile_dataset",
                         "quality_group", "n_bscan", "median_suspect_score",
                         "mean_unsupported_frac", "mean_shadow_frac",
                         "mean_implausible_frac", "median_slow_axis_roughness_px",
                         "n_notes"] + [f"median_{n}_um" for n in layer_names])
        for v in volumes:
            summary = layer_summary(v["surfaces"], v["shadow"])
            writer.writerow([
                v["scan_id"], f"{v['qc_score']:.3f}", f"{v['qc_pct_dataset']:.2f}",
                v["quality_group"], v["surfaces"].shape[0],
                f"{np.median(v['score']):.4f}",
                f"{np.mean(v['parts']['unsupported']):.4f}",
                f"{np.mean(v['parts']['shadow_frac']):.4f}",
                f"{np.mean(v['parts']['implausible']):.4f}",
                f"{np.median(v['parts']['roughness']):.2f}",
                len(v["notes"]),
            ] + [f"{summary[n]:.1f}" for n in layer_names])
    print(f"wrote {table_path}")

    # Pass 2: one volume per requested decile of the held-out qc_score.
    n = len(volumes)
    chosen, manifest = [], []
    for pct in DECILES:
        i = int(round(pct / 100.0 * (n - 1)))
        while i in chosen and len(chosen) < n:
            i = (i + 1) % n
        chosen.append(i)
    for pct, i in zip(DECILES, chosen):
        v = volumes[i]
        order = np.argsort(v["score"])
        picks = [("median", int(order[len(order) // 2])),
                 ("worst", int(order[-1]))]
        images = read_images(v["source"])
        for kind, bscan in picks:
            name = (f"pct{pct:02d}_{kind}_{v['scan_id']}_b{bscan:04d}.png")
            render(
                images[bscan], v["surfaces"][bscan],
                f"{v['scan_id']}  |  B-scan {bscan}  ({kind} segmentation support)",
                f"held-out QC decile {pct} of 16 volumes  |  qc_score "
                f"{v['qc_score']:.2f}  |  dataset-wide percentile "
                f"{v['qc_pct_dataset']:.1f}  |  {v['quality_group']} group  |  "
                f"suspect {v['score'][bscan]:.2f}, unsupported "
                f"{v['parts']['unsupported'][bscan]:.2f}, shadow "
                f"{v['parts']['shadow_frac'][bscan]:.2f}",
                fig_dir / name)
            manifest.append({
                "held_out_decile": pct, "kind": kind, "scan_id": v["scan_id"],
                "bscan": bscan, "figure": name,
                "qc_score": f"{v['qc_score']:.3f}",
                "qc_score_percentile_dataset": f"{v['qc_pct_dataset']:.2f}",
                "quality_group": v["quality_group"],
                "suspect_score": f"{v['score'][bscan]:.4f}",
                "unsupported_frac": f"{v['parts']['unsupported'][bscan]:.4f}",
                "implausible_frac": f"{v['parts']['implausible'][bscan]:.4f}",
                "shadow_frac": f"{v['parts']['shadow_frac'][bscan]:.4f}",
                "slow_axis_roughness_px": f"{v['parts']['roughness'][bscan]:.2f}",
            })
            print(f"  pct{pct:02d} {kind:6s} {v['scan_id']} b{bscan:04d}")

    manifest_path = fig_dir / "examples_manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest[0]))
        writer.writeheader()
        writer.writerows(manifest)
    print(f"\n{len(manifest)} figures in {fig_dir}\nwrote {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
