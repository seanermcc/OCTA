"""Eight-boundary tree-shrew retinal segmentation.

Canonical orientation is vitreous at depth 0.  The outer retina is simplified
to a composite photoreceptor band: the old ELM and IS/OS internal surfaces are
not segmented.  ``PR_RPE`` is the RPE-complex peak and the final ``RPE`` line
is its outer edge (the endpoint formerly called BM).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from octa.segment import (
    _fill_nan,
    _interp_over,
    banded_dp,
    build_costs,
    detect_orientation,
    prepare_bscan,
    shadow_columns,
    tissue_bounds,
)
from octa.surfaces import dp_surface, local_confidence, median_filter1d

from .config import (
    INNER_SURFACES,
    LAYER_DEFS,
    N_SURFACES,
    RELATIVE_PRIORS,
    SURFACE_COST,
    SURFACE_NAMES,
    validate_priors,
)


NEIGHBOUR_FRAC = 0.40
MIN_HALFWIDTH_PX = 3.0
MAX_HALFWIDTH_FRAC = 0.07


@dataclass
class BscanResult:
    surfaces: np.ndarray
    confidence: np.ndarray
    shadow: np.ndarray
    notes: list[str] = field(default_factory=list)


def enforce_order(surf: np.ndarray, min_gap: float = 1.0) -> np.ndarray:
    out = np.asarray(surf).copy()
    for i in range(1, out.shape[0]):
        out[i] = np.maximum(out[i], out[i - 1] + min_gap)
    return out


def segment_bscan(
    img: np.ndarray,
    px_um: float = 1.12,
    costs: dict | None = None,
    relative_priors: dict[str, float] | None = None,
) -> BscanResult:
    """Find the eight requested boundaries in one canonical B-scan."""
    del px_um  # retained for API symmetry with the original segmenter
    n_depth, n_col = img.shape
    surf = np.full((N_SURFACES, n_col), np.nan, dtype=np.float32)
    conf = np.zeros_like(surf)
    notes: list[str] = []
    idx = {name: i for i, name in enumerate(SURFACE_NAMES)}
    priors = (RELATIVE_PRIORS if relative_priors is None
              else validate_priors(relative_priors))

    C = costs if costs is not None else build_costs(img)
    c_db, c_bd, c_bright = C["db"], C["bd"], C["bright"]

    # 1. ILM: first dark-to-bright tissue transition.
    first, _last = tissue_bounds(img)
    ilm = median_filter1d(
        banded_dp(c_db, first, halfwidth=18, max_step=2).astype(float), 11)
    surf[idx["ILM"]] = ilm
    conf[idx["ILM"]] = local_confidence(c_db, np.round(ilm).astype(int))

    # 2. PR/RPE: strongest outer-retina peak.  This is the same stable anchor
    # the ten-surface cascade called RPE; only its anatomical name changed.
    pr_rpe = dp_surface(
        c_bright, max_step=2, lo=ilm + 60,
        hi=np.full(n_col, n_depth, dtype=float))
    pr_rpe = median_filter1d(pr_rpe.astype(float), 15)

    shadow = shadow_columns(img, ilm, pr_rpe + 20)
    if shadow.mean() > 0.6:
        notes.append("more than 60% of A-lines shadowed; scan may be unusable")
        # Preserve the original measured behaviour: a mask this broad is more
        # likely a failed shadow detector and must not erase the anchor.
        shadow = np.zeros(n_col, dtype=bool)
    pr_rpe = median_filter1d(_interp_over(shadow, pr_rpe), 11)
    span = pr_rpe - ilm
    if np.median(span) < 60:
        notes.append("ILM-to-PR_RPE span implausibly small; segmentation suspect")

    surf[idx["PR_RPE"]] = pr_rpe
    conf[idx["PR_RPE"]] = local_confidence(
        c_bright, np.round(pr_rpe).astype(int))

    # 3. Outer RPE edge: the old BM endpoint, renamed to match the requested
    # eight-line annotation contract.
    rpe = dp_surface(c_bd, max_step=2, lo=pr_rpe + 4, hi=pr_rpe + 45)
    rpe = median_filter1d(_interp_over(shadow, rpe), 11)
    surf[idx["RPE"]] = rpe
    conf[idx["RPE"]] = local_confidence(c_bd, np.round(rpe).astype(int))

    # 4. Five weak inner boundaries.  Search widths remain tied to adjacent
    # priors, never a free fixed window, so thin layers cannot collapse.
    prior_depth = {name: ilm + priors[name] * span for name in INNER_SURFACES}
    prior_depth["_top"] = ilm
    prior_depth["_bottom"] = pr_rpe
    chain = ["_top"] + INNER_SURFACES + ["_bottom"]

    prev = ilm + 3
    for k, name in enumerate(INNER_SURFACES):
        centre = prior_depth[name]
        gap_up = centre - prior_depth[chain[k]]
        gap_dn = prior_depth[chain[k + 2]] - centre
        half = np.minimum(NEIGHBOUR_FRAC * gap_up, NEIGHBOUR_FRAC * gap_dn)
        half = np.clip(half, MIN_HALFWIDTH_PX, MAX_HALFWIDTH_FRAC * span)
        lo = np.maximum(centre - half, prev + 2)
        hi = np.minimum(centre + half, pr_rpe - 2)
        hi = np.maximum(hi, lo + 3)
        cost = C[SURFACE_COST[name]]
        found = dp_surface(cost, max_step=2, lo=lo, hi=hi)
        found = median_filter1d(_interp_over(shadow, found), 15)
        surf[idx[name]] = found
        conf[idx[name]] = local_confidence(cost, np.round(found).astype(int))
        prev = found

    surf = enforce_order(surf)
    return BscanResult(surf.astype(np.float32), conf.astype(np.float32),
                       shadow.astype(bool), notes)


def thicknesses_um(
    surf: np.ndarray,
    px_um: float,
    surface_reliable: np.ndarray | None = None,
) -> dict[str, np.ndarray]:
    """Per-A-line thickness, with deselected-boundary bands set to NaN."""
    idx = {name: i for i, name in enumerate(SURFACE_NAMES)}
    reliable = (np.ones(N_SURFACES, dtype=bool) if surface_reliable is None
                else np.asarray(surface_reliable, dtype=bool))
    if reliable.shape != (N_SURFACES,):
        raise ValueError(f"surface_reliable must have shape ({N_SURFACES},)")
    out = {}
    for name, top, bottom in LAYER_DEFS:
        value = (surf[idx[bottom]] - surf[idx[top]]) * px_um
        if not (reliable[idx[top]] and reliable[idx[bottom]]):
            value = np.full_like(value, np.nan, dtype=float)
        out[name] = value
    return out

