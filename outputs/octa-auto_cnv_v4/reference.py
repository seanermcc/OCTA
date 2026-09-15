"""Interpretable spatial reference and lesion proposals, no annotation inputs."""
from dataclasses import dataclass, asdict
import numpy as np
from scipy import ndimage as ndi
from scipy.spatial import Delaunay, QhullError
from common import PIXEL_UM

@dataclass(frozen=True)
class Parameters:
    tile_px: int = 48
    tile_quantile: float = .60
    polynomial_degree: int = 2
    border_um: float = 35
    vessel_margin_um: float = 25
    halo_exclusion_um: float = 150
    background_deficit_cutoff: float = 7
    support_distance_um: float = 350
    minimum_background_fraction: float = .08
    minimum_core_um2: float = 1600
    core_deficit: float = 30
    footprint_deficit: float = 10
    structural_z: float = 1

VARIANTS = {
    'default': Parameters(),
    'narrow_halo': Parameters(halo_exclusion_um=90),
    'wide_halo': Parameters(halo_exclusion_um=210),
    'lower_reference': Parameters(tile_quantile=.50),
    'upper_reference': Parameters(tile_quantile=.70),
    'plane_reference': Parameters(polynomial_degree=1),
}

def grow(mask, um):
    if not np.any(mask):
        return np.zeros_like(mask, bool)
    return ndi.distance_transform_edt(~mask) <= um / PIXEL_UM

def keep(mask, pixels):
    lab, n = ndi.label(mask, np.ones((3, 3)))
    sizes = np.bincount(lab.ravel())
    allowed = sizes >= pixels
    allowed[0] = False
    return allowed[lab]

def smooth_finite(a, sigma):
    ok = np.isfinite(a)
    weight = ndi.gaussian_filter(ok.astype(float), sigma)
    result = ndi.gaussian_filter(np.where(ok, a, 0.), sigma) / np.maximum(weight, 1e-9)
    result[weight < .3] = np.nan
    return result

def design(y, x, shape, degree):
    y = 2 * np.asarray(y) / (shape[0]-1) - 1
    x = 2 * np.asarray(x) / (shape[1]-1) - 1
    cols = [np.ones_like(x), x, y]
    if degree == 2:
        cols += [x*x, x*y, y*y]
    return np.stack(cols, axis=-1)

def fit_tiles(thickness, eligible, p):
    points, values = [], []
    for y in range(0, thickness.shape[0], p.tile_px):
        for x in range(0, thickness.shape[1], p.tile_px):
            sl = np.s_[y:y+p.tile_px, x:x+p.tile_px]
            yy, xx = np.nonzero(eligible[sl])
            if len(yy) < max(32, eligible[sl].size * .15):
                continue
            points.append((y+np.mean(yy), x+np.mean(xx)))
            values.append(np.quantile(thickness[sl][eligible[sl]], p.tile_quantile))
    points = np.asarray(points)
    ncoef = 6 if p.polynomial_degree == 2 else 3
    if len(points) < max(12, ncoef*3):
        return None
    X = design(points[:, 0], points[:, 1], thickness.shape, p.polynomial_degree)
    values = np.asarray(values)
    weights = np.ones(len(values))
    for _ in range(8):
        coef, _, rank, _ = np.linalg.lstsq(X*weights[:, None]**.5, values*weights**.5, rcond=None)
        if rank < ncoef:
            return None
        residual = values-X@coef
        scale = max(2., 1.4826*np.median(np.abs(residual-np.median(residual))))
        weights = np.minimum(1, 1.5*scale/np.maximum(np.abs(residual), 1e-6))
    yy, xx = np.indices(thickness.shape)
    bg = design(yy, xx, thickness.shape, p.polynomial_degree) @ coef
    return bg, points, coef, float(np.sqrt(np.mean(residual**2)))

