"""
Dynamic-programming surface finding for OCT B-scans.

The workhorse is `dp_surface`: given a cost image [depth x A-line] it finds the
single depth per A-line that minimises total cost, subject to a hard limit on
how far the surface may move between neighbouring A-lines. That smoothness
constraint is what makes it robust - a vessel shadow can wipe out the evidence
in a column entirely and the surface still crosses it sensibly, because it is
not allowed to jump.

This is the same family of method as the lab's existing `segment_visoct`, but
with two differences that matter for this dataset:

* every surface is found under an explicit ordering constraint relative to the
  surfaces already found, so surfaces *cannot* cross each other. The existing
  `layers_refined_auto.mat` has ILM and NFL/GCL crossing in a large fraction of
  A-lines, which is what makes its RNFL thickness unusable.
* per-A-line confidence is carried through, so downstream analysis can exclude
  columns where the evidence was weak rather than silently averaging garbage.
"""

from __future__ import annotations

import numpy as np

# A cost so large nothing will ever be chosen at it. Used as the sentinel for
# 'inadmissible' in a MINIMISATION, so despite the historical name it acts as
# positive infinity, not negative. Reading it as a negative sentinel inverts
# the meaning of every comparison it takes part in.
BAD_COST = np.float32(1e12)

# Ceiling on `local_confidence`. Real surfaces in this data top out around 2-3,
# so this is a guard against pathology, not a scale -- and it keeps the value
# inside the float16 the batch writer stores it as (max 65504).
CONF_CLIP = np.float32(50.0)


# --------------------------------------------------------------------------
# core
# --------------------------------------------------------------------------

def dp_surface(cost: np.ndarray, max_step: int = 2,
               lo: np.ndarray | None = None,
               hi: np.ndarray | None = None,
               bound_weight: float = 12.0) -> np.ndarray:
    """
    Minimum-cost path across A-lines through `cost` [n_depth, n_col].

    max_step : maximum change in depth between adjacent A-lines, in pixels.
    lo, hi   : optional per-column bounds (inclusive lo, exclusive hi).

    Bounds are enforced as a steep linear penalty rather than a hard mask, and
    that choice is load-bearing. A hard mask can make the problem *infeasible*:
    if the band shifts by more than `max_step` between two adjacent A-lines --
    which happens wherever a vessel shadow disturbs the initial guess -- then no
    admissible path exists at all, every candidate accumulates the same
    saturating penalty, and the traceback returns noise pinned to row 0. A
    penalty of `bound_weight` per pixel of excursion keeps a feasible path
    always available while still costing far more than any real image evidence
    (costs are normalised to roughly +/-1), so the surface hugs the band where
    it can and crosses the impossible spot gracefully.

    Returns an integer depth index per column, shape [n_col].
    """
    cost = np.asarray(cost, dtype=np.float32)
    n_depth, n_col = cost.shape

    work = cost.copy()
    if lo is not None or hi is not None:
        rows = np.arange(n_depth, dtype=np.float32)[:, None]
        pen = np.zeros_like(work)
        if lo is not None:
            pen += np.maximum(0.0, np.asarray(lo, dtype=np.float32)[None, :] - rows)
        if hi is not None:
            pen += np.maximum(0.0, rows - (np.asarray(hi, dtype=np.float32)[None, :] - 1.0))
        work = work + np.float32(bound_weight) * pen

    acc = work[:, 0].copy()
    back = np.empty((n_depth, n_col), dtype=np.int16)
    back[:, 0] = 0

    offsets = np.arange(-max_step, max_step + 1)
    for c in range(1, n_col):
        # cand[k, r] = acc[r - offsets[k]] i.e. coming from depth r-offset
        cand = np.full((offsets.size, n_depth), BAD_COST, dtype=np.float32)
        for k, s in enumerate(offsets):
            if s == 0:
                cand[k] = acc
            elif s > 0:
                cand[k, s:] = acc[:-s]
            else:
                cand[k, :s] = acc[-s:]
        k_best = np.argmin(cand, axis=0)
        acc = cand[k_best, np.arange(n_depth)] + work[:, c]
        back[:, c] = offsets[k_best]

    path = np.empty(n_col, dtype=np.int32)
    path[-1] = int(np.argmin(acc))
    for c in range(n_col - 1, 0, -1):
        path[c - 1] = path[c] - back[path[c], c]
    return np.clip(path, 0, n_depth - 1)


