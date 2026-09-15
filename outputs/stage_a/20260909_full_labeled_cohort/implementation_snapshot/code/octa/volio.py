"""
Reading the pipeline's `*_processedVolumes.mat` files from Python.

Those files are MATLAB v7.3, which is HDF5 underneath, so `h5py` opens them
directly with no MATLAB involved. Two things to know:

1. **Axis order is reversed.** MATLAB stores `frame_3DAvg` as
   [depth x A-line x B-scan] = 1024 x 512 x 512. HDF5 writes it in C order, so
   h5py reports the shape as (512 B-scan, 512 A-line, 1024 depth). We always
   return arrays in the h5py order and name the axes explicitly, because
   silently transposing a 2 GB array is a good way to run out of memory.

2. **Slicing one B-scan at a time is a trap, not an optimisation.** These
   files are written chunked as `(n_bscan, 16, 1)` -- every chunk spans the
   FULL B-scan axis. So `f['frame_3DAvg'][i]` still has to decompress the
   exact same complete set of chunks as reading the whole array; it just
   throws away 511/512 B-scans of what it decompressed. Looping `ds[i]` over
   512 B-scans therefore pays that decompression cost 512 times instead of
   once -- measured at ~9s/B-scan, ~78 minutes for one volume, versus ~13s to
   read the entire 2 GB array in one bulk call. There is no in-between: any
   read touching most of the B-scan/A-line range costs about the same
   whether it returns 1 B-scan or all 512, because the chunk boundaries don't
   split along that axis. Use `ProcessedVolume.read_volume()` for anything
   that needs more than a couple of B-scans, and treat `bscan()` as suitable
   only for grabbing one or two.

Orientation: the acquisition pipeline saves the volume with the choroid at low
depth index and the vitreous at high depth index (the `flipud` in
`newOCTA_processing_unbalance_batch.m` happens *after* the save). We detect it
from the data rather than assuming, because it is exactly the kind of thing that
silently flips between datasets.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

try:
    import h5py
    _H5PY_ERROR = None
except Exception as _e:  # ImportError, or a Windows DLL load failure
    h5py = None
    _H5PY_ERROR = _e

STRUCT_KEY = "frame_3DAvg"
ANGIO_KEY = "frame_OCTAAvg"


class VolumeReadError(RuntimeError):
    pass


def _require_h5py():
    if h5py is not None:
        return
    import sys as _sys
    kind = type(_H5PY_ERROR).__name__
    msg = str(_H5PY_ERROR)

    lines = [
        f"could not import h5py: {kind}: {msg}",
        "",
        f"  python:      {_sys.executable}",
        f"  environment: {os.environ.get('CONDA_DEFAULT_ENV', '(not a conda env)')}",
        "",
    ]
    if "DLL load failed" in msg or "specified module could not be found" in msg.lower():
        lines += [
            "h5py IS installed but its HDF5 libraries will not load. This is a broken",
            "install, not a missing one -- usually a conda/pip mix in the same env.",
            "The reliable fix is a clean environment rather than repairing this one:",
        ]
    elif isinstance(_H5PY_ERROR, ImportError):
        lines += ["h5py is not available to THIS interpreter. Either it was installed",
                  "into a different environment, or the env is not active. Cleanest fix:"]
    else:
        lines += ["h5py failed to import for an unexpected reason. Cleanest fix:"]

    lines += [
        "",
        "  conda create -n octa -c conda-forge python=3.11 h5py numpy scipy "
        "scikit-image matplotlib pandas",
        "  conda activate octa",
        "",
        "then rerun this command. Run  python check_env.py  to diagnose further.",
    ]
    raise VolumeReadError("\n".join(lines))


@dataclass
class VolumeInfo:
    path: Path
    n_bscan: int
    n_aline: int
    n_depth: int
    dtype: str
    vitreous_at_high_index: bool     # True = choroid first, vitreous last
    retina_lo: int                   # depth index, start of retina+choroid band
    retina_hi: int                   # depth index, end (exclusive)

    @property
    def retina_thickness_px(self) -> int:
        return self.retina_hi - self.retina_lo


class ProcessedVolume:
    """Context manager around one `*_processedVolumes.mat`."""

    def __init__(self, path: str | Path):
        _require_h5py()
        self.path = Path(path)
        if not self.path.is_file():
            raise VolumeReadError(f"no such file: {self.path}")
        self._f = h5py.File(self.path, "r")

        missing = [k for k in (STRUCT_KEY,) if k not in self._f]
        if missing:
            raise VolumeReadError(
                f"{self.path.name} does not contain {missing}; "
                f"found {list(self._f.keys())}"
            )
        self.struct = self._f[STRUCT_KEY]
        self.angio = self._f[ANGIO_KEY] if ANGIO_KEY in self._f else None

    # -- lifecycle ---------------------------------------------------------
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        try:
            self._f.close()
        except Exception:
            pass

    # -- shape -------------------------------------------------------------
    @property
    def shape(self):
        """(n_bscan, n_aline, n_depth)."""
        return self.struct.shape

    # -- sampling ----------------------------------------------------------
    def bscan(self, i: int, channel: str = "struct") -> np.ndarray:
        """One B-scan as [A-line x depth] float32.

        Costs the same as `read_volume()` under the hood (see module
        docstring) -- fine for grabbing one or two B-scans, a bad choice in
        a loop.
        """
        ds = self.struct if channel == "struct" else self.angio
        if ds is None:
            raise VolumeReadError(f"channel {channel!r} not present")
        return np.asarray(ds[i], dtype=np.float32)

    def read_volume(self, channel: str = "struct",
                    depth_slice: Optional[slice] = None) -> np.ndarray:
        """
        Read (B-scan, A-line, depth) in ONE bulk h5py call.

        This is the fast path -- see the module docstring. Narrowing
        `depth_slice` helps (depth chunks are 1 px each, so it directly
        reduces the number of chunks touched); narrowing which B-scans you
        ask for does NOT help, since B-scan chunks span the full axis.
        """
        ds = self.struct if channel == "struct" else self.angio
        if ds is None:
            raise VolumeReadError(f"channel {channel!r} not present")
        arr = ds[:, :, depth_slice] if depth_slice is not None else ds[:]
        return np.asarray(arr, dtype=np.float32)

    def depth_profile(self, stride: int = 32) -> np.ndarray:
        """
        Mean intensity vs depth, averaged over a strided subset of B-scans.

        Does one bulk `read_volume()` rather than looping `bscan(i)` per
        stride step -- see the module docstring: `stride` doesn't reduce disk
        cost here (B-scan chunk boundaries don't split), so looping only
        bought a smaller decompression-times-N bill, not a smaller one.
        """
        full = self.read_volume(channel="struct")
        idx = list(range(0, full.shape[0], max(1, stride)))
        return full[idx].mean(axis=(0, 1))

    def enface_mean(self, channel: str = "struct", stride: int = 1,
                    depth_slice: Optional[slice] = None) -> np.ndarray:
        """Depth-averaged en-face projection, [B-scan x A-line]."""
        ds = self.struct if channel == "struct" else self.angio
        if ds is None:
            raise VolumeReadError(f"channel {channel!r} not present")
        n = ds.shape[0]
        rows = []
        for i in range(0, n, max(1, stride)):
            b = np.asarray(ds[i], dtype=np.float32)
            if depth_slice is not None:
                b = b[:, depth_slice]
            rows.append(b.mean(axis=1))
        return np.stack(rows, axis=0)


# --------------------------------------------------------------------------
# Retina band detection
# --------------------------------------------------------------------------

def _runs(mask: np.ndarray):
    """Yield (start, stop) of contiguous True runs."""
    lo = None
    for i, v in enumerate(np.append(mask, False)):
        if v and lo is None:
            lo = i
        elif not v and lo is not None:
            yield lo, i
            lo = None


def _close(mask: np.ndarray, max_gap: int) -> np.ndarray:
    """Binary closing along 1-D: fill False gaps shorter than `max_gap`."""
    out = mask.copy()
    for lo, hi in _runs(~mask):
        if lo > 0 and hi < mask.size and (hi - lo) < max_gap:
            out[lo:hi] = True
    return out


def find_retina_band(profile: np.ndarray, pad: int = 40,
                     rel_thresh: float = 0.20,
                     max_gap: int = 90) -> tuple[int, int, bool]:
    """
    Locate the depth range containing retina + choroid from a mean depth profile.

    The profile has a broad elevated region (tissue) and a long low plateau
    (vitreous / empty space). Thresholding alone is not enough: in tree shrew
    vis-OCT the ONL is dark enough to dip below any threshold that also excludes
    the vitreous, which splits the tissue band in two and makes a naive
    "largest run" rule return only the inner retina. So we close gaps shorter
    than `max_gap` before taking the largest run.

    Returns (lo, hi, vitreous_at_high_index).
    """
    p = np.asarray(profile, dtype=np.float64)
    n = p.size

    # The vitreous floor is a robust low quantile rather than the min, which can
    # be a zero-padding artefact at an edge.
    floor = np.percentile(p, 10)
    peak = np.percentile(p, 99.5)
    if peak <= floor:
        raise VolumeReadError("depth profile is flat; cannot locate retina")

    mask = _close(p > (floor + rel_thresh * (peak - floor)), max_gap)

    runs = list(_runs(mask))
    if not runs:
        raise VolumeReadError("no tissue band found in depth profile")
    best_lo, best_hi = max(runs, key=lambda r: r[1] - r[0])

    # Which side is vitreous? Compare mean intensity outside the band.
    above = p[:best_lo].mean() if best_lo > 5 else np.inf
    below = p[best_hi:].mean() if best_hi < n - 5 else np.inf
    vitreous_high = below < above

    return max(0, best_lo - pad), min(n, best_hi + pad), bool(vitreous_high)


def probe(path: str | Path, stride: int = 32, pad: int = 40) -> VolumeInfo:
    """Open a volume, measure its shape and retina band, close it."""
    with ProcessedVolume(path) as v:
        nb, na, nd = v.shape
        prof = v.depth_profile(stride=stride)
        lo, hi, vit_high = find_retina_band(prof, pad=pad)
        return VolumeInfo(
            path=Path(path), n_bscan=nb, n_aline=na, n_depth=nd,
            dtype=str(v.struct.dtype),
            vitreous_at_high_index=vit_high, retina_lo=lo, retina_hi=hi,
        )
