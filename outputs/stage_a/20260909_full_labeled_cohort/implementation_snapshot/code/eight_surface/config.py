"""Anatomical contract for the eight-boundary workflow."""

from __future__ import annotations

from pathlib import Path
import json

import numpy as np

from octa import reference


SURFACE_NAMES = [
    "ILM",
    "RNFL_GCL",
    "GCL_IPL",
    "IPL_INL",
    "INL_OPL",
    "OPL_ONL",
    "PR_RPE",
    "RPE",
]
N_SURFACES = len(SURFACE_NAMES)

# The surface count and, more importantly, the outer-retina meanings changed.
# Never accept a label merely because it happens to contain eight arrays.
CASCADE_VERSION = "5-8surf-pr"
LABEL_FORMAT_VERSION = "3-local-provenance"
# Versions this workflow can read.  Older files are read exactly as they
# were written and are never rewritten; see eight_surface/provenance.py for
# the conservative policy that governs using them.
READABLE_LABEL_FORMAT_VERSIONS = (
    "1", "2-surface-reliability", "3-local-provenance",
)

SURFACE_DESCRIPTIONS = {
    "ILM": "vitreous / RNFL",
    "RNFL_GCL": "RNFL / GCL",
    "GCL_IPL": "GCL / IPL",
    "IPL_INL": "IPL / INL",
    "INL_OPL": "INL / OPL",
    "OPL_ONL": "OPL / photoreceptor composite",
    "PR_RPE": "photoreceptor composite / RPE (former RPE-complex peak)",
    "RPE": "outer RPE edge (former BM endpoint)",
}

# Directly analysed bands.  PHOTORECEPTOR deliberately combines ONL, ELM,
# inner/outer-segment structure, and the old IS/OS boundary into one band.
ANALYSIS_LAYER_DEFS = [
    ("RNFL", "ILM", "RNFL_GCL"),
    ("GCL", "RNFL_GCL", "GCL_IPL"),
    ("IPL", "GCL_IPL", "IPL_INL"),
    ("INL", "IPL_INL", "INL_OPL"),
    ("OPL", "INL_OPL", "OPL_ONL"),
    ("PHOTORECEPTOR", "OPL_ONL", "PR_RPE"),
    ("RPE", "PR_RPE", "RPE"),
]
LAYER_DEFS = ANALYSIS_LAYER_DEFS + [("TOTAL", "ILM", "RPE")]
LAYER_NAMES = [name for name, _, _ in ANALYSIS_LAYER_DEFS]

# Only these weak inner boundaries are positioned by a relative-depth prior.
# PR_RPE and RPE are strong image anchors, so a scalar prior is not used for
# them and human corrections to them are retained for a future cost model.
INNER_SURFACES = [
    "RNFL_GCL", "GCL_IPL", "IPL_INL", "INL_OPL", "OPL_ONL",
]

SURFACE_COST = {
    "ILM": "db",
    "RNFL_GCL": "bd_soft",
    "GCL_IPL": "db_soft",
    "IPL_INL": "bd_soft",
    "INL_OPL": "db_soft",
    "OPL_ONL": "bd_soft",
    "PR_RPE": "bright",
    "RPE": "bd",
}


def default_priors() -> dict[str, float]:
    """Validated priors for the five retained weak inner boundaries."""
    priors = {
        k: v for k, v in reference.relative_priors("peripheral").items()
        if k in INNER_SURFACES
    }
    # Measured from real hand corrections and re-verified on 19 corrections.
    priors.update({"RNFL_GCL": 0.2390, "GCL_IPL": 0.2799})
    return priors


RELATIVE_PRIORS = default_priors()


def validate_priors(priors: dict[str, float]) -> dict[str, float]:
    """Merge and validate a trusted-prior override."""
    out = RELATIVE_PRIORS.copy()
    unknown = sorted(set(priors) - set(INNER_SURFACES))
    if unknown:
        raise ValueError(
            "prior override contains non-prior surfaces: " + ", ".join(unknown))
    for name, value in priors.items():
        value = float(value)
        if not np.isfinite(value) or not 0.0 < value < 1.0:
            raise ValueError(f"prior for {name} must be finite and between 0 and 1")
        out[name] = value
    values = [out[name] for name in INNER_SURFACES]
    if any(b <= a for a, b in zip(values, values[1:])):
        raise ValueError("inner-surface priors must be strictly ordered")
    return out


def load_priors(path: str | Path | None) -> dict[str, float]:
    """Load ``refit_trusted``/``prior_overrides`` from a refit JSON file."""
    if path is None:
        return RELATIVE_PRIORS.copy()
    p = Path(path)
    payload = json.loads(p.read_text(encoding="utf-8"))
    if "prior_overrides" in payload:
        raw = payload["prior_overrides"]
    elif "refit_trusted" in payload:
        raw = payload["refit_trusted"]
    else:
        raw = payload
    if not isinstance(raw, dict):
        raise ValueError(f"{p} does not contain a prior dictionary")
    return validate_priors(raw)


def affected_layers(surface: str) -> list[str]:
    """Direct thickness bands invalidated when one boundary is deselected."""
    return [name for name, top, bottom in ANALYSIS_LAYER_DEFS
            if surface in (top, bottom)]


def layer_reliability(surface_reliable: np.ndarray) -> dict[str, np.ndarray]:
    """Propagate boundary reliability to each directly bounded layer.

    ``surface_reliable`` may be ``[surface]`` or ``[..., surface]``.  A layer
    is usable only when both of its boundary lines are reliable.  This is the
    exact, deterministic meaning of a GUI boundary deselection.
    """
    rel = np.asarray(surface_reliable, dtype=bool)
    if rel.shape[-1] != N_SURFACES:
        raise ValueError(
            f"surface_reliable last dimension must be {N_SURFACES}, got {rel.shape}")
    idx = {name: i for i, name in enumerate(SURFACE_NAMES)}
    return {name: rel[..., idx[top]] & rel[..., idx[bottom]]
            for name, top, bottom in ANALYSIS_LAYER_DEFS}

