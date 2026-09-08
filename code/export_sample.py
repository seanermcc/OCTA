#!/usr/bin/env python3
"""
Pull a small, representative sample out of one `*_processedVolumes.mat` so the
segmentation algorithm can be developed against real float data instead of the
8-bit display TIFFs.

The full volume is ~2 GB of float64 and cannot be moved off your machine. This
writes a ~40 MB .npz containing:

    block       32 consecutive B-scans (tests depth-direction consistency)
    spread      24 B-scans evenly spaced through the volume (tests robustness
                across the whole field, including near the ONH and vessels)
    enface      full-field depth-averaged structural projection, 512 x 512
    enface_octa same for the angiography channel
    profile     mean intensity vs depth
    meta        shape, dtype, detected retina band, orientation

Depth is cropped to the detected retina+choroid band, which is what makes the
file small: ~300 of 1024 depth pixels carry all the signal.

Usage
-----
    # by explicit path
    python export_sample.py --volumes "G:/OCT_TreeShrew/OCTA_RawData/<session>/<scan>_Processed/<scan>_processedVolumes.mat"

    # or let it find one from the index
    python export_sample.py --index "G:/OCT_TreeShrew/derived/scan_index.csv" --animal TS267 --day 0 --eye OD

Output goes to --out (default: ./octa_sample_<scanname>.npz).

Requires h5py:  conda install -c conda-forge h5py
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from octa.volio import ProcessedVolume, find_retina_band, VolumeReadError  # noqa: E402


def pick_from_index(index_csv: Path, animal: str | None, day: str | None,
                    eye: str | None) -> Path:
    rows = list(csv.DictReader(index_csv.open(encoding="utf-8")))
    cand = [r for r in rows if r["has_volumes"] == "True"]
    if animal:
        cand = [r for r in cand if r["animal"].upper() == animal.upper()]
    if day is not None:
        cand = [r for r in cand if str(r["day"]) == str(day)]
    if eye:
        cand = [r for r in cand if r["eye"].upper() == eye.upper()]
    if not cand:
        raise SystemExit("no acquisition in the index matches those filters")
    r = cand[0]
    session = Path(r["raw_path"]).parent if r["raw_path"] else None
    if session is None:
        raise SystemExit("matched row has no raw_path; pass --volumes explicitly")
    pdir = session / r["processed_dir"]
    hits = list(pdir.glob("*_processedVolumes.mat"))
    if not hits:
        raise SystemExit(f"no processedVolumes.mat in {pdir}")
    print(f"selected {r['animal']} {r['eye']} day {r['day']}  ({r['session_folder']})")
    return hits[0]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--volumes", help="path to a *_processedVolumes.mat")
    src.add_argument("--index", help="scan_index.csv, used with --animal/--day/--eye")
    ap.add_argument("--animal", help="e.g. TS267 (used with --index)")
    ap.add_argument("--day", help="e.g. 0 (used with --index)")
    ap.add_argument("--eye", help="OD or OS (used with --index)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--n-block", type=int, default=32,
                    help="consecutive B-scans to export (default 32)")
    ap.add_argument("--n-spread", type=int, default=24,
                    help="evenly spaced B-scans to export (default 24)")
    ap.add_argument("--block-center", type=int, default=None,
                    help="center B-scan for the consecutive block "
                         "(default: middle of the volume; set this to a lesion)")
    ap.add_argument("--pad", type=int, default=48,
                    help="depth padding around the detected retina band")
    ap.add_argument("--slab", action="store_true",
                    help="export EVERY B-scan at reduced A-line sampling instead of "
                         "a block plus spread. Use this to study anything that "
                         "varies along the slow axis (B-scan averaging, 3D "
                         "regularisation), which a 32-B-scan block cannot show.")
    ap.add_argument("--aline-stride", type=int, default=2,
                    help="with --slab: keep every Nth A-line (default 2, ~215 MB)")
    args = ap.parse_args()

    if args.volumes:
        vpath = Path(args.volumes)
    else:
        vpath = pick_from_index(Path(args.index), args.animal, args.day, args.eye)

    try:
        v = ProcessedVolume(vpath)
    except VolumeReadError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    with v:
        nb, na, nd = v.shape
        print(f"{vpath.name}\n  shape (B-scan, A-line, depth) = {v.shape}, dtype {v.struct.dtype}")

        print("  scanning depth profile ...", flush=True)
        profile = v.depth_profile(stride=16)
        lo, hi, vit_high = find_retina_band(profile, pad=args.pad)
        print(f"  retina band: depth[{lo}:{hi}]  ({hi - lo} px of {nd}); "
              f"vitreous at {'high' if vit_high else 'low'} depth index")

        dsl = slice(lo, hi)

        if args.slab:
            st = max(1, args.aline_stride)
            print(f"  slab mode: all {nb} B-scans, every {st} A-line(s) ...", flush=True)
            slab = np.stack([v.bscan(i)[::st, dsl] for i in range(nb)])
            enface = v.enface_mean("struct", depth_slice=dsl)
            out = (Path(args.out) if args.out
                   else Path.cwd() / f"octa_slab_{vpath.stem}.npz")
            np.savez_compressed(
                out,
                slab=slab.astype(np.float32),
                aline_stride=np.array([st], dtype=np.int32),
                enface=enface.astype(np.float32),
                profile=profile.astype(np.float32),
                shape=np.array([nb, na, nd], dtype=np.int32),
                retina_band=np.array([lo, hi], dtype=np.int32),
                vitreous_at_high_index=np.array([vit_high]),
                source=np.array([str(vpath)]),
            )
            mb = out.stat().st_size / 1024 ** 2
            print(f"\nwrote {out}  ({mb:.1f} MB, slab {slab.shape})")
            if mb > 350:
                print("  NOTE: too large to transfer; rerun with --aline-stride 4.")
            return 0

        center = args.block_center if args.block_center is not None else nb // 2
        b0 = max(0, min(nb - args.n_block, center - args.n_block // 2))
        block_idx = np.arange(b0, b0 + args.n_block)
        spread_idx = np.unique(np.linspace(0, nb - 1, args.n_spread).astype(int))

        print(f"  extracting block B-scans {block_idx[0]}..{block_idx[-1]} "
              f"and {len(spread_idx)} spread B-scans ...", flush=True)
        block = np.stack([v.bscan(int(i))[:, dsl] for i in block_idx])
        spread = np.stack([v.bscan(int(i))[:, dsl] for i in spread_idx])

        block_a = spread_a = None
        if v.angio is not None:
            block_a = np.stack([v.bscan(int(i), "angio")[:, dsl] for i in block_idx])
            spread_a = np.stack([v.bscan(int(i), "angio")[:, dsl] for i in spread_idx])

        print("  building en-face projections (reads the whole volume once) ...", flush=True)
        enface = v.enface_mean("struct", depth_slice=dsl)
        enface_octa = (v.enface_mean("angio", depth_slice=dsl)
                       if v.angio is not None else np.zeros_like(enface))

    out = Path(args.out) if args.out else Path.cwd() / f"octa_sample_{vpath.stem}.npz"
    payload = dict(
        block=block.astype(np.float32),
        spread=spread.astype(np.float32),
        block_idx=block_idx.astype(np.int32),
        spread_idx=spread_idx.astype(np.int32),
        enface=enface.astype(np.float32),
        enface_octa=enface_octa.astype(np.float32),
        profile=profile.astype(np.float32),
        shape=np.array([nb, na, nd], dtype=np.int32),
        retina_band=np.array([lo, hi], dtype=np.int32),
        vitreous_at_high_index=np.array([vit_high]),
        source=np.array([str(vpath)]),
    )
    if block_a is not None:
        payload["block_angio"] = block_a.astype(np.float32)
        payload["spread_angio"] = spread_a.astype(np.float32)

    np.savez_compressed(out, **payload)
    mb = out.stat().st_size / 1024 ** 2
    print(f"\nwrote {out}  ({mb:.1f} MB)")
    if mb > 350:
        print("  NOTE: that is large; rerun with fewer B-scans if it needs to be "
              "transferred (--n-block 16 --n-spread 12).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
