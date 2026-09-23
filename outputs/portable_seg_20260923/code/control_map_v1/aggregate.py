"""Observed cells only; nested equal-weight sampling units and verified repeats."""
import warnings
import numpy as np
import pandas as pd
from . import LAYERS
from .geometry import xy_grid,apply,sample_native


def finite_stats(x):
    x=np.asarray(x); x=x[np.isfinite(x)]
    return dict(n=int(len(x)),mean_um=float(x.mean()) if len(x) else None,
                sd_um=float(x.std(ddof=1)) if len(x)>1 else None,
                range_um=float(np.ptp(x)) if len(x) else None)


def reduce_cells(values,cells):
    valid=np.isfinite(values)
    if not valid.any(): return []
    unique,inverse=np.unique(cells[valid],axis=0,return_inverse=True)
    count=np.bincount(inverse); means=np.bincount(inverse,weights=values[valid])/count
    return [(tuple(map(int,key)),float(val),int(n)) for key,val,n in zip(unique,means,count)]


def acquisition_rows(sid,data,info,loc,cfg):
    rows=[]; local=[]
    xy=xy_grid(data["enface"].shape,data["spacing"])
    if loc.get("resolved"):
        # Native axes in disconnected components remain provisional. Only verified
        # vessel registration supplies relative rotation within a component.
        relative=apply(xy,np.asarray(loc["matrix_to_component"]))-loc["component_center_um"]
        theta=np.deg2rad(cfg["orientation"]["rotation_deg"])
        rot=np.array([[np.cos(theta),-np.sin(theta)],[np.sin(theta),np.cos(theta)]])
        relative=relative@rot.T
        distance=np.linalg.norm(relative,axis=-1)
        angle=np.mod(np.degrees(np.arctan2(-relative[...,1],relative[...,0])),360.)
        polar=np.stack([np.floor(distance/cfg["radial_band_um"]),np.floor(angle/cfg["angular_sector_deg"])],axis=-1).astype(int)
        cart=np.floor(relative/cfg["grid_um"]+.5).astype(int)
    else:
        relative=np.full_like(xy,np.nan);distance=np.full(xy.shape[:2],np.nan);angle=distance.copy()
    area=float(np.prod(data["spacing"]))
    for version in ("A","B"):
        for k,(name,_,_) in enumerate(LAYERS):
            values=np.where(data["eligible_"+version],data["thickness"][k],np.nan)
            base=dict(scan_id=sid,animal=info["animal"],eye=info["eye"],date=info["session_date"],
                      days_post_laser=info.get("days_post_laser",""),layer=name,version=version)
            stats=finite_stats(values)
            local.append(dict(base,**stats,eligible_area_um2=stats["n"]*area,localized=loc.get("resolved",False)))
            if not loc.get("resolved"): continue
            for kind,cells in (("cartesian",cart),("polar",polar)):
                for key,mean,n in reduce_cells(values,cells):
                    rows.append(dict(base,kind=kind,cell_0=key[0],cell_1=key[1],value_um=mean,
                                     native_pixel_n=n,area_um2=n*area))
    coordinates=dict(native_x_um=xy[...,0],native_y_um=xy[...,1],onh_x_um=relative[...,0],
                     onh_y_um=relative[...,1],onh_distance_um=distance,onh_angle_deg=angle)
    return rows,local,coordinates


KEYS=["kind","cell_0","cell_1","layer","version"]


def balanced(rows):
    """Repeats within dates -> dates within eyes -> eyes within animals -> animals."""
    if not len(rows): return {k:pd.DataFrame() for k in ("date","eye","animal","cohort")}
    df=pd.DataFrame(rows)
    date_keys=KEYS+["animal","eye","date"]
    dates=df.groupby(date_keys,as_index=False).agg(value_um=("value_um","mean"),
        acquisitions=("scan_id","nunique"),observed_area_sum_um2=("area_um2","sum"))
    eye_keys=KEYS+["animal","eye"]
    eyes=dates.groupby(eye_keys,as_index=False).agg(value_um=("value_um","mean"),dates=("date","nunique"),
        acquisitions=("acquisitions","sum"),date_sd_um=("value_um","std"),
        observed_area_sum_um2=("observed_area_sum_um2","sum"))
    animals=eyes.groupby(KEYS+["animal"],as_index=False).agg(value_um=("value_um","mean"),
        eyes=("eye","nunique"),dates=("dates","sum"),acquisitions=("acquisitions","sum"),
        observed_area_sum_um2=("observed_area_sum_um2","sum"))
    cohort=animals.groupby(KEYS,as_index=False).agg(value_um=("value_um","mean"),animals=("animal","nunique"),
        eyes=("eyes","sum"),dates=("dates","sum"),acquisitions=("acquisitions","sum"),
        animal_sd_um=("value_um","std"),observed_area_sum_um2=("observed_area_sum_um2","sum"))
    cohort["animal_sem_um"]=cohort["animal_sd_um"]/np.sqrt(cohort["animals"])
    return dict(date=dates,eye=eyes,animal=animals,cohort=cohort)


