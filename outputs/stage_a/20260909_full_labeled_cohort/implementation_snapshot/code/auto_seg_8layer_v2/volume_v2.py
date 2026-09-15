"""Volume driver for the revision-2 eight-boundary cascade.

Identical in structure to ``eight_surface.volume``; it only swaps in the
revision-2 per-B-scan segmenter.  The measured settings are preserved:
``bscan_avg=3``, ``attract=0.05``, ``smooth_bscans=5``.
"""

from __future__ import annotations

import numpy as np

from eight_surface.config import N_SURFACES, validate_priors
from eight_surface.volume import (
    average_bscans,
    refine_slow_axis,
    surface_confidences,
    thickness_maps,
)

from .segment_v2 import build_costs, load_priors_v2, prepare_bscan, segment_bscan

__all__ = ["segment_volume", "thickness_maps", "average_bscans"]


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
    """Segment one OCT volume with the revision-2 cascade."""
    priors = validate_priors(
        load_priors_v2() if prior_overrides is None else prior_overrides)
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
        # refine_slow_axis re-finds every surface under the validated soft
        # slow-axis prior; it is cost-driven and cascade-agnostic, so the
        # revision-2 surfaces reuse it unchanged.
        surfaces = refine_slow_axis(
            surfaces, costs, smooth_bscans=smooth_bscans,
            attract=attract).astype(np.float32)
        conf = surface_confidences(surfaces, costs)
    return surfaces, conf, shadow, notes
