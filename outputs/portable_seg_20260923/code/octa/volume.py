"""
Volume-level (3D) segmentation.

Segmenting each B-scan independently leaves the weak inner surfaces free to land
somewhere slightly different in every slice, which shows up in a thickness map as
vertical streaking that swamps the real anatomy. Two mechanisms fix that, and
they do different jobs:

**B-scan averaging** raises SNR *before* the surfaces are found, so the evidence
itself is stronger. Averaging N adjacent B-scans cuts speckle by roughly sqrt(N)
-- but it also blurs genuine structure along the slow axis, and retinal vessels
are exactly the sharp, localised, real feature that blurring destroys first.
So more is not simply better and the optimum has to be measured.

**Slow-axis refinement** constrains each surface to be continuous *between*
B-scans, the same way the DP already constrains it between A-lines. Pass 1 finds
surfaces independently; the surface maps are then smoothed along the slow axis
and each surface is re-found in a narrow band around that smoothed prior. This is
regularisation, not post-hoc smoothing: the image still decides the final
position, it just cannot disagree wildly with its neighbours.
"""

from __future__ import annotations

import numpy as np

from .segment import (
    N_SURFACES, SURFACE_NAMES, SURFACE_COST,
    build_costs, segment_bscan, enforce_order, prepare_bscan,
    shadow_columns, _interp_over,
)
from .surfaces import dp_surface, median_filter1d, local_confidence

MIN_GAP_PX = 2.0


def average_bscans(imgs: np.ndarray, n: int) -> np.ndarray:
    """
    Rolling mean of `n` adjacent B-scans, edge-clamped so the output has the
    same length as the input.

    Averaging happens in dB (the images are already log-compressed), which is
    the right domain here: speckle is multiplicative in linear amplitude, so it
    is additive in dB and a plain mean is the correct estimator.
    """
    if n <= 1:
        return imgs
    # An even window cannot be centred, so it is taken one slice further back
    # than forward. Using n//2 on each side instead would silently make width 4
    # identical to width 5 and width 6 identical to width 7 -- which is exactly
    # the bug that made an earlier version of this sweep report duplicate rows.
    back = (n - 1) // 2
    fwd = n // 2
    out = np.empty_like(imgs)
    n_b = imgs.shape[0]
    for i in range(n_b):
        lo = max(0, i - back)
        hi = min(n_b, i + fwd + 1)
        out[i] = imgs[lo:hi].mean(axis=0)
    return out


def refine_slow_axis(surfaces: np.ndarray, costs: list[dict],
                     smooth_bscans: int = 5, halfwidth: int = 6,
                     max_step: int = 2, attract: float = 0.0) -> np.ndarray:
    """
    Re-find every surface under a slow-axis prior.

    surfaces : [n_bscan, N_SURFACES, n_col]
    costs    : per-B-scan cost dicts from build_costs
    attract  : if > 0, the prior acts as a *soft* attraction of this many cost
               units per pixel of departure, instead of a hard +/- `halfwidth`
               window. Soft is better for weak boundaries: inside a hard window
               the search can flip between two nearly equal minima from one
               B-scan to the next, which adds jitter rather than removing it -
               that is why the first version of this made RNFL worse, not better.
               A linear pull leaves one global optimum that moves smoothly.
    """
    n_b, n_s, n_col = surfaces.shape
    prior = surfaces.copy()
    for s in range(n_s):
        # median along the B-scan axis, per A-line
        prior[:, s, :] = median_filter1d(
            surfaces[:, s, :].T.astype(np.float64), smooth_bscans).T

    out = np.empty_like(surfaces)
    for i in range(n_b):
        C = costs[i]
        # Surfaces are re-found from the vitreous inward, and each one is bounded
        # below by the surface already refined above it and above by the *prior*
        # of the one below. Without those bounds the refinement is free to let a
        # thin layer's two surfaces converge - which is exactly what made RNFL
        # noisier with refinement on than off, since RNFL/GCL could drift onto
        # the ILM and then get shoved back by enforce_order afterwards.
        prev = None
        for s, name in enumerate(SURFACE_NAMES):
            p = prior[i, s].astype(np.float64)
            cost = C[SURFACE_COST[name]]
            if attract > 0:
                # lo == hi collapses dp_surface's out-of-band penalty into a
                # symmetric linear pull toward the prior, weight `attract` per px.
                found = dp_surface(cost, max_step=max_step, lo=p, hi=p + 1.0,
                                   bound_weight=attract).astype(np.float64)
                if prev is not None:
                    found = np.maximum(found, prev + MIN_GAP_PX)
            else:
                lo = p - halfwidth
                hi = p + halfwidth + 1
                if prev is not None:
                    lo = np.maximum(lo, prev + MIN_GAP_PX)
                if s + 1 < n_s:
                    hi = np.minimum(hi, prior[i, s + 1].astype(np.float64) - MIN_GAP_PX)
                hi = np.maximum(hi, lo + 2)
                found = dp_surface(cost, max_step=max_step, lo=lo, hi=hi)
            out[i, s] = found
            prev = found.astype(np.float64)
        out[i] = enforce_order(out[i])
    return out