def surface_confidence(cost: np.ndarray, path: np.ndarray,
                       margin: int = 6) -> np.ndarray:
    """
    How distinctive was the chosen depth in each A-line?

    Compares the cost at the chosen surface against the best cost *outside* a
    margin around it, over the whole column.

    CAREFUL: this is a **global** comparison, so for any surface found by a
    banded search it is routinely negative -- and that is correct behaviour,
    not a failure. The whole point of banding the search is that a stronger but
    anatomically wrong edge exists elsewhere in the column: the choroid is
    brighter than the RNFL, so the best dark->bright transition in an A-line is
    not the ILM. A negative value here means "a better edge existed elsewhere
    and the band correctly refused it". It says nothing about whether the image
    decided the position *within* the band.

    For "did the image or the prior decide?", use `local_confidence`. Reading
    this function's sign as a quality score marks every surface in the cascade
    as unsupported, the ILM included.
    """
    cost = np.asarray(cost, dtype=np.float32)
    n_depth, n_col = cost.shape
    rows = np.arange(n_depth)[:, None]
    masked = cost.copy()
    masked[np.abs(rows - path[None, :]) <= margin] = BAD_COST
    best_elsewhere = masked.min(axis=0)
    chosen = cost[path, np.arange(n_col)]
    conf = best_elsewhere - chosen
    conf[~np.isfinite(conf)] = 0.0
    return conf.astype(np.float32)


def local_confidence(cost: np.ndarray, path: np.ndarray,
                     halfwidth: int = 8, margin: int = 2) -> np.ndarray:
    """
    Did the image decide this surface's depth, or did the prior?

    Looks only inside the band the search could actually have chosen from:
    compares the cost at the chosen depth against the typical cost in a
    +/-`halfwidth` neighbourhood, in units of that neighbourhood's own spread.

        conf = (median(ring) - cost[chosen]) / MAD(ring)

    where `ring` is the window excluding +/-`margin` around the chosen depth.

      >~ 1    the chosen depth is a distinct local minimum: the image decided
      ~  0    the cost is flat across the window: the prior and the smoothness
              term decided, and the surface carries no local evidence

    Normalising by the MAD is what makes the number comparable across surfaces:
    the gradient and intensity cost images have quite different scales, so an
    unnormalised difference would rank ILM against ELM by units rather than by
    how distinctive each one is.

    This distinction matters because an unsupported surface is not obviously
    wrong to look at. It is smooth, correctly ordered, and sits at an
    anatomically sensible depth, because the prior put it at one. Plotting it
    over a contrast-stretched B-scan will not reveal the problem.
    """
    cost = np.asarray(cost, dtype=np.float32)
    n_depth, n_col = cost.shape
    path = np.clip(np.asarray(path, dtype=int), 0, n_depth - 1)

    offs = np.arange(-halfwidth, halfwidth + 1)
    keep = np.abs(offs) > margin
    rows = np.clip(path[None, :] + offs[keep][:, None], 0, n_depth - 1)
    ring = cost[rows, np.arange(n_col)[None, :]]

    med = np.median(ring, axis=0)
    mad = np.median(np.abs(ring - med[None, :]), axis=0)
    chosen = cost[path, np.arange(n_col)]

    # Where the ring had to be clamped, there is no neighbourhood to compare
    # against and the answer is "no measurement" -- not a huge z-score.
    #
    # Within `halfwidth` of the top or bottom of the image, `np.clip` above
    # folds most of the ring onto the same row, so the MAD collapses toward
    # zero and the ratio explodes. The previous form divided by
    # `1.4826 * mad + 1e-6`, which let those A-lines report confidences in the
    # hundreds or thousands -- BM sitting at the bottom of the recorded depth
    # range measured 2,156 on one A-line here. They overflowed the float16 the
    # batch writer stores confidence in (the visible symptom, a `RuntimeWarning:
    # overflow encountered in cast`) and, less visibly, dominated any mean taken
    # over the surface: one scan ranked 3x higher than every other in the
    # dataset on the strength of a handful of them.
    #
    # BM is the surface this matters most for, and not by accident -- it is
    # clipped at the bottom of the recorded range in some B-scans, which is
    # already why the cascade anchors on the RPE peak instead of on BM.
    valid = (path >= halfwidth) & (path <= n_depth - 1 - halfwidth)

    # A genuinely flat ring away from the edge (a dead or saturated region)
    # carries no evidence either way, and gets the same answer for the same
    # reason. The floor is taken from the cost image's own scale rather than as
    # an absolute epsilon, so it means the same thing whatever units the cost
    # image is in.
    scale = 1.4826 * mad
    ref_scale = np.median(scale[scale > 0]) if np.any(scale > 0) else 0.0
    ok = valid & (scale > 1e-2 * ref_scale) & (scale > 0)
    conf = np.where(ok, (med - chosen) / np.maximum(scale, 1e-12), 0.0)
    conf[~np.isfinite(conf)] = 0.0

    # Backstop only: with the edge and flat-ring cases handled above nothing
    # should reach this, and real surfaces here top out around 2-3.
    np.clip(conf, -CONF_CLIP, CONF_CLIP, out=conf)
    return conf.astype(np.float32)


