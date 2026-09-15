"""Eight-boundary segmentation, revision 2, calibrated on the 16 labelled packs.

Two measured changes relative to ``eight_surface.segment``:

1. **PR_RPE is anchored from the posterior tissue edge, not from a fixed
   offset below the ILM.**  The original rule searched the brightest path in
   ``[ILM + 60, n_depth]``.  In tree shrew the RNFL/IPL plateau is broad and,
   on many scans, brighter *and more laterally consistent* than the RPE
   complex, so the shortest bright path preferred the inner retina.  Measured
   on the 53 human-corrected B-scans, that failure hit 17 of them (32%) with
   the automatic line 160-215 px too shallow.  The human PR_RPE sits at
   0.76-0.92 of the ILM-to-last-tissue span in every one of the 53, so the
   search is restricted to the outer part of that span.

2. **The five inner relative priors are refit from the human labels.**  The
   values inherited from the ten-surface cascade placed every inner surface one
   landmark too shallow under this contract: automatic GCL measured 9.0 um and
   IPL 76.2 um, against 13.2 and 56.9 um drawn by hand and 10.1-12.5 and
   45.7-50.0 um published (eNeuro 2024, tree shrew).

Everything else is deliberately unchanged: ILM cost and search, the RPE outer
edge, neighbour-scaled inner search windows, shadow handling, ``attract=0.05``
slow-axis refinement, and local-confidence reporting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path

import numpy as np

from octa.segment import (
    _interp_over,
    banded_dp,
    build_costs,
    detect_orientation,
    prepare_bscan,
    shadow_columns,
    tissue_bounds,
)
from octa.surfaces import dp_surface, local_confidence, median_filter1d

from eight_surface.config import (
    INNER_SURFACES,
    N_SURFACES,
    SURFACE_COST,
    SURFACE_NAMES,
    validate_priors,
)
from eight_surface.segment import enforce_order

CASCADE_VERSION = "6-8surf-outeranchor"

NEIGHBOUR_FRAC = 0.40
MIN_HALFWIDTH_PX = 3.0
MAX_HALFWIDTH_FRAC = 0.07

# Outer-anchor window as a fraction of the ILM-to-last-tissue depth.  The
# observed human range over 53 corrected B-scans is 0.759-0.924; the window is
# widened on both sides rather than fitted tightly to that sample.
OUTER_LO_FRAC = 0.60
OUTER_HI_FRAC = 1.02
# If the posterior tissue edge is implausible the outer anchor has no meaning,
# so fall back to the original rule rather than trusting a bad bracket.
MIN_TISSUE_DEPTH_PX = 120.0
MAX_TISSUE_DEPTH_PX = 500.0

PRIORS_PATH = Path(__file__).with_name("priors_v2.json")


def load_priors_v2(path=None) -> dict[str, float]:
    """Refit inner priors written by ``fit_priors.py``."""
    p = Path(PRIORS_PATH if path is None else path)
    payload = json.loads(p.read_text(encoding="utf-8"))
    raw = payload.get("priors", payload)
    return validate_priors({k: v for k, v in raw.items() if k in INNER_SURFACES})


@dataclass
class BscanResult:
    surfaces: np.ndarray
    confidence: np.ndarray
    shadow: np.ndarray
    notes: list[str] = field(default_factory=list)


def outer_anchor_window(img, ilm):
    """Depth bracket for the RPE complex, measured from the posterior edge.

    Returns ``(lo, hi, used_outer_anchor)``.  ``used_outer_anchor`` is False
    where the posterior tissue edge was not usable, so a caller can report how
    often the robust bracket actually applied.
    """
    n_depth = img.shape[0]
    _first, last = tissue_bounds(img)
    depth = np.asarray(last, float) - np.asarray(ilm, float)
    ok = np.isfinite(depth) & (depth > MIN_TISSUE_DEPTH_PX) & (depth < MAX_TISSUE_DEPTH_PX)
    # A per-A-line bracket would inherit every local tissue_bounds glitch.  One
    # robust depth for the whole B-scan keeps the bracket smooth; the DP still
    # follows curvature because the bracket rides on the per-A-line ILM.
    if ok.sum() < max(20, 0.2 * ok.size):
        lo = np.asarray(ilm, float) + 60.0
        hi = np.full(img.shape[1], float(n_depth))
        return lo, hi, False
    typical = float(np.median(depth[ok]))
    lo = np.asarray(ilm, float) + OUTER_LO_FRAC * typical
    hi = np.asarray(ilm, float) + OUTER_HI_FRAC * typical
    hi = np.minimum(hi, n_depth - 1.0)
    lo = np.minimum(lo, hi - 5.0)
    return lo, hi, True


def segment_bscan(
    img: np.ndarray,
    px_um: float = 1.12,
    costs: dict | None = None,
    relative_priors: dict[str, float] | None = None,
) -> BscanResult:
    """Find the eight boundaries in one canonical B-scan (vitreous at depth 0)."""
    del px_um  # retained for API symmetry with the original segmenter
    n_depth, n_col = img.shape
    surf = np.full((N_SURFACES, n_col), np.nan, dtype=np.float32)
    conf = np.zeros_like(surf)
    notes: list[str] = []
    idx = {name: i for i, name in enumerate(SURFACE_NAMES)}
    priors = validate_priors(
        load_priors_v2() if relative_priors is None else relative_priors)

    C = costs if costs is not None else build_costs(img)
    c_db, c_bd, c_bright = C["db"], C["bd"], C["bright"]

    # 1. ILM: unchanged.  Measured against the human labels it is already
    # correct -- median correction 0.0 px, 95th percentile 6.4 px.
    first, _last = tissue_bounds(img)
    ilm = median_filter1d(
        banded_dp(c_db, first, halfwidth=18, max_step=2).astype(float), 11)
    surf[idx["ILM"]] = ilm
    conf[idx["ILM"]] = local_confidence(c_db, np.round(ilm).astype(int))

    # 2. PR/RPE, bracketed against the posterior tissue edge.
    lo, hi, used_outer = outer_anchor_window(img, ilm)
    if not used_outer:
        notes.append("posterior tissue edge unusable; fell back to ILM+60 anchor")
    pr_rpe = dp_surface(c_bright, max_step=2, lo=lo, hi=hi)
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
    conf[idx["PR_RPE"]] = local_confidence(c_bright, np.round(pr_rpe).astype(int))

    # 3. Outer RPE edge: unchanged.
    rpe = dp_surface(c_bd, max_step=2, lo=pr_rpe + 4, hi=pr_rpe + 45)
    rpe = median_filter1d(_interp_over(shadow, rpe), 11)
    surf[idx["RPE"]] = rpe
    conf[idx["RPE"]] = local_confidence(c_bd, np.round(rpe).astype(int))

    # 4. Five weak inner boundaries, neighbour-scaled windows unchanged.
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
        lo_k = np.maximum(centre - half, prev + 2)
        hi_k = np.minimum(centre + half, pr_rpe - 2)
        hi_k = np.maximum(hi_k, lo_k + 3)
        cost = C[SURFACE_COST[name]]
        found = dp_surface(cost, max_step=2, lo=lo_k, hi=hi_k)
        found = median_filter1d(_interp_over(shadow, found), 15)
        surf[idx[name]] = found
        conf[idx[name]] = local_confidence(cost, np.round(found).astype(int))
        prev = found

    surf = enforce_order(surf)
    return BscanResult(surf.astype(np.float32), conf.astype(np.float32),
                       shadow.astype(bool), notes)
