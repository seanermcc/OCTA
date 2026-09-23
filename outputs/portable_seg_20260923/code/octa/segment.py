"""
Multi-surface retinal layer segmentation for tree shrew vis-OCT volumes.

Canonical orientation used throughout this module: **depth index 0 is the
vitreous side and increases into the tissue** (vitreous -> RNFL -> ... -> RPE ->
choroid). The acquisition pipeline stores volumes the other way round, so
`prepare_bscan` flips them. Getting this wrong silently inverts every layer, so
it is asserted rather than assumed.

Surfaces, in depth order:

     0 ILM        vitreous / RNFL
     1 RNFL_GCL   RNFL / GCL
     2 GCL_IPL    GCL / IPL
     3 IPL_INL    IPL / INL
     4 INL_OPL    INL / OPL
     5 OPL_ONL    OPL / ONL
     6 ELM        external limiting membrane
     7 ISOS       inner segment / outer segment (ellipsoid zone)
     8 RPE        RPE inner edge
     9 BM         Bruch's membrane / choroid

GCL_IPL was added once the tree shrew layer structure was pinned to published
values (see `reference.py`): the GCL is a distinct dark band in this species,
and failing to separate it from the IPL was the bug that placed every inner
surface one landmark too shallow.

The two IPL sublamina boundaries (IPL_S1S2, IPL_S2S3) were segmented for a
while and have been **removed from the cascade**. They are real anatomy -- the
paper resolves them -- but not in our data: across all 15 scans checked they
landed in `mixed` support every single time and never in `image`, averaging
40-42% prior-driven A-lines, the two least-supported boundaries in the stack.
The paper resolves them on speckle-reduced SR-B-scans, which we do not have.
Segmenting them produced smooth, correctly-ordered, anatomically sensible
surfaces carrying no information -- the plausible-but-unsupported case that
this project has already been burned by once.

They are still in `reference._STACK`, which is the published anatomy and must
stay complete: IPL_S1 + S2 + S3 is how the stack arrives at the correct depth
for IPL_INL. Dropping the two surfaces therefore moves no other prior. To bring
them back, add the names to `SURFACE_NAMES` and `INNER_SURFACES` and restore
their `SURFACE_COST` entries; the priors are already there.

Why a cascade rather than one big optimisation: the outer surfaces (ILM, ISOS,
BM) carry far more contrast than the inner ones. Finding them first and using
them as hard bounds turns the weak inner problem into a well-conditioned one,
and guarantees the surfaces come out in anatomical order. The existing
`layers_refined_auto.mat` has no such constraint, which is why its ILM and
RNFL/GCL surfaces cross.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import reference as _reference
from .surfaces import (
    dp_surface,
    gradient_cost,
    intensity_cost,
    surface_confidence,
    local_confidence,
    median_filter1d,
    _smooth,
)

SURFACE_NAMES = [
    "ILM", "RNFL_GCL", "GCL_IPL", "IPL_INL",
    "INL_OPL", "OPL_ONL", "ELM", "ISOS", "RPE", "BM",
]
N_SURFACES = len(SURFACE_NAMES)

# Bumped whenever the set or meaning of the surfaces changes, and stored in
# every output. Consumers compare against it rather than against a surface
# count, so that a file holding a superset of the current surfaces can still be
# scored on the surfaces it shares.
#
# "4": RNFL_GCL/GCL_IPL priors refit from real hand corrections (see the
# comment on RELATIVE_PRIORS below). Same 10 surfaces, same names, measurably
# different numbers -- existing outputs are still structurally scoreable
# (surface names match, so qc_vs_reference and label_gui accept them) but were
# segmented with the old, now-known-worse RNFL_GCL/GCL_IPL placement. Batches
# from before this version are not wrong in the way the 9->12 surface change
# was; they are simply less accurate than a re-run would be.
CASCADE_VERSION = "4-10surf"

# Segmented by an earlier version, deliberately dropped. Kept by name so an
# older output can be recognised as a superset rather than as corrupt.
RETIRED_SURFACES = ["IPL_S1S2", "IPL_S2S3"]

# Layers are the gaps between consecutive surfaces. A few entries are
# deliberately *not* consecutive: IPL and GCL_IPL span several surfaces, so
# that results stay comparable with the published table (which reports the
# whole IPL) and with our own earlier output (which could only report GCL+IPL
# combined). They are derived quantities, not extra segmentation work.
LAYER_DEFS = [
    ("RNFL", "ILM", "RNFL_GCL"),
    ("GCL", "RNFL_GCL", "GCL_IPL"),
    ("IPL", "GCL_IPL", "IPL_INL"),
    ("GCL_IPL", "RNFL_GCL", "IPL_INL"),
    ("INL", "IPL_INL", "INL_OPL"),
    ("OPL", "INL_OPL", "OPL_ONL"),
    ("ONL", "OPL_ONL", "ELM"),
    ("IS", "ELM", "ISOS"),
    ("OS", "ISOS", "RPE"),
    ("RPE_BM", "RPE", "BM"),
    ("TOTAL", "ILM", "BM"),
]


# --------------------------------------------------------------------------
# preparation
# --------------------------------------------------------------------------

def prepare_bscan(bscan_aline_depth: np.ndarray,
                  vitreous_at_high_index: bool) -> np.ndarray:
    """
    Convert one stored B-scan into canonical [depth, A-line] dB with the
    vitreous at depth 0.

    Input is [A-line, depth] linear amplitude, as stored by the acquisition
    pipeline.
    """
    x = np.asarray(bscan_aline_depth, dtype=np.float32).T      # [depth, aline]
    x = 20.0 * np.log10(np.maximum(x, 1e-3))
    if vitreous_at_high_index:
        x = x[::-1]
    return np.ascontiguousarray(x)


def detect_orientation(volume_profile: np.ndarray) -> bool:
    """
    True if the vitreous sits at high depth index.

    Decided by which side of the tissue carries the *longer* low-intensity run.
    Comparing mean intensity either side does not work: the first few depth
    pixels sit at the zero-delay edge and are darker than the vitreous, so a
    mean comparison is decided by an 8-pixel sliver and gets it backwards.
    """
    p = np.asarray(volume_profile, dtype=np.float64)
    thresh = np.percentile(p, 10) + 0.25 * (np.percentile(p, 99.5) - np.percentile(p, 10))
    low = p < thresh

    def longest_run_from(end: str) -> int:
        seq = low if end == "high" else low[::-1]
        n = 0
        for v in seq[::-1] if end == "high" else seq[::-1]:
            if v:
                n += 1
            else:
                break
        return n

    tail = 0
    for v in low[::-1]:
        if v:
            tail += 1
        else:
            break
    head = 0
    for v in low:
        if v:
            head += 1
        else:
            break
    return tail > head


def tissue_bounds(img: np.ndarray, frac: float = 0.35,
                  smooth_col: int = 15) -> tuple[np.ndarray, np.ndarray]:
    """
    Per-A-line first and last depth at which tissue is present.

    Uses a per-A-line threshold between that A-line's own noise floor and its
    peak, so it survives the strong lateral brightness variation caused by
    vignetting and vessel shadows.
    """
    x = _smooth(img, 5, smooth_col)
    floor = np.percentile(x, 5, axis=0, keepdims=True)
    peak = np.percentile(x, 99, axis=0, keepdims=True)
    mask = x > (floor + frac * (peak - floor))

    n_depth, n_col = img.shape
    rows = np.arange(n_depth)[:, None]
    big = np.where(mask, rows, n_depth)
    first = big.min(axis=0).astype(np.float64)
    small = np.where(mask, rows, -1)
    last = small.max(axis=0).astype(np.float64)

    first[first >= n_depth] = np.nan
    last[last < 0] = np.nan
    first = _robust_curve(_fill_nan(first))
    last = _robust_curve(_fill_nan(last))
    return first, last


def _robust_curve(a: np.ndarray, med_k: int = 41, max_dev: float = 25.0) -> np.ndarray:
    """
    Turn a noisy per-A-line estimate into a smooth initialisation.

    These curves are only ever used to place a search band, so accuracy matters
    far less than being outlier-free: a vessel shadow can drive the raw tissue
    extent 100+ pixels off, and a band that jumps that far between neighbouring
    A-lines is one the surface search cannot follow.
    """
    m = median_filter1d(np.asarray(a, dtype=np.float64), med_k)
    dev = a - m
    bad = np.abs(dev) > max_dev
    if bad.any():
        fixed = a.copy()
        fixed[bad] = np.nan
        m2 = _fill_nan(fixed)
    else:
        m2 = a
    return median_filter1d(m2, med_k)


def _fill_nan(a: np.ndarray) -> np.ndarray:
    a = np.asarray(a, dtype=np.float64).copy()
    bad = ~np.isfinite(a)
    if bad.all():
        return np.zeros_like(a)
    if bad.any():
        good = np.flatnonzero(~bad)
        a[bad] = np.interp(np.flatnonzero(bad), good, a[good])
    return a


# --------------------------------------------------------------------------
# banded search
# --------------------------------------------------------------------------

def banded_dp(cost: np.ndarray, guess: np.ndarray, halfwidth: int,
              max_step: int = 2,
              lo: np.ndarray | None = None,
              hi: np.ndarray | None = None) -> np.ndarray:
    """
    Run the DP restricted to +/- `halfwidth` around a per-A-line initial guess,
    intersected with any hard ordering bounds.

    Restricting the search is what stops a surface being captured by a stronger
    but anatomically wrong edge elsewhere in the column - in this data the
    choroid is brighter than the RNFL, so an unrestricted search for the ILM
    finds the choroid every time.
    """
    n_depth, n_col = cost.shape
    g = np.asarray(guess, dtype=np.float64)
    band_lo = np.clip(np.floor(g - halfwidth), 0, n_depth - 1)
    band_hi = np.clip(np.ceil(g + halfwidth) + 1, 1, n_depth)

    if lo is not None:
        band_lo = np.maximum(band_lo, np.asarray(lo, dtype=np.float64))
    if hi is not None:
        band_hi = np.minimum(band_hi, np.asarray(hi, dtype=np.float64))

    # never let the window collapse
    bad = band_hi <= band_lo + 1
    if bad.any():
        band_hi[bad] = np.minimum(band_lo[bad] + 2, n_depth)
        band_lo[bad] = np.maximum(band_hi[bad] - 2, 0)

    return dp_surface(cost, max_step=max_step, lo=band_lo, hi=band_hi)


# --------------------------------------------------------------------------
# the cascade
# --------------------------------------------------------------------------

@dataclass
class BscanResult:
    surfaces: np.ndarray            # [N_SURFACES, n_col] float32, depth px
    confidence: np.ndarray          # [N_SURFACES, n_col] float32
    shadow: np.ndarray              # [n_col] bool, vessel-shadow columns
    notes: list = field(default_factory=list)


def shadow_score(img: np.ndarray, ilm: np.ndarray, bm: np.ndarray) -> np.ndarray:
    """
    Continuous per-A-line attenuation score: robust z of mean intensity between
    ILM and BM. Strongly negative = a vessel is casting a shadow.

    Kept separate from the boolean mask so it can serve as the vessel indicator
    for the negative-control test, where a threshold would throw away the very
    gradation the test needs.
    """
    n_depth, n_col = img.shape
    rows = np.arange(n_depth)[:, None]
    inside = (rows >= ilm[None, :]) & (rows < bm[None, :])
    with np.errstate(invalid="ignore"):
        energy = np.nanmean(np.where(inside, img, np.nan), axis=0)
    energy = _fill_nan(energy)
    med = np.median(energy)
    mad = np.median(np.abs(energy - med)) or 1.0
    return ((energy - med) / (1.4826 * mad)).astype(np.float32)


def dilate_mask(mask: np.ndarray, width: int) -> np.ndarray:
    """Widen a boolean 1-D mask by `width` samples on each side."""
    if width <= 0:
        return mask
    out = mask.copy()
    for s in range(1, width + 1):
        out[s:] |= mask[:-s]
        out[:-s] |= mask[s:]
    return out


def shadow_columns_graded(img: np.ndarray, ilm: np.ndarray, bm: np.ndarray,
                          z_thresh: float = -1.2, dilate: int = 0) -> np.ndarray:
    """
    Vessel-shadow mask, optionally widened to cover the penumbra.

    A retinal vessel does not cast a sharp-edged shadow: attenuation fades over
    several A-lines either side of the trunk. Those penumbra columns pass a
    threshold test but their outer surfaces have already started to move, which
    is why total thickness stayed correlated with vessel position (r ~ -0.3)
    even after the core shadows were excluded. Widening the mask is the cheap,
    honest fix - it discards more of the map rather than pretending the edge
    columns are clean.
    """
    core = shadow_score(img, ilm, bm) < z_thresh
    return dilate_mask(core, dilate)


def shadow_columns(img: np.ndarray, ilm: np.ndarray, bm: np.ndarray,
                   z_thresh: float = -1.2) -> np.ndarray:
    """
    Flag A-lines where a retinal vessel has attenuated the deeper signal.

    Measured as total energy between ILM and BM relative to the B-scan median.
    These columns are where segmentation evidence is weakest; downstream they
    are excluded from thickness statistics rather than silently averaged in.
    """
    n_depth, n_col = img.shape
    rows = np.arange(n_depth)[:, None]
    inside = (rows >= ilm[None, :]) & (rows < bm[None, :])
    with np.errstate(invalid="ignore"):
        e = np.where(inside, img, np.nan)
        energy = np.nanmean(e, axis=0)
    energy = _fill_nan(energy)
    med = np.median(energy)
    mad = np.median(np.abs(energy - med)) or 1.0
    z = (energy - med) / (1.4826 * mad)
    return z < z_thresh


# Boundary depths as a fraction of the ILM -> RPE-peak distance, so they scale
# with the retina. These are priors that place a narrow search window; the image
# decides the final position inside that window.
#
# They now come from the published tree shrew layer table (`reference.py`)
# rather than from landmarks fitted to one wild-type scan. The old hand-fitted
# set was:
#
#     RNFL_GCL 0.12   IPL_INL 0.26   INL_OPL 0.37   OPL_ONL 0.55   ELM 0.73
#
# and it was wrong by one landmark throughout the inner retina: it took the
# first dark band below the RNFL to be the INL, when in tree shrew that band is
# the GCL. Everything below it was then stacked too shallow, which put ELM at
# ~146 um where the published stack puts it at ~179 um -- inside the ONL, and
# far enough out that the IS "layer" came out 47 um thick, which is not an
# anatomically possible number. Both the published stack and our own measured
# profile agree on the corrected positions to within ~8 um; see reference.py.
# `relative_priors` returns every boundary in the published stack, including
# the retired IPL sublaminae. Restrict it to what this cascade segments; the
# retired entries stay computable from `reference` if they are ever restored.
RELATIVE_PRIORS = {k: v for k, v in _reference.relative_priors("peripheral").items()
                   if k in SURFACE_NAMES}

# RNFL_GCL and GCL_IPL refit from 10 real hand corrections (2026-08-27), the
# first two surfaces this project has ever had actual human ground truth for
# rather than only the paper and a plausibility check. Measured, not assumed:
#
#   review_surfaces.py refit --labels ../outputs/labels
#     RNFL_GCL  0.3068 -> 0.2390   GCL_IPL  0.3561 -> 0.2799
#
# Verified with the *real* pipeline (bscan_avg=3, refine=True, attract=0.05)
# on the two real scans with corrections plus the WT dev slab, distance from
# the automatic output to the hand-drawn ground truth, published vs refit:
#
#   RNFL_GCL   16.3 um -> 3.4 um   (-79%)
#   GCL_IPL    16.2 um -> 4.4 um   (-73%)
#
# The other four surfaces `refit` also reported (IPL_INL, INL_OPL, OPL_ONL,
# ELM) are deliberately NOT applied here. Their corrections are dominated by
# per-A-line noise rather than a consistent offset (measured bias share
# 19-33%, against 78-84% for the two above) -- refitting them moved the number
# without fixing anything, and applying all six at once made it worse: with
# GCL_IPL pulled shallower and IPL_INL barely moved, the derived IPL layer
# came out *thicker* against the paper in every one of the three re-segmented
# scans (e.g. 38->53, 53->65, 37->50 um against a peripheral value of 45.7),
# and its in-range fraction on the review packs dropped from 42% to 28%.
# IPL_INL likely needs its own correction of comparable size to GCL_IPL's, but
# the 6-8 examples so far don't show it clearly enough to trust a number for
# it yet -- a good target for the next labelling pass.
#
# This is the "deliberate manual edit" review_surfaces.py refit's own output
# warns about. Re-running it as more labels accumulate may justify moving
# these further, or extending the same treatment to other surfaces once their
# bias share clears a similar bar.
#
# RE-VERIFIED 2026-08-28 against 19 corrected label files (was 10). Both
# numbers below are CONFIRMED and were left unchanged:
#
#   refit residual   RNFL_GCL +0.004   GCL_IPL +0.011   -- converged
#   distance to hand-drawn truth, real pipeline, 14 corrected B-scans / 5 scans
#     RNFL_GCL  17.5 um -> 6.3 um     GCL_IPL  16.0 um -> 8.0 um
#     RNFL layer 24.6 -> 7.3          IPL layer 13.0 -> 9.3
#
# The IPL_INL refit this comment previously called "a good target for the next
# labelling pass" was tested with the fuller label set and REJECTED. `refit`
# reports a -0.024 delta for it, the largest left, but that statistic is a
# relative position and is moved by where ILM and RPE land. Measured directly,
# the automatic IPL_INL sits 0.7 um from where humans drew it -- it is already
# right, and there is nothing for a prior to fix. A second candidate, rebuilding
# the whole stack from the human-measured RNFL instead of the paper's, was also
# tested: it fits RNFL_GCL/GCL_IPL/IPL_INL better but OPL_ONL and ELM worse,
# for no net gain (mean |error to human| 0.010 vs 0.009). The discrepancy with
# the paper is confined to the inner retina; it is not a global rescaling.
#
# Known and accepted consequence: against the published table these priors read
# RNFL 11-16 um thinner and IPL 8-17 um thicker than the pre-refit ones, in all
# six scans re-segmented. The SUM RNFL+GCL+IPL is conserved to within ~3 um, so
# this redistributes the inner retina rather than adding or removing tissue --
# consistent with the paper's RNFL being axon *bundle* height (see
# reference.plausible_range's note), which a per-A-line surface reads ~27%
# lower. Which convention this project should report is a question for
# Xiaorong, not a prior to tune: the humans and the paper agree on the total.
RELATIVE_PRIORS.update({"RNFL_GCL": 0.2390, "GCL_IPL": 0.2799})

# Peripheral rather than central because the ONH lies outside the ~1460 um
# field in many of our scans, so most of what we image is nearer the paper's
# 1,200 um peripheral ring than its 500 um central one. The choice only sets
# where the search window is centred -- the window is wide enough to reach the
# central values, and the image decides.


def _interp_over(mask_bad: np.ndarray, values: np.ndarray) -> np.ndarray:
    """Replace masked entries by linear interpolation from good neighbours."""
    v = np.asarray(values, dtype=np.float64).copy()
    good = np.flatnonzero(~mask_bad)
    if good.size < 2:
        return v
    bad = np.flatnonzero(mask_bad)
    if bad.size:
        v[bad] = np.interp(bad, good, v[good])
    return v


def build_costs(img: np.ndarray) -> dict:
    """All cost images for one B-scan, computed once and reused."""
    return {
        "db": gradient_cost(img, "dark_to_bright", smooth_depth=5, smooth_col=11),
        "bd": gradient_cost(img, "bright_to_dark", smooth_depth=5, smooth_col=11),
        "db_soft": gradient_cost(img, "dark_to_bright", smooth_depth=9, smooth_col=17),
        "bd_soft": gradient_cost(img, "bright_to_dark", smooth_depth=9, smooth_col=17),
        "bright": intensity_cost(img, "bright", smooth_depth=7, smooth_col=13),
    }


# Which cost image each surface is found on. Used by the refinement pass.
#
# The polarity of each entry follows directly from the reflectivity of the two
# layers it separates, so it is worth writing them out:
#
#   RNFL (bright) -> GCL (dark)      bright_to_dark
#   GCL (dark)    -> IPL S1 (bright) dark_to_bright
#   S1 (bright)   -> S2 (dark)       bright_to_dark
#   S2 (dark)     -> S3 (bright)     dark_to_bright
#   S3 (bright)   -> INL (dark)      bright_to_dark
#   INL (dark)    -> OPL (bright)    dark_to_bright
#   OPL (bright)  -> ONL (dark)      bright_to_dark
#   ONL (dark)    -> ELM (bright)    dark_to_bright
#
# The "_soft" variants are the more heavily smoothed cost images, used wherever
# the transition is low-contrast. The inner boundaries are all weak -- in our
# data the whole IPL spans only ~0.6 dB peak to valley, against ~6 dB at the
# ILM -- so they use the soft costs throughout.
#
# The retired IPL sublamina entries were "IPL_S1S2": "bd_soft" and
# "IPL_S2S3": "db_soft"; restore them alongside the names if they come back.
SURFACE_COST = {
    "ILM": "db",
    "RNFL_GCL": "bd_soft",
    "GCL_IPL": "db_soft",
    "IPL_INL": "bd_soft",
    "INL_OPL": "db_soft",
    "OPL_ONL": "bd_soft",
    "ELM": "db_soft",
    "ISOS": "db", "RPE": "bright", "BM": "bd",
}

# Surfaces the cascade places by prior + weak image evidence, in the order they
# are searched. Everything else (ILM, RPE, BM, ISOS) is anchored on strong
# features and handled separately.
INNER_SURFACES = ["RNFL_GCL", "GCL_IPL", "IPL_INL",
                  "INL_OPL", "OPL_ONL", "ELM"]

# Search-window geometry for those surfaces. See the comment in the cascade for
# why the window is tied to the neighbouring priors rather than to the span.
NEIGHBOUR_FRAC = 0.40        # never search >40% of the way to a neighbour
MIN_HALFWIDTH_PX = 3.0       # below this the DP has nothing to choose between
MAX_HALFWIDTH_FRAC = 0.07    # the old fixed value, now only an upper cap


def segment_bscan(img: np.ndarray, px_um: float = 1.12,
                  costs: dict | None = None) -> BscanResult:
    """
    Find all surfaces in one canonical-orientation B-scan.

    `img` is [depth, A-line] in dB with the vitreous at depth 0.

    The cascade is anchored on the two features this data carries most strongly:
    the ILM, and the peak of the RPE/photoreceptor complex (a ~10 dB bump, by
    far the largest feature in any A-line). Everything else is located relative
    to those two. Anchoring on BM instead fails, because BM sits at the bottom
    of the recorded depth range in some B-scans and vanishes entirely under
    large vessel shadows.
    """
    n_depth, n_col = img.shape
    surf = np.full((N_SURFACES, n_col), np.nan, dtype=np.float32)
    conf = np.zeros((N_SURFACES, n_col), dtype=np.float32)
    notes: list[str] = []
    idx = {n: i for i, n in enumerate(SURFACE_NAMES)}

    C = costs if costs is not None else build_costs(img)
    c_db, c_bd = C["db"], C["bd"]
    c_db_soft, c_bd_soft, c_bright = C["db_soft"], C["bd_soft"], C["bright"]

    # ---- 1. ILM ----------------------------------------------------------
    first, last = tissue_bounds(img)
    ilm = median_filter1d(
        banded_dp(c_db, first, halfwidth=18, max_step=2).astype(np.float64), 11)
    surf[0] = ilm
    conf[0] = local_confidence(c_db, np.round(ilm).astype(int))

    # ---- 2. RPE complex peak: the brightest thing below the inner retina --
    rpe_peak = dp_surface(c_bright, max_step=2,
                          lo=ilm + 60, hi=np.full(n_col, n_depth, dtype=float))
    rpe_peak = median_filter1d(rpe_peak.astype(np.float64), 15)

    # Shadowed A-lines carry no deep signal at all, so nothing found there is
    # meaningful. Interpolate the anchor across them before it is used to place
    # every other surface.
    shadow = shadow_columns(img, ilm, rpe_peak + 20)
    if shadow.mean() > 0.6:
        notes.append("more than 60% of A-lines shadowed; scan may be unusable")
        shadow = np.zeros(n_col, dtype=bool)
    rpe_peak = median_filter1d(_interp_over(shadow, rpe_peak), 11)

    span = rpe_peak - ilm                     # ILM -> RPE peak, the scale bar
    if np.median(span) < 60:
        notes.append("ILM-to-RPE span implausibly small; segmentation suspect")

    surf[idx["RPE"]] = rpe_peak
    conf[idx["RPE"]] = local_confidence(c_bright, np.round(rpe_peak).astype(int))

    # ---- 3. BM: first strong bright->dark below the RPE peak -------------
    bm = dp_surface(c_bd, max_step=2, lo=rpe_peak + 4, hi=rpe_peak + 45)
    bm = median_filter1d(_interp_over(shadow, bm), 11)
    surf[idx["BM"]] = bm
    conf[idx["BM"]] = local_confidence(c_bd, np.round(bm).astype(int))

    # ---- 4. IS/OS: dark->bright rise just inner to the RPE peak ----------
    isos = dp_surface(c_db, max_step=2, lo=rpe_peak - 0.20 * span,
                      hi=rpe_peak - 2)
    isos = median_filter1d(_interp_over(shadow, isos), 11)
    surf[idx["ISOS"]] = isos
    conf[idx["ISOS"]] = local_confidence(c_db, np.round(isos).astype(int))

    # ---- 5. inner surfaces, each in a window around its published prior ---
    #
    # The search half-width can no longer be a fixed fraction of the span. The
    # old cascade had five inner surfaces spread over the retina and could
    # afford +/-7% of the span (~14 px) around each. There are now eight, and
    # two of the gaps between them are genuinely thin: the GCL is ~10 um (9 px)
    # and IPL S2 is ~10-12 um. A +/-14 px window around each of those overlaps
    # its neighbours completely, and the DP is then free to return the same
    # edge for two different surfaces -- which enforce_order would paper over
    # by stacking them 1 px apart, producing a zero-thickness layer that looks
    # like a confident measurement.
    #
    # So the window is tied to the distance to the neighbouring priors instead:
    # never search more than `NEIGHBOUR_FRAC` of the way toward either
    # neighbour. Two adjacent surfaces then cannot reach the same depth, and
    # thin layers automatically get proportionally tighter windows.
    prior_depth = {n: ilm + RELATIVE_PRIORS[n] * span for n in INNER_SURFACES}
    prior_depth["_top"] = ilm
    prior_depth["_bottom"] = isos

    chain = ["_top"] + INNER_SURFACES + ["_bottom"]
    prev = ilm + 3
    for k, name in enumerate(INNER_SURFACES):
        centre = prior_depth[name]
        gap_up = centre - prior_depth[chain[k]]
        gap_dn = prior_depth[chain[k + 2]] - centre
        half = np.minimum(NEIGHBOUR_FRAC * gap_up, NEIGHBOUR_FRAC * gap_dn)
        half = np.clip(half, MIN_HALFWIDTH_PX, MAX_HALFWIDTH_FRAC * span)

        lo = np.maximum(centre - half, prev + 2)
        hi = np.minimum(centre + half, isos - 2)
        hi = np.maximum(hi, lo + 3)
        cost = C[SURFACE_COST[name]]
        s = dp_surface(cost, max_step=2, lo=lo, hi=hi)
        s = median_filter1d(_interp_over(shadow, s), 15)
        surf[idx[name]] = s
        conf[idx[name]] = local_confidence(cost, np.round(s).astype(int))
        prev = s

    surf = enforce_order(surf)
    return BscanResult(surfaces=surf.astype(np.float32),
                       confidence=conf.astype(np.float32),
                       shadow=shadow, notes=notes)


def enforce_order(surf: np.ndarray, min_gap: float = 1.0) -> np.ndarray:
    """
    Guarantee surface[i] <= surface[i+1] - min_gap everywhere.

    A cumulative maximum from the vitreous side is enough: it never moves a
    surface inward, only pushes a violating deeper surface further out, so a
    single surface that has gone wrong cannot drag the rest of the stack with it.
    """
    out = surf.copy()
    for i in range(1, out.shape[0]):
        out[i] = np.maximum(out[i], out[i - 1] + min_gap)
    return out


def thicknesses_um(surf: np.ndarray, px_um: float) -> dict:
    """Per-A-line thickness of every defined layer, in micrometres."""
    idx = {n: i for i, n in enumerate(SURFACE_NAMES)}
    return {name: (surf[idx[b]] - surf[idx[a]]) * px_um
            for name, a, b in LAYER_DEFS}
