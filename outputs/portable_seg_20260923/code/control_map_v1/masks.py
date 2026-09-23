"""Overlapping reasons and exact masked local median/MAD screens."""
import warnings
import numpy as np
from scipy import ndimage as ndi
from .geometry import lesion_buffer, vessel_buffer, xy_grid

REASONS = dict(human_excluded=1,shadow=2,cnv_human=4,cnv_candidate=8,cnv_buffer=16,
               major_vessel=32,onh=64,unavailable_full_retina=128,
               normal_abnormal=256,normal_unresolved=512,cnv_transferred=1024)


def local_screen(full, eligible, spacing, cfg, sigma=None):
    """500 um diameter disk by default; outside-FOV pixels count as unavailable.

    Both median and MAD use exactly the same eligible neighborhood. In particular
    this is NOT a median filter on spatially varying trend residuals.
    """
    radius=cfg["neighborhood_diameter_um"]/2
    ry,rx=np.ceil(radius/np.asarray(spacing)).astype(int)
    yy,xx=np.mgrid[-ry:ry+1,-rx:rx+1]
    footprint=(yy*spacing[0])**2+(xx*spacing[1])**2<=radius**2
    data=np.where(eligible&np.isfinite(full),full,np.nan)
    def stats(values,axis):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore",RuntimeWarning)
            med=np.nanmedian(values,axis=axis,keepdims=True)
            mad=np.nanmedian(np.abs(values-med),axis=axis)
            med=np.squeeze(med,axis=axis)
        return np.stack([med,mad],axis=-1)
    # Tile both image axes: scipy alone chunks rows, and a native 512-pixel
    # row with a 500-um footprint exceeds its minimum-chunk memory budget.
    # Explicit halos preserve the exact full-image neighborhood at tile seams.
    padded=np.pad(data,((ry,ry),(rx,rx)),constant_values=np.nan)
    result=np.empty((*data.shape,2),dtype=data.dtype)
    footprint_indices=np.flatnonzero(footprint)
    for y in range(0,data.shape[0],16):
        for x in range(0,data.shape[1],16):
            h=min(16,data.shape[0]-y);w=min(16,data.shape[1]-x)
            window=padded[y:y+h+2*ry,x:x+w+2*rx]
            windows=np.lib.stride_tricks.sliding_window_view(window,footprint.shape)
            # Materialize in row-major neighborhood order before footprint take.
            # Boolean advanced indexing otherwise puts the footprint dimension
            # first in memory, making each median traverse a whole tile's cache.
            windows=np.ascontiguousarray(windows).reshape(h,w,-1)
            values=np.take(windows,footprint_indices,axis=-1)
            result[y:y+h,x:x+w]=stats(values,axis=-1)
    from scipy.signal import fftconvolve
    count=np.rint(fftconvolve(np.isfinite(data).astype(float),footprint.astype(float),mode="same"))
    trend,mad=result[...,0],result[...,1]
    sd=np.maximum(1.4826*mad,cfg["local_sigma_floor_um"])
    resolved=(count>=cfg["minimum_neighborhood_fraction"]*footprint.sum())&np.isfinite(trend)
    keep=eligible&np.isfinite(full)&resolved&(np.abs(full-trend)<=(sigma or cfg["normal_sigma"])*sd)
    return dict(keep=keep,resolved=resolved,trend=trend,sd=sd,neighborhood_count=count,
                residual=full-trend)


def candidates(data,cfg):
    eligible=~(data["human_excluded"]|data["shadow"]|data["vessel"]|data["onh"]|data["cnv_human"])
    screen=local_screen(data["thickness"][0],eligible,data["spacing"],cfg,cfg["candidate_sigma"])
    full=eligible&np.isfinite(data["thickness"][0])&screen["resolved"]&~screen["keep"]
    # Outer disruption is a separate available outer-composite thickness abnormality.
    # Missing outer data is unavailable evidence, never a positive lesion candidate.
    outer=data["thickness"][6]+data["thickness"][7]
    os=local_screen(outer,eligible,data["spacing"],cfg,cfg["candidate_sigma"])
    disruption=eligible&np.isfinite(outer)&os["resolved"]&~os["keep"]
    lab,n=ndi.label(full|disruption); accepted=np.zeros_like(full)
    for k in range(1,n+1):
        mask=lab==k
        if mask.sum()*np.prod(data["spacing"])>=cfg["candidate_min_area_um2"]: accepted|=mask
    return accepted,dict(candidate_full_deviation=full,candidate_outer_deviation=disruption,
                         candidate_screen_resolved=screen["resolved"],candidate_trend_um=screen["trend"])


def exclusions(data,localization,cfg):
    spacing=data["spacing"]; shape=data["enface"].shape
    transferred=data.get("cnv_transferred",np.zeros(shape,bool))
    lesion=data["cnv_human"]|data["cnv_candidate"]|transferred
    buffered,components=lesion_buffer(lesion,spacing,cfg["cnv_buffer_diameters"])
    # A recovered, larger Feret diameter may supply a conservative buffer after
    # a lesion was transferred from a same-session neighbor.
    buffered |= data.get("cnv_transferred_buffer",np.zeros(shape,bool))
    vessel=vessel_buffer(data["vessel"],spacing,cfg["vessel_buffer_diameters"])
    onh=data["onh"].copy(); disc=localization.get("diameter_um")
    onh_complete=False
    if localization.get("resolved") and disc is not None:
        distance=np.linalg.norm(xy_grid(shape,spacing)-localization["center_um"],axis=-1)
        onh|=distance<=disc*(.5+cfg["onh_buffer_diameters"])+.5*np.hypot(*spacing)
        onh_complete=True
    elif onh.any():
        # Visible partial footprint has no established whole-disc size.
        onh |= data["onh_edge"]
    else: onh |= data["onh_edge"]
    masks=dict(human_excluded=data["human_excluded"],shadow=data["shadow"],
               cnv_human=data["cnv_human"],cnv_candidate=data["cnv_candidate"],
               cnv_buffer=buffered,major_vessel=vessel,onh=onh,cnv_transferred=transferred,
               unavailable_full_retina=~np.isfinite(data["thickness"][0]))
    # Version A retains each layer's own availability. Missing full retina alone
    # does not discard available measurements of other layers.
    blocked=np.logical_or.reduce([m for k,m in masks.items() if k!="unavailable_full_retina"])
    a=~blocked
    screen=local_screen(data["thickness"][0],a,spacing,cfg)
    masks["normal_abnormal"]=a&screen["resolved"]&np.isfinite(data["thickness"][0])&~screen["keep"]
    masks["normal_unresolved"]=a&(~screen["resolved"]|~np.isfinite(data["thickness"][0]))
    reason=np.zeros(shape,np.uint16)
    for key,mask in masks.items(): reason[mask]|=REASONS[key]
    return dict(eligible_A=a,eligible_B=screen["keep"],exclusion_reasons=reason,
                local_trend_um=screen["trend"],local_sd_um=screen["sd"],
                local_screen_resolved=screen["resolved"]), components, onh_complete