# --------------------------------------------------------------------------
# cost construction
# --------------------------------------------------------------------------

def _box1d(a: np.ndarray, k: int, axis: int) -> np.ndarray:
    """Box blur along one axis with edge replication.

    Zero-padded convolution ('same') darkens the first and last rows, which
    manufactures a huge intensity gradient at the array boundary - and the DP
    then happily snaps every surface onto row 0. Replicating the edge instead
    keeps the boundary gradient at zero, which is the truth.
    """
    if k <= 1:
        return a
    pad = k // 2
    padw = [(0, 0)] * a.ndim
    padw[axis] = (pad, pad)
    ap = np.pad(a, padw, mode="edge")
    c = np.cumsum(ap, axis=axis, dtype=np.float64)
    lead = np.take(c, np.arange(k, c.shape[axis]), axis=axis)
    trail = np.take(c, np.arange(0, c.shape[axis] - k), axis=axis)
    first = np.take(c, np.arange(k - 1, k), axis=axis)
    out = np.concatenate([first, lead - trail], axis=axis) / k
    # trim any off-by-one from odd/even kernels
    sl = [slice(None)] * a.ndim
    sl[axis] = slice(0, a.shape[axis])
    return out[tuple(sl)].astype(np.float32)


def _smooth(img: np.ndarray, sz_depth: int, sz_col: int) -> np.ndarray:
    """Separable box blur, edge-replicated, no scipy dependency."""
    out = np.asarray(img, dtype=np.float32)
    out = _box1d(out, sz_depth, axis=0)
    out = _box1d(out, sz_col, axis=1)
    return out


def gradient_cost(img: np.ndarray, polarity: str = "dark_to_bright",
                  smooth_depth: int = 3, smooth_col: int = 9) -> np.ndarray:
    """
    Cost image favouring an intensity transition of the given polarity, scanning
    in the direction of increasing depth index.

    polarity 'dark_to_bright' finds boundaries like the ILM (vitreous above,
    retina below); 'bright_to_dark' finds boundaries like the outer edge of the
    RPE/choroid complex.
    """
    x = _smooth(np.asarray(img, dtype=np.float32), smooth_depth, smooth_col)
    g = np.gradient(x, axis=0)
    if polarity == "bright_to_dark":
        g = -g
    elif polarity != "dark_to_bright":
        raise ValueError(f"unknown polarity {polarity!r}")
    # normalise per B-scan so costs are comparable across scans
    s = np.percentile(np.abs(g), 99) or 1.0
    return (-g / s).astype(np.float32)


def intensity_cost(img: np.ndarray, want: str = "bright",
                   smooth_depth: int = 3, smooth_col: int = 9) -> np.ndarray:
    """Cost favouring bright (or dark) pixels rather than transitions."""
    x = _smooth(np.asarray(img, dtype=np.float32), smooth_depth, smooth_col)
    s = np.percentile(x, 99) or 1.0
    x = x / s
    return (-x if want == "bright" else x).astype(np.float32)


# --------------------------------------------------------------------------
# geometry helpers
# --------------------------------------------------------------------------

def flatten_to(img: np.ndarray, surface: np.ndarray, target: int) -> np.ndarray:
    """Shift every A-line so `surface` lands on depth `target`."""
    img = np.asarray(img, dtype=np.float32)
    n_depth, n_col = img.shape
    shift = (target - surface).astype(int)
    out = np.zeros_like(img)
    for c in range(n_col):
        s = shift[c]
        if s == 0:
            out[:, c] = img[:, c]
        elif s > 0:
            out[s:, c] = img[:-s, c]
        else:
            out[:s, c] = img[-s:, c]
    return out


def unflatten_surface(surface_flat: np.ndarray, ref_surface: np.ndarray,
                      target: int) -> np.ndarray:
    """Map a surface found in flattened space back to original depth."""
    return surface_flat - (target - ref_surface)


def median_filter1d(x: np.ndarray, k: int) -> np.ndarray:
    """Median filter along the last axis, edge-replicated. Works for any ndim."""
    if k <= 1:
        return x
    x = np.asarray(x)
    pad = k // 2
    padw = [(0, 0)] * x.ndim
    padw[-1] = (pad, pad)
    xp = np.pad(x, padw, mode="edge")
    win = np.lib.stride_tricks.sliding_window_view(xp, k, axis=-1)
    return np.median(win, axis=-1)
