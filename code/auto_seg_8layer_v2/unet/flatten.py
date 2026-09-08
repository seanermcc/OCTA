"""Integer per-A-line flattening, anchored on the posterior tissue edge.

Why the posterior edge and not the ILM: the ILM is the surface currently known
to fail (``outputs/auto_seg_8layer_v2/REPORT.md``, "A pre-existing ILM
failure"), so anchoring the network's input geometry to it would bake that
failure into every training sample.  ``tissue_bounds``' posterior edge is
independent of the cascade.

Why integer shifts and a circular roll:

* an integer shift makes ``unflatten(flatten(x)) == x`` **exactly**, which is
  a numeric assertion rather than a visual check.  An interpolated shift would
  round-trip only approximately and could hide a bug;
* a circular roll never discards a row, so the round trip is lossless for the
  whole image and not merely for the part that stays in frame.  The wrapped
  rows land far outside the retina and are removed by :func:`crop`, which is a
  separate, explicitly lossy step.

Surface rows are transformed with the same shift array, so anything predicted
in flattened coordinates can be returned to original image coordinates before
it is compared with a human label or written to disk.
"""

from __future__ import annotations

import numpy as np

from octa.segment import tissue_bounds
from octa.surfaces import median_filter1d

# Crop window around the anchor row, in pixels.  Measured on the 53 corrected
# labels and their 3-B-scan averages: the human ILM sits 219-353 px above the
# median posterior tissue edge, and the human RPE between 5 px below it and
# 258 px above it, so 384 above / 64 below contains every labelled surface with
# margin.  ``run_phase1.py`` reprints both ranges on every run, so a new
# labelled volume that breaks the assumption is visible immediately, and
# ``dataset.build_sample`` refuses a sample whose surfaces fall outside.
#
# Retinal bands are 389-648 rows, so a 448-row window is partly padding on the
# short ones; that padding is marked in ``wrap_mask``, zeroed in the input, and
# carries no loss weight.
CROP_ABOVE = 384
CROP_BELOW = 64
EDGE_SMOOTH_COL = 41


def posterior_edge(img: np.ndarray, smooth_col: int = EDGE_SMOOTH_COL) -> np.ndarray:
    """Median-smoothed posterior tissue edge, one row per A-line.

    Smoothed before use so a single-A-line ``tissue_bounds`` glitch cannot tear
    the image.
    """
    img = np.asarray(img)
    if img.ndim != 2:
        raise ValueError(f"expected a [depth, A-line] B-scan, got {img.shape}")
    _first, last = tissue_bounds(img)
    edge = median_filter1d(np.asarray(last, float), smooth_col)
    if not np.all(np.isfinite(edge)):
        raise ValueError("posterior tissue edge contains non-finite values")
    return edge


def flatten_shifts(img: np.ndarray, target_row: int,
                   smooth_col: int = EDGE_SMOOTH_COL) -> np.ndarray:
    """Integer shift per A-line that puts the posterior edge on ``target_row``.

    Positive shift means the column's content moves *up* in the flattened
    image.
    """
    edge = posterior_edge(img, smooth_col=smooth_col)
    return np.rint(edge - float(target_row)).astype(np.int64)


def apply_shifts(img: np.ndarray, shifts: np.ndarray) -> np.ndarray:
    """Flatten: ``out[r, c] = img[(r + shifts[c]) % depth, c]``."""
    img = np.asarray(img)
    shifts = _check_shifts(shifts, img.shape[1])
    n_depth = img.shape[0]
    rows = (np.arange(n_depth)[:, None] + shifts[None, :]) % n_depth
    cols = np.broadcast_to(np.arange(img.shape[1])[None, :], rows.shape)
    return img[rows, cols]


def invert_shifts(flat: np.ndarray, shifts: np.ndarray) -> np.ndarray:
    """Exact inverse of :func:`apply_shifts` on the full-height image."""
    flat = np.asarray(flat)
    shifts = _check_shifts(shifts, flat.shape[1])
    n_depth = flat.shape[0]
    rows = (np.arange(n_depth)[:, None] - shifts[None, :]) % n_depth
    cols = np.broadcast_to(np.arange(flat.shape[1])[None, :], rows.shape)
    return flat[rows, cols]


def shift_rows(rows: np.ndarray, shifts: np.ndarray) -> np.ndarray:
    """Image-coordinate surface rows -> flattened coordinates."""
    rows = np.asarray(rows, float)
    shifts = _check_shifts(shifts, rows.shape[-1])
    return rows - shifts.astype(float)


def unshift_rows(rows: np.ndarray, shifts: np.ndarray) -> np.ndarray:
    """Flattened surface rows -> image coordinates."""
    rows = np.asarray(rows, float)
    shifts = _check_shifts(shifts, rows.shape[-1])
    return rows + shifts.astype(float)


def wrap_mask(shape, shifts: np.ndarray) -> np.ndarray:
    """``[depth, A-line]`` True where a flattened pixel is real, not wrapped.

    The roll is circular so that the round trip is lossless, which means a
    column shifted by more than its own margin brings rows in from the other
    end of the image.  Those pixels are not evidence about the retina and are
    zeroed (and given no loss weight) once the window is cut.
    """
    n_depth, n_col = shape
    shifts = _check_shifts(shifts, n_col)
    source = np.arange(n_depth)[:, None] + shifts[None, :]
    return (source >= 0) & (source < n_depth)


def crop(flat: np.ndarray, target_row: int, above: int = CROP_ABOVE,
         below: int = CROP_BELOW) -> tuple[np.ndarray, int]:
    """Fixed-height window around the anchor row.  Returns ``(window, row0)``.

    This is the only lossy step; it is deliberately separate from the shift so
    the round-trip assertion covers the shift on its own.  Rows outside the
    stored image are zero-padded and the padding amount is checked by the
    caller through ``row0`` and the returned height.
    """
    flat = np.asarray(flat)
    row0 = int(target_row) - int(above)
    row1 = int(target_row) + int(below)
    height = row1 - row0
    out = np.zeros((height,) + flat.shape[1:], dtype=flat.dtype)
    src_lo, src_hi = max(0, row0), min(flat.shape[0], row1)
    if src_hi > src_lo:
        out[src_lo - row0:src_hi - row0] = flat[src_lo:src_hi]
    return out, row0


def _check_shifts(shifts: np.ndarray, n_col: int) -> np.ndarray:
    shifts = np.asarray(shifts)
    if shifts.ndim != 1 or shifts.shape[0] != n_col:
        raise ValueError(
            f"shifts must be one integer per A-line ({n_col}), got {shifts.shape}")
    if not np.issubdtype(shifts.dtype, np.integer):
        raise TypeError(
            "shifts must be an integer array; a fractional shift breaks the "
            "lossless round trip this module guarantees")
    return shifts
