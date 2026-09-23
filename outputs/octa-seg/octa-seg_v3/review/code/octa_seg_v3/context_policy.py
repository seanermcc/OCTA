"""Derived uncertainty guards, never human annotation mutations."""
import numpy as np

VERSION = 'vessel-shadow-manual-override-2'


def shadow_masks(resolved, shadow, include_overrides=True):
    """Original detector output and a separate column-wide human-stroke override cohort."""
    original = np.asarray(shadow, bool)
    sources = resolved.get('shadow_override_sources')
    overridden = original & (np.any(sources, axis=0) if sources is not None else False)
    effective = original & ~overridden if include_overrides else original.copy()
    return effective, overridden


def boundary_uncertainty(shape, vessel, shadow):
    columns = np.asarray(shadow, bool).copy()
    if vessel is not None:
        columns |= np.asarray(vessel, bool)
    if columns.shape != (shape[-1],):
        raise ValueError('Vessel/shadow mask does not match native A-lines')
    guarded = np.broadcast_to(columns, shape).copy()
    guarded[0] = False  # ILM alone is exempt from automatic uncertainty.
    return guarded


def vessel_columns(volume, row=None):
    """Conservative union of frozen provider and currently displayed vessel footprints."""
    frozen = np.asarray(volume.data['vessel'], bool)
    displayed = np.asarray(volume.overlays[1], bool)
    if displayed.shape != frozen.shape:
        raise ValueError('Displayed vessel footprint does not match the provider grid')
    return frozen | displayed if row is None else frozen[row] | displayed[row]
