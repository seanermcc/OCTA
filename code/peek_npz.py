#!/usr/bin/env python3
"""
Look inside a .npz file.

A .npz is just a ZIP archive of numpy arrays -- the standard way Python stores
several labelled numeric arrays in one file. It is not an image and not a
spreadsheet, so nothing on Windows will open it by double-clicking. Rename one to
.zip and you can see the parts inside, but each part is raw numbers with no
header, so that isn't useful on its own either.

This script prints what's in the file and, with --figures, writes PNGs you CAN
just double-click.

    python peek_npz.py "G:\\OCT_TreeShrew\\derived\\slab_TS165_WT.npz"
    python peek_npz.py "...slab_TS165_WT.npz" --figures

--figures writes, next to the .npz:
    <name>_enface.png     the en-face projection
    <name>_bscan###.png   a few B-scans
    <name>_profile.png    mean intensity vs depth
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


def describe(path: Path) -> dict:
    d = np.load(path)
    print(f"{path.name}   ({path.stat().st_size / 1024**2:.1f} MB)")
    print(f"{'array':24s} {'shape':20s} {'dtype':10s}  summary")
    print("-" * 78)
    for k in d.files:
        a = d[k]
        if a.dtype.kind in "US":
            summary = str(a.ravel()[0])[:40]
        elif a.size <= 6:
            summary = str(a.ravel())
        else:
            summary = (f"min {np.nanmin(a):.4g}  med {np.nanmedian(a):.4g}  "
                       f"max {np.nanmax(a):.4g}")
        print(f"{k:24s} {str(a.shape):20s} {str(a.dtype):10s}  {summary}")
    return d


def figures(d, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    stem = path.with_suffix("")

    if "enface" in d.files:
        e = d["enface"]
        lo, hi = np.percentile(e, [1, 99.5])
        plt.figure(figsize=(7, 7))
        plt.imshow(e, cmap="gray", vmin=lo, vmax=hi)
        plt.title("en-face projection"); plt.xlabel("A-line"); plt.ylabel("B-scan")
        plt.tight_layout(); plt.savefig(f"{stem}_enface.png", dpi=120); plt.close()
        print(f"wrote {stem}_enface.png")

    cube_key = "slab" if "slab" in d.files else ("block" if "block" in d.files else None)
    if cube_key:
        cube = d[cube_key]
        picks = np.linspace(0, cube.shape[0] - 1, 3).astype(int)
        for i in picks:
            img = 20 * np.log10(np.maximum(cube[i], 1e-3)).T
            lo, hi = np.percentile(img, [5, 99.7])
            plt.figure(figsize=(10, 5))
            plt.imshow(img, cmap="gray", vmin=lo, vmax=hi, aspect="auto")
            plt.title(f"{cube_key} B-scan {i} (dB)")
            plt.xlabel("A-line"); plt.ylabel("depth px")
            plt.tight_layout()
            plt.savefig(f"{stem}_bscan{i:03d}.png", dpi=120); plt.close()
            print(f"wrote {stem}_bscan{i:03d}.png")

    if "profile" in d.files:
        p = d["profile"]
        plt.figure(figsize=(10, 4))
        plt.plot(p, lw=1.4)
        plt.xlabel("depth pixel"); plt.ylabel("mean intensity")
        plt.title("mean intensity vs depth"); plt.grid(alpha=.3)
        plt.tight_layout(); plt.savefig(f"{stem}_profile.png", dpi=120); plt.close()
        print(f"wrote {stem}_profile.png")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("--figures", action="store_true",
                    help="also write PNGs you can open by double-clicking")
    args = ap.parse_args()
    p = Path(args.path)
    if not p.is_file():
        print(f"no such file: {p}")
        return 2
    d = describe(p)
    if args.figures:
        print()
        figures(d, p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