def segment_volume(bscans_aline_depth: np.ndarray,
                   vitreous_at_high_index: bool,
                   bscan_avg: int = 5,
                   refine: bool = True,
                   smooth_bscans: int = 5,
                   px_um: float = 1.12,
                   attract: float = 0.05,
                   progress: bool = False):
    """
    Segment a stack of B-scans with 3D consistency.

    `attract` is the soft slow-axis attraction weight and is forwarded to
    `refine_slow_axis`. It defaults to the measured value (0.05) rather than to
    0.0: this function previously had no `attract` parameter at all, so every
    call fell through to `refine_slow_axis`'s own default of 0.0 and silently
    used the hard +/-6 px window instead -- the variant the README records as
    making RNFL *worse* (TOTAL jitter 5.48 um vs 3.33 um for the soft pull).
    `batch_segment.py` was recording attract=0.05 into every output .npz while
    this was happening, so those files' metadata did not describe how they were
    produced. Any output written before this was fixed should be regenerated.

    Returns (surfaces   [n_bscan, N_SURFACES, n_col] float32, depth px,
             confidence [n_bscan, N_SURFACES, n_col] float32,
             shadow     [n_bscan, n_col] bool,
             notes      list[str])
    """
    imgs = np.stack([prepare_bscan(b, vitreous_at_high_index)
                     for b in bscans_aline_depth])
    avg = average_bscans(imgs, bscan_avg)

    costs = [build_costs(a) for a in avg]

    surfaces = np.empty((len(avg), N_SURFACES, imgs.shape[2]), dtype=np.float32)
    conf = np.empty((len(avg), N_SURFACES, imgs.shape[2]), dtype=np.float32)
    shadow = np.empty((len(avg), imgs.shape[2]), dtype=bool)
    notes: list[str] = []
    for i, a in enumerate(avg):
        r = segment_bscan(a, px_um=px_um, costs=costs[i])
        surfaces[i] = r.surfaces
        conf[i] = r.confidence
        shadow[i] = r.shadow
        notes.extend(f"bscan {i}: {n}" for n in r.notes)
        if progress and i % 50 == 0:
            print(f"    segmented {i}/{len(avg)}", flush=True)

    if refine:
        surfaces = refine_slow_axis(surfaces, costs, smooth_bscans=smooth_bscans,
                                    attract=attract).astype(np.float32)
        conf = surface_confidences(surfaces, costs).astype(np.float32)
    return surfaces, conf, shadow, notes


def surface_confidences(surfaces: np.ndarray, costs: list[dict]) -> np.ndarray:
    """
    Per-A-line confidence for every surface, recomputed after refinement.

    Confidence has to be recomputed rather than carried through: refinement
    moves surfaces, and a confidence value measured at the pre-refinement depth
    describes a position the output no longer contains.

    This is the number that separates "the image put the surface here" from
    "the prior put the surface here and the image had no opinion". Without it,
    a surface placed entirely by its prior is indistinguishable from a measured
    one -- both look equally smooth and equally plausible when plotted over a
    contrast-stretched B-scan. Every consumer of these surfaces should be
    reporting it.
    """
    n_b, n_s, n_col = surfaces.shape
    out = np.zeros_like(surfaces, dtype=np.float32)
    for i in range(n_b):
        for s, name in enumerate(SURFACE_NAMES):
            cost = costs[i][SURFACE_COST[name]]
            rows = np.clip(np.round(surfaces[i, s]).astype(int),
                           0, cost.shape[0] - 1)
            out[i, s] = local_confidence(cost, rows)
    return out


def thickness_maps(surfaces: np.ndarray, shadow: np.ndarray,
                   px_um: float = 1.12, mask_shadow: bool = True) -> dict:
    """
    Per-layer thickness maps, [n_bscan, n_col], in micrometres.

    Shadowed A-lines are set to NaN rather than interpolated: a vessel shadow
    means the evidence was absent, and a map should say so rather than invent a
    plausible number.
    """
    from .segment import LAYER_DEFS
    idx = {n: i for i, n in enumerate(SURFACE_NAMES)}
    out = {}
    for name, a, b in LAYER_DEFS:
        t = (surfaces[:, idx[b], :] - surfaces[:, idx[a], :]) * px_um
        if mask_shadow:
            t = np.where(shadow, np.nan, t)
        out[name] = t.astype(np.float32)
    return out