def repeat_pair(a,b,ia,ib,match,cfg):
    moved=apply(xy_grid(a["enface"].shape,a["spacing"]),np.asarray(match["matrix"]))
    rows=[]; maps={}
    bcnv,_=sample_native(b["cnv_human"]|b["cnv_candidate"],moved,b["spacing"])
    history=a["cnv_human"]|a["cnv_candidate"]|(bcnv==1)
    for version in ("A","B"):
        bvalues,inbounds=sample_native(np.where(b["eligible_"+version],b["thickness"],np.nan),moved,b["spacing"])
        av=np.where(a["eligible_"+version],a["thickness"],np.nan)
        differences=bvalues-av
        maps["difference_"+version+"_um"]=differences
        maps["overlap_"+version]=np.isfinite(differences)
        for k,(name,_,_) in enumerate(LAYERS):
            stats=finite_stats(differences[k]);ok=np.isfinite(differences[k])
            rows.append(dict(animal=ia["animal"],eye=ia["eye"],scan_a=ia["scan_id"],scan_b=ib["scan_id"],
                date_a=ia["session_date"],date_b=ib["session_date"],
                interval="same_session" if ia["session_date"]==ib["session_date"] else "across_date",
                layer=name,version=version,registration_error_um=match["residual_um"],
                branch_error_um=match["branch_residual_um"],overlap_fraction=match["overlap_fraction"],
                eligible_overlap_um2=stats["n"]*float(np.prod(a["spacing"])),
                difference_b_minus_a_mean_um=stats["mean_um"],difference_sd_um=stats["sd_um"],
                difference_range_um=stats["range_um"],matched_native_pixels=stats["n"],
                cnv_history_pixels=int((history&ok).sum()),
                cnv_history_either_acquisition=bool(history.any())))
    maps["cnv_history"]=history
    return rows,maps


def repeated_component(scans,infos,localizations,cfg):
    """Variation over >=2 observations in a vessel-connected physical component.

    Cartesian cells here establish tissue only within a verified registration
    component. ONH proximity between disconnected components never pools repeats.
    """
    records=[]
    for sid,data in scans.items():
        loc=localizations[sid]; info=infos[sid]
        xy=apply(xy_grid(data["enface"].shape,data["spacing"]),np.array(loc["matrix_to_component"]))
        lo=np.ceil(xy.reshape(-1,2).min(axis=0)/cfg["grid_um"]).astype(int)
        hi=np.floor(xy.reshape(-1,2).max(axis=0)/cfg["grid_um"]).astype(int)
        xx,yy=np.meshgrid(np.arange(lo[0],hi[0]+1),np.arange(lo[1],hi[1]+1))
        cells=np.stack([xx,yy],axis=-1)
        target=apply(cells*cfg["grid_um"],np.linalg.inv(np.array(loc["matrix_to_component"])))
        for version in ("A","B"):
            for k,(name,_,_) in enumerate(LAYERS):
                vals,_=sample_native(np.where(data["eligible_"+version],data["thickness"][k],np.nan),target,data["spacing"])
                for cell,val,n in reduce_cells(vals,cells):
                    records.append(dict(component=loc["component"],cell_0=cell[0],cell_1=cell[1],
                        animal=info["animal"],eye=info["eye"],date=info["session_date"],scan_id=sid,
                        layer=name,version=version,value_um=val))
    if not records: return pd.DataFrame()
    df=pd.DataFrame(records); keys=["component","animal","eye","cell_0","cell_1","layer","version"]
    same=df.groupby(keys+["date"],as_index=False).agg(acquisitions=("scan_id","nunique"),
        mean_um=("value_um","mean"),sd_um=("value_um","std"),range_um=("value_um",lambda x:x.max()-x.min()))
    across=same.groupby(keys,as_index=False).agg(dates=("date","nunique"),acquisitions=("acquisitions","sum"),
        mean_um=("mean_um","mean"),sd_um=("mean_um","std"),range_um=("mean_um",lambda x:x.max()-x.min()))
    same=same[same.acquisitions>=2].copy();same["interval"]="same_session";same["dates"]=1
    across=across[across.dates>=2].copy();across["interval"]="across_date";across["date"]="multiple"
    return pd.concat([same,across],ignore_index=True)
