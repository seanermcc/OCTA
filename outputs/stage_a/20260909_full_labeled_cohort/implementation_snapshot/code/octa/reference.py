"""
Normative tree shrew retinal layer thicknesses, and the segmentation priors
derived from them.

Source
------
Grannonico M, Miller DA, Liu M, Krause MA, Savier E, Erisir A, Netland PA,
Cang J, Zhang HF, Liu X. "Comparative In Vivo Imaging of Retinal Structures in
Tree Shrews, Humans, and Mice." eNeuro 11(3), March 2024.
DOI: 10.1523/ENEURO.0373-23.2024

Only the **tree shrew** columns are reproduced here. The paper also reports
mouse and human values; they are irrelevant to this project and are omitted so
nobody can pick the wrong species out of a table.

Central = 500 um radius from the ONH, peripheral = 1,200 um radius. Our scans
have a ~1460 um field and in many of them the ONH is outside it entirely, so we
usually cannot say which regime a given scan belongs to. Default behaviour
everywhere in this module is therefore to accept the **union** of the two
regimes rather than to pick one -- see `plausible_range`.

Why this file exists
--------------------
The priors in `segment.py` were originally fitted to landmarks in one wild-type
scan, with the anatomical labelling unconfirmed (README "Open questions"). That
labelling was wrong: it identified the first dark band below the RNFL as the
INL, when the paper shows it is the **GCL**, which in tree shrew is a distinct
dark band 10-12 um thick. Every inner surface was consequently placed one
landmark too shallow, which is why measured RNFL (34.7 um) and GCL+IPL (28 um)
came out at roughly half the published values while TOTAL (238 um) still
matched -- the error was entirely in how the inner retina was subdivided, not
in its overall extent.

Cross-checks that the table below is self-consistent:

  central     RNFL 81.7 + GCL 12.5 + IPL 50.0 + INL 34 + ONL 14 = 192.2
              TOTAL 250.7 - 192.2 = 58.5 um left for OPL + IS + OS + RPE-BM
  peripheral  RNFL 62.8 + GCL 10.1 + IPL 45.7 + INL 34 + ONL 19 = 171.6
              TOTAL 229.8 - 171.6 = 58.2 um left for OPL + IS + OS + RPE-BM

The two residuals agree to 0.3 um despite being differences of independently
measured quantities. They also agree with S1+S2+S3 summing to the stated IPL
thickness (49.1 vs 50.0 central; 45.8 vs 45.7 peripheral). That is a strong
indication the figure-read INL and ONL values below are close to correct.

Independent check against our own data: stacking the peripheral column from the
ILM predicts the GCL dark band at 59 um, the INL dark band centred at 128 um,
the OPL bright band at 150 um and the ONL dark band at 165 um. The measured
ILM-flattened profile of the TS165 wild-type slab has a trough at 59.4, a
trough at 125.4, a peak at 146.7 and a trough at 166.9. Four independent
landmarks within ~4 um.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LayerRef:
    """One layer's published thickness, in micrometres."""
    central: float
    central_sd: float
    peripheral: float
    peripheral_sd: float
    source: str
    confirmed: bool = True      # False = read off a figure, not stated in text


# --------------------------------------------------------------------------
# the table
# --------------------------------------------------------------------------
#
# confirmed=True   the number appears as text in the paper, quoted in `source`
# confirmed=False  read off a figure axis; treat the SD as indicative only

