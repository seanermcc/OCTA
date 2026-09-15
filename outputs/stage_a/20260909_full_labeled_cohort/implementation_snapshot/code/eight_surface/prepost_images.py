#!/usr/bin/env python3
"""Create matched pre- and post-manual eight-boundary comparison images.

``pre`` writes exactly one representative automatic B-scan per selected volume
to ``outputs/pre-images_8layer_Gui``.  It chooses the review-pack control B-scan
(nearest that volume's median review score), ensuring the image is also present
in the manual queue.  ``post`` renders the same image after its label exists.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import matplotlib

# This exporter never needs a Qt window.  A raster-only backend avoids loading
# the GUI stack while rendering the pre/post comparison PNGs.
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR))

from eight_surface import labels as L  # noqa: E402
from eight_surface.config import SURFACE_NAMES  # noqa: E402


COLOURS = ["#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231", "#911eb4", "#46f0f0", "#f032e6"]


def _selection(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["scan_id"]: row for row in csv.DictReader(handle) if row.get("scan_id")}


def _render(image, surfaces, title: str, out: Path):
    finite = image[np.isfinite(image)]
    lo, hi = np.percentile(finite, [2, 99.5]) if finite.size else (0, 1)
    fig, ax = plt.subplots(figsize=(12, 6), constrained_layout=True)
    ax.imshow(image, cmap="gray", aspect="auto", vmin=lo, vmax=hi, origin="upper")
    x = np.arange(image.shape[1])
    for k, name in enumerate(SURFACE_NAMES):
        ax.plot(x, surfaces[k], color=COLOURS[k], linewidth=1.2, label=name)
    ax.set(title=title, xlabel="A-line", ylabel="Depth (pixels)")
    ax.legend(loc="upper right", ncol=2, fontsize=7, framealpha=0.80)
    fig.savefig(out, dpi=180, facecolor="white")
    plt.close(fig)


def cmd_pre(args) -> int:
    selection = _selection(Path(args.selection))
    packs = sorted(Path(args.packs).glob("*_pack.npz"))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest, rendered = [], 0
    for pack_path in packs:
        with np.load(pack_path, allow_pickle=False) as pack:
            scan_id = str(pack["scan_id"][0])
            if scan_id not in selection:
                continue
            controls = np.flatnonzero(pack["is_control"].astype(bool))
            if not controls.size:
                print(f"  {pack_path.name}: no control B-scan; skipping")
                continue
            # The pack writes one median-ranked control for this workflow.
            i = int(controls[0])
            bscan = int(pack["bscan_index"][i])
            image = pack["images"][i].astype(float)
            surfaces = pack["surfaces"][i].astype(float)
            row = selection[scan_id]
            name = f"{scan_id}_b{bscan:04d}_pre.png"
            image_path = out_dir / name
            # Resumable rendering is important on Windows: an interrupted
            # export should continue with the next panel, not redraw the
            # entire selection.  The manifest is still written in full.
            if not image_path.exists() and (args.limit is None or rendered < args.limit):
                _render(
                    image, surfaces,
                    f"Pre-manual automatic segmentation | {scan_id} | B-scan {bscan} | "
                    f"QC score {float(row['qc_score']):.3f} ({float(row['qc_score_percentile']):.1f}th pct) | "
                    f"{row['quality_group']} QC",
                    image_path)
                rendered += 1
            manifest.append({
                "scan_id": scan_id, "bscan": bscan, "quality_group": row["quality_group"],
                "qc_score": row["qc_score"], "qc_score_percentile": row["qc_score_percentile"],
                "pack_file": pack_path.name, "pack_item_index": i, "pre_image": name,
            })
    manifest_path = out_dir / "pre_manual_manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "scan_id", "bscan", "quality_group", "qc_score", "qc_score_percentile",
            "pack_file", "pack_item_index", "pre_image"])
        writer.writeheader()
        writer.writerows(manifest)
    print(f"rendered {rendered}; {len(manifest)} pre-manual records in {manifest_path}")
    return 0


def cmd_post(args) -> int:
    pre_dir, packs_dir, labels_dir, out_dir = map(Path, (args.pre_dir, args.packs, args.labels, args.out_dir))
    with (pre_dir / "pre_manual_manifest.csv").open(newline="", encoding="utf-8") as handle:
        manifest = list(csv.DictReader(handle))
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for row in manifest:
        label_path = L.label_path(labels_dir, row["scan_id"], int(row["bscan"]))
        if not label_path.exists():
            continue
        label = L.load_label(label_path)
        with np.load(packs_dir / row["pack_file"], allow_pickle=False) as pack:
            i = int(row["pack_item_index"])
            image = pack["images"][i].astype(float)
        filename = f"{row['scan_id']}_b{int(row['bscan']):04d}_post.png"
        _render(
            image, label["surfaces"],
            f"Post-manual segmentation | {row['scan_id']} | B-scan {row['bscan']} | "
            f"verdict: {label['verdict']} | {row['quality_group']} QC",
            out_dir / filename)
        written += 1
    print(f"wrote {written} post-manual images to {out_dir}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    pre = sub.add_parser("pre")
    pre.add_argument("--packs", default="../outputs/eight_surface/review")
    pre.add_argument("--selection", default="../outputs/eight_surface/qc_review_groups.csv")
    pre.add_argument("--out-dir", default="../outputs/pre-images_8layer_Gui")
    pre.add_argument("--limit", type=int, default=None,
                     help="render at most this many missing panels (resumable)")
    pre.set_defaults(func=cmd_pre)
    post = sub.add_parser("post")
    post.add_argument("--pre-dir", default="../outputs/pre-images_8layer_Gui")
    post.add_argument("--packs", default="../outputs/eight_surface/review")
    post.add_argument("--labels", default="../outputs/eight_surface/labels")
    post.add_argument("--out-dir", default="../outputs/post-images_8layer_Gui")
    post.set_defaults(func=cmd_post)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
