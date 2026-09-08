"""Volume segmentation and reliability-aware thickness maps for eight lines."""

from __future__ import annotations

import numpy as np

from octa.surfaces import dp_surface, local_confidence, median_filter1d

from .config import (
    LAYER_DEFS,
    N_SURFACES,
    SURFACE_COST,
    SURFACE_NAMES,
    layer_reliability,
    validate_priors,
)
from .segment import (
    build_costs,
    enforce_order,
    prepare_bscan,
    segment_bscan,
)


MIN_GAP_PX = 2.0


def average_bscans(imgs: np.ndarray, n: int) -> np.ndarray:
    if n <= 1:
        return imgs
    back, fwd = (n - 1) // 2, n // 2
    out = np.empty_like(imgs)
    for i in range(imgs.shape[0]):
        lo, hi = max(0, i - back), min(imgs.shape[0], i + fwd + 1)
        out[i] = imgs[lo:hi].mean(axis=0)
    return out


def refine_slow_axis(
    surfaces: np.ndarray,
    costs: list[dict],
    smooth_bscans: int = 5,
    halfwidth: int = 6,
    max_step: int = 2,
    attract: float = 0.0,
) -> np.ndarray:
    """Re-find surfaces under the validated soft slow-axis prior."""
    n_b, n_s, _n_col = surfaces.shape
    prior = surfaces.copy()
    for s in range(n_s):
        prior[:, s, :] = median_filter1d(
            surfaces[:, s, :].T.astype(float), smooth_bscans).T

    out = np.empty_like(surfaces)
    for i in range(n_b):
        prev = None
        for s, name in enumerate(SURFACE_NAMES):
            p = prior[i, s].astype(float)
            cost = costs[i][SURFACE_COST[name]]
            if attract > 0:
                found = dp_surface(
                    cost, max_step=max_step, lo=p, hi=p + 1.0,
                    bound_weight=attract).astype(float)
                if prev is not None:
                    found = np.maximum(found, prev + MIN_GAP_PX)
            else:
                lo, hi = p - halfwidth, p + halfwidth + 1
                if prev is not None:
                    lo = np.maximum(lo, prev + MIN_GAP_PX)
                if s + 1 < n_s:
                    hi = np.minimum(
                        hi, prior[i, s + 1].astype(float) - MIN_GAP_PX)
                hi = np.maximum(hi, lo + 2)
                found = dp_surface(cost, max_step=max_step, lo=lo, hi=hi)
            out[i, s] = found
            prev = found.astype(float)
        out[i] = enforce_order(out[i])
    return out


def surface_confidences(surfaces: np.ndarray, costs: list[dict]) -> np.ndarray:
    out = np.zeros_like(surfaces, dtype=np.float32)
    for i in range(surfaces.shape[0]):
        for s, name in enumerate(SURFACE_NAMES):
            cost = costs[i][SURFACE_COST[name]]
            rows = np.clip(np.round(surfaces[i, s]).astype(int),
                           0, cost.shape[0] - 1)
            out[i, s] = local_confidence(cost, rows)
    return out


def segment_volume(
    bscans_aline_depth: np.ndarray,
    vitreous_at_high_index: bool,
    bscan_avg: int = 3,
    refine: bool = True,
    smooth_bscans: int = 5,
    px_um: float = 1.12,
    attract: float = 0.05,
    progress: bool = False,
    prior_overrides: dict[str, float] | None = None,
):
    """Segment an OCT volume; defaults preserve the measured settings."""
    priors = None if prior_overrides is None else validate_priors(prior_overrides)
    imgs = np.stack([prepare_bscan(b, vitreous_at_high_index)
                     for b in bscans_aline_depth])
    avg = average_bscans(imgs, bscan_avg)
    costs = [build_costs(a) for a in avg]

    surfaces = np.empty((len(avg), N_SURFACES, imgs.shape[2]), np.float32)
    conf = np.empty_like(surfaces)
    shadow = np.empty((len(avg), imgs.shape[2]), bool)
    notes: list[str] = []
    for i, image in enumerate(avg):
        result = segment_bscan(
            image, px_um=px_um, costs=costs[i], relative_priors=priors)
        surfaces[i], conf[i], shadow[i] = (
            result.surfaces, result.confidence, result.shadow)
        notes.extend(f"bscan {i}: {note}" for note in result.notes)
        if progress and i % 50 == 0:
            print(f"    segmented {i}/{len(avg)}", flush=True)

    if refine:
        surfaces = refine_slow_axis(
            surfaces, costs, smooth_bscans=smooth_bscans,
            attract=attract).astype(np.float32)
        conf = surface_confidences(surfaces, costs)
    return surfaces, conf, shadow, notes


def thickness_maps(
    surfaces: np.ndarray,
    shadow: np.ndarray,
    px_um: float = 1.12,
    mask_shadow: bool = True,
    surface_reliable: np.ndarray | None = None,
    region_excluded: np.ndarray | None = None,
) -> dict[str, np.ndarray]:
    """Return layer maps and honour human boundary deselections.

    ``surface_reliable`` is ``[surface]``, ``[B-scan, surface]`` or the
    per-A-line ``[B-scan, surface, A-line]``.  Wherever a boundary is false the
    immediately adjacent bands are NaN -- for the whole B-scan in the first two
    shapes, for exactly those A-lines in the third.  The per-A-line form is what
    a local "cannot identify this boundary here" mark produces, and it is the
    only one that can blank the RPE band through a lesion core while leaving
    the inner layers measured in the same columns.  ``region_excluded`` is the
    independent per-A-line human exclusion mask that invalidates every surface.
    """
    surf = np.asarray(surfaces)
    if surf.ndim != 3 or surf.shape[1] != N_SURFACES:
        raise ValueError(
            f"surfaces must be [B-scan, {N_SURFACES}, A-line], got {surf.shape}")
    idx = {name: i for i, name in enumerate(SURFACE_NAMES)}
    full = (surf.shape[0], N_SURFACES, surf.shape[2])

    if surface_reliable is None:
        rel = np.ones(full, dtype=bool)
    else:
        rel = np.asarray(surface_reliable, dtype=bool)
        if rel.shape == (N_SURFACES,):
            rel = np.broadcast_to(rel[None, :, None], full)
        elif rel.shape == (surf.shape[0], N_SURFACES):
            rel = np.broadcast_to(rel[:, :, None], full)
        if rel.shape != full:
            raise ValueError(
                "surface_reliable must be [surface], [B-scan, surface] or "
                "[B-scan, surface, A-line]")

    excluded = (np.zeros((surf.shape[0], surf.shape[2]), dtype=bool)
                if region_excluded is None
                else np.asarray(region_excluded, dtype=bool))
    if excluded.shape != (surf.shape[0], surf.shape[2]):
        raise ValueError("region_excluded must be [B-scan, A-line]")

    # ``layer_reliability`` wants the surface axis last; give it the per-A-line
    # array transposed so the same rule serves both shapes, then put it back.
    direct_rel = layer_reliability(np.moveaxis(rel, 1, -1))
    out = {}
    for name, top, bottom in LAYER_DEFS:
        value = (surf[:, idx[bottom], :] - surf[:, idx[top], :]) * px_um
        valid = rel[:, idx[top], :] & rel[:, idx[bottom], :]
        if name in direct_rel:
            valid = direct_rel[name]
        invalid_px = excluded.copy()
        if mask_shadow:
            invalid_px |= np.asarray(shadow, dtype=bool)
        value = np.where(valid & ~invalid_px, value, np.nan)
        out[name] = value.astype(np.float32)
    return out