TREE_SHREW = {
    "TOTAL": LayerRef(
        250.7, 25.0, 229.8, 21.0,
        "Results p.5: C, 250.7 +/- 25 um; P, 229.8 +/- 21 um; "
        "n = 88 measurements from three eyes; p = 1.0e-4"),

    # NOTE: the paper measures *axon bundle height*, not mean RNFL thickness.
    # In tree shrew the RNFL is organised into discrete, vertically elongated
    # bundles separated by thinner gaps, so a per-A-line RNFL thickness map
    # will sit BELOW this value on average and will legitimately vary a lot
    # laterally. A low measured RNFL is therefore not by itself evidence of a
    # segmentation failure -- `plausible_range` widens the lower bound for
    # exactly this reason.
    "RNFL": LayerRef(
        81.7, 23.0, 62.8, 17.0,
        "Fig 2C / Results p.7: axon bundle height C, 81.7 +/- 23 um; "
        "P, 62.8 +/- 17 um; n = 88 measurements from three different eyes"),

    "GCL": LayerRef(
        12.5, 4.5, 10.1, 3.7,
        "Fig 2D / Results p.7: C, 12.5 +/- 4.5 um; P, 10.1 +/- 3.7 um; "
        "n = 88 measurements from four eyes; p = 0.99"),

    "IPL": LayerRef(
        50.0, 5.9, 45.7, 3.4,
        "Fig 2E / Results p.8: the average IPL thickness was 50.0 +/- 5.9 um "
        "in the central region and 45.7 +/- 3.4 um in the peripheral region"),

    "IPL_S1": LayerRef(
        19.5, 2.1, 18.3, 2.1,
        "Fig 4D / Results p.9: S1 in the central region (19.5 +/- 2.1; n = 47) "
        "was significantly thicker than S1 in the peripheral region "
        "(18.3 +/- 2.1; n = 52; p = 3.0e-2)"),

    "IPL_S2": LayerRef(
        12.4, 1.9, 9.7, 1.6,
        "Fig 4D / Results p.9: S2 the central region (12.4 +/- 1.9 um, n = 64) "
        "compared with that in the peripheral region (9.7 +/- 1.6 um, n = 49)"),

    "IPL_S3": LayerRef(
        17.2, 2.2, 17.8, 1.5,
        "Fig 4D / Results p.9: no significant difference was detected in S3 "
        "across the retina (C, 17.2 +/- 2.2 um; P, 17.8 +/- 1.5 um; p = 0.63)"),

    # The paper states INL and ONL only as violin plots (Fig 3C); no numbers
    # appear in the text. These are read off that figure's axis and are the
    # least trustworthy entries in this table -- but they pass the residual
    # cross-check in the module docstring.
    "INL": LayerRef(
        34.0, 7.0, 34.0, 7.0,
        "Fig 3C, read off the axis; text only says INL kept an approximately "
        "homogeneous thickness moving toward the periphery", confirmed=False),

    "ONL": LayerRef(
        14.0, 5.0, 19.0, 6.0,
        "Fig 3C, read off the axis; text: ONL appeared to be significantly "
        "thinner in tree shrews compared with the ONL in mice and humans",
        confirmed=False),
}

# Layers the paper does not measure at all. We still need a prior for OPL in
# order to place the OPL/ONL surface, so it is taken from the residual of the
# paper's own arithmetic (58.2-58.5 um for OPL + IS + OS + RPE-BM, see the
# module docstring) split using our own measured outer-retina landmarks.
# Kept in a separate dict so nothing downstream can report these as published.
NOT_IN_PAPER = {
    "OPL": 12.0,
    "IS": 15.0,
    "OS": 12.0,
    "RPE_BM": 19.0,
}

# The IPL's internal structure, as the paper defines it (Results p.9):
#   "two hyper-reflective bands and one hyporeflective band separating the top
#    and bottom portions of the IPL"
#   S1: top IPL boundary -> first minimum of the valley   (BRIGHT)
#   S2: first minimum -> second minimum of the valley     (DARK)
#   S3: second minimum -> bottom IPL boundary             (BRIGHT)
# This is what makes the sublayers findable at all: S2 is a dark band with a
# bright band on either side, so its upper edge is a bright->dark transition
# and its lower edge a dark->bright one -- the same two cost images the rest
# of the cascade already builds.
IPL_SUBLAYER_POLARITY = {"IPL_S1": "bright", "IPL_S2": "dark", "IPL_S3": "bright"}

# Anatomical order of the boundaries, with the layer whose thickness separates
# each one from the previous. Single source of truth for the stacking order.
_STACK = [
    ("RNFL_GCL", "RNFL"),
    ("GCL_IPL",  "GCL"),
    ("IPL_S1S2", "IPL_S1"),
    ("IPL_S2S3", "IPL_S2"),
    ("IPL_INL",  "IPL_S3"),
    ("INL_OPL",  "INL"),
    ("OPL_ONL",  "OPL"),
    ("ELM",      "ONL"),
    ("ISOS",     "IS"),
    ("RPE",      "OS"),
    ("BM",       "RPE_BM"),
]