def background(thickness, vessel, shadow, low_signal, p, user_excluded=None):
    yy, xx = np.indices(thickness.shape)
    border = (np.minimum.reduce([yy, xx, thickness.shape[0]-1-yy, thickness.shape[1]-1-xx]) * PIXEL_UM < p.border_um)
    eligible = (np.isfinite(thickness) & ~border & ~low_signal
                & ~grow(vessel | shadow, p.vessel_margin_um))
    if user_excluded is not None:
        eligible &= ~user_excluded
    initial = eligible.copy()
    halo = np.zeros_like(eligible)
    fit = None
    # Once suspected, a halo cannot vote itself back into this fit.
    for _ in range(5):
        fit = fit_tiles(thickness, eligible, p)
        if fit is None:
            break
        bg = fit[0]
        deficit = np.where(np.isfinite(thickness) & (bg > 0), 100*(bg-thickness)/bg, np.nan)
        low = keep((smooth_finite(deficit, 3) > p.background_deficit_cutoff) & initial, 100)
        new_halo = halo | grow(low, p.halo_exclusion_um)
        changed = np.sum(new_halo != halo)
        halo = new_halo
        eligible = initial & ~halo
        if not changed:
            break
    # Refit on the final saved selection, never return the preceding fit.
    fit = fit_tiles(thickness, eligible, p)
    sufficient = fit is not None and eligible.mean() >= p.minimum_background_fraction
    supported = np.zeros_like(eligible)
    bg = np.full(thickness.shape, np.nan)
    diagnostics = dict(sufficient=bool(sufficient), background_fraction=float(eligible.mean()),
                       tile_count=0, fit_rmse_um=None, parameters=asdict(p))
    if sufficient:
        bg, points, coef, rmse = fit
        try:
            inside = Delaunay(points).find_simplex(np.stack([yy.ravel(), xx.ravel()], axis=1)).reshape(thickness.shape) >= 0
        except QhullError:
            inside = np.zeros_like(eligible)
        distance = ndi.distance_transform_edt(~eligible)*PIXEL_UM
        supported = inside & (distance <= p.support_distance_um) & (bg > 0) & ~border
        diagnostics.update(tile_count=len(points), fit_rmse_um=rmse, coefficients=coef.tolist())
    diagnostics['supported_fraction'] = float(supported.mean())
    deficit = np.full(thickness.shape, np.nan, np.float32)
    valid = supported & np.isfinite(thickness)
    deficit[valid] = 100*(bg[valid]-thickness[valid])/bg[valid]
    return dict(background_um=bg.astype(np.float32), background_regions=eligible,
                background_supported=supported, background_halo_excluded=halo,
                background_initial=initial, deficit_percent=deficit,
                border=border), diagnostics

def structural_context(enface, vessel):
    # Local structural departures in either direction; neither is CNV-specific.
    a = np.asarray(enface, float)
    trend = ndi.gaussian_filter(a, 28)
    residual = ndi.gaussian_filter(a-trend, 3)
    ref = residual[~grow(vessel, 25)]
    scale = max(.1, 1.4826*np.median(np.abs(ref-np.median(ref)))) if len(ref) else 1
    return (np.abs(residual)/scale).astype(np.float32)

def proposals(maps, thickness, vessel, shadow, auto_missing, low_signal, context, p):
    deficit = maps['deficit_percent']
    supported = maps['background_supported']
    artifact = grow(vessel | shadow, 10) | low_signal | maps['border']
    severe = keep((smooth_finite(deficit, 2) >= p.core_deficit) & np.isfinite(deficit) & ~artifact,
                  p.minimum_core_um2 / PIXEL_UM**2)
    missing = auto_missing & ~artifact & supported
    # Connect fragmented unavailable columns as a proposal, never as thickness.
    clustered = ndi.binary_closing(missing, iterations=3) | missing
    loss = keep(clustered, p.minimum_core_um2 / PIXEL_UM**2) & ~artifact & supported
    nearby_thin = grow((deficit >= 15) & ~artifact, 70)
    possible = severe | (loss & nearby_thin)
    lab, count = ndi.label(possible, np.ones((3, 3)))
    core = np.zeros_like(possible)
    for i in range(1, count+1):
        mask = lab == i
        if mask.sum()*PIXEL_UM**2 >= p.minimum_core_um2 and np.mean(context[mask] >= p.structural_z) >= .1:
            core |= mask
    # Connectivity can span small vessel gaps, but no gap is made measurable.
    thin = (deficit >= p.footprint_deficit) & ~vessel & ~shadow & ~low_signal
    association = ndi.binary_closing(thin | core, iterations=3) | thin | core
    labels, count = ndi.label(association, np.ones((3, 3)))
    ids = np.unique(labels[grow(core, 20)])
    ids = ids[ids != 0]
    footprint = np.isin(labels, ids) & thin
    uncertain = (grow(core | footprint, 10) & ~supported) | (grow(core, 15) & artifact)
    return dict(core=core, footprint=footprint, severe_unconfirmed=severe & ~core,
                clustered_loss=loss, uncertain_margin=uncertain,
                structural_context_z=context, contour10=deficit >= 10,
                contour20=deficit >= 20, contour30=deficit >= 30)

def run(thickness, vessel, shadow, auto_missing, low_signal, enface, p=Parameters(), user_excluded=None):
    shape = thickness.shape
    if thickness.ndim != 2 or any(a.shape != shape for a in (vessel, shadow, auto_missing, low_signal, enface)):
        raise ValueError('All inputs must share native [B-scan,A-line] coordinates')
    if np.any(np.isfinite(thickness) & (thickness <= 0)):
        raise ValueError('Nonpositive measurements must be missing')
    maps, diagnostics = background(thickness, vessel, shadow, low_signal, p, user_excluded)
    maps.update(proposals(maps, thickness, vessel, shadow, auto_missing, low_signal,
                          structural_context(enface, vessel), p))
    return maps, diagnostics