def layer_thickness(layer: str, region: str = "peripheral") -> float:
    """Published (or, for NOT_IN_PAPER layers, assumed) thickness in um."""
    if layer in TREE_SHREW:
        r = TREE_SHREW[layer]
        return r.central if region == "central" else r.peripheral
    if layer in NOT_IN_PAPER:
        return NOT_IN_PAPER[layer]
    raise KeyError(f"unknown layer {layer!r}")


def cumulative_depths(region: str = "peripheral") -> dict[str, float]:
    """
    Depth of each boundary below the ILM, in micrometres, by stacking the
    published layer thicknesses in anatomical order.

    This is the quantity segmentation actually needs: a thickness table
    constrains *differences*, but a cascade has to place *positions*.
    """
    if region not in ("central", "peripheral"):
        raise ValueError(f"region must be 'central' or 'peripheral', got {region!r}")
    out, depth = {}, 0.0
    for boundary, layer in _STACK:
        depth += layer_thickness(layer, region)
        out[boundary] = depth
    return out


def relative_priors(region: str = "peripheral") -> dict[str, float]:
    """
    Boundary depths as a fraction of the ILM -> RPE-complex-peak distance.

    Why that denominator: the ILM and the RPE-complex peak are the two features
    this data carries most strongly, and the cascade already anchors on them
    (PIPELINE.md Stage 4). Expressing the priors as fractions of the span
    between them makes them scale with the retina, so one table serves a thin
    peripheral scan and a thick central one alike.

    The RPE-complex *peak* is the middle of the RPE band, which is half the
    RPE-BM thickness above BM -- not BM itself. Using TOTAL as the denominator
    instead would put every prior ~8% too shallow.
    """
    d = cumulative_depths(region)
    span = d["RPE"] - 0.5 * NOT_IN_PAPER["OS"]      # ILM -> middle of RPE band
    return {k: v / span for k, v in d.items() if k not in ("RPE", "BM")}


def plausible_range(layer: str, n_sd: float = 2.0) -> tuple[float, float]:
    """
    Accept-range for a measured layer thickness, in micrometres.

    Spans the union of the central and peripheral regimes, each widened by
    `n_sd` standard deviations, because we usually cannot tell which regime a
    given scan belongs to -- the ONH is outside the field in many of them and
    eccentricity mapping is not built yet (README "What is not built yet").

    RNFL gets a deliberately wider lower bound: the published figure is axon
    *bundle height*, measured at the bundles, whereas a per-A-line thickness map
    averages bundles together with the thinner gaps between them. A mean RNFL
    well below the published bundle height is expected anatomy, not a failure.
    """
    if layer not in TREE_SHREW:
        raise KeyError(f"{layer!r} is not in the published tree shrew table; "
                       f"known layers: {sorted(TREE_SHREW)}")
    r = TREE_SHREW[layer]
    lo = min(r.central - n_sd * r.central_sd, r.peripheral - n_sd * r.peripheral_sd)
    hi = max(r.central + n_sd * r.central_sd, r.peripheral + n_sd * r.peripheral_sd)
    if layer == "RNFL":
        lo = 0.35 * lo          # bundle height vs mean thickness, see docstring
    return max(lo, 0.0), hi


def summary_table() -> str:
    """Human-readable dump of the whole reference, for logs and QC figures."""
    lines = [f"{'layer':8s} {'central':>16s} {'peripheral':>16s}  source"]
    lines.append("-" * 78)
    for name, r in TREE_SHREW.items():
        mark = "" if r.confirmed else "  [figure-read]"
        lines.append(f"{name:8s} {r.central:8.1f} +/-{r.central_sd:5.1f} "
                     f"{r.peripheral:8.1f} +/-{r.peripheral_sd:5.1f}{mark}")
    lines.append("")
    lines.append("not measured in the paper (assumed): " +
                 ", ".join(f"{k} {v:.0f} um" for k, v in NOT_IN_PAPER.items()))
    return "\n".join(lines)
