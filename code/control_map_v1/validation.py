"""Validation measures localization separately from exclusions and thickness."""
import numpy as np
from .io import npz,table,write
from .geometry import branches,convergence,lesion_buffer


def validate_real(out,infos,localizations,cfg):
    crops=[];sensitivity=[]
    for sid,info in sorted(infos.items()):
        d=npz(out/"maps"/(sid+"_analysis.npz"))
        visible=info["visible_onh"]
        if visible.get("resolved"):
            center=np.array(visible["center_um"]);radius=visible["diameter_um"]/2
            # Remove the entire fitted disc, not merely its central pixel.
            bounds=[("right",1,int(np.ceil((center[0]+radius)/d["spacing"][1])),True),
                    ("left",1,int(np.floor((center[0]-radius)/d["spacing"][1])),False),
                    ("below",0,int(np.ceil((center[1]+radius)/d["spacing"][0])),True),
                    ("above",0,int(np.floor((center[1]-radius)/d["spacing"][0])),False)]
            for name,axis,cut,after in bounds:
                if not 8<cut<d["enface"].shape[axis]-8:continue
                sl=[slice(None),slice(None)];sl[axis]=slice(cut,None) if after else slice(None,cut)
                mask=(d["vessel"]&~d["registration_blocked"])[tuple(sl)]
                records,_=branches(mask,d["spacing"],cfg);estimate=convergence(records,cfg)
                origin=np.zeros(2)
                if after:origin[1-axis]=cut*d["spacing"][axis]
                error=float(np.linalg.norm(np.array(estimate["center_um"])+origin-center)) if estimate.get("resolved") else None
                crops.append(dict(scan_id=sid,crop=name,resolved=estimate.get("resolved",False),error_um=error,
                    uncertainty_um=estimate.get("uncertainty_um"),reference="full-view visible-edge fit; self-consistency only",
                    reason=estimate["reason"]))
        lesion=d["cnv_human"]|d["cnv_candidate"]|d.get("cnv_transferred",False)
        # Hold non-CNV reasons fixed so multiplier effects are interpretable.
        other=(d["exclusion_reasons"]&(1|2|32|64))!=0
        for factor in (.5,1.,1.5):
            buffered,_=lesion_buffer(lesion,d["spacing"],factor)
            eligible=~(other|buffered)&np.isfinite(d["thickness"][0])
            sensitivity.append(dict(scan_id=sid,policy="CNV clearance / longest diameter",parameter=factor,
                eligible_fraction=float(eligible.mean()),note="local outlines; excludes transferred outside-FOV extent buffers"))
        for sigma in (2.,3.,4.):
            eligible=d["eligible_A"]&d["local_screen_resolved"]&np.isfinite(d["thickness"][0])
            eligible&=np.abs(d["thickness"][0]-d["local_trend_um"])<=sigma*d["local_sd_um"]
            sensitivity.append(dict(scan_id=sid,policy="B local robust sigma threshold",parameter=sigma,
                eligible_fraction=float(eligible.mean()),note="fixed neighborhood and A mask"))
    table(out/"tables/hidden_onh_validation.csv",crops,fields=["scan_id","crop","resolved","error_um","uncertainty_um","reference","reason"])
    table(out/"tables/sensitivity.csv",sensitivity)
    errors=[r["error_um"] for r in crops if r["resolved"]]
    write(out/"qc/localization_validation.json",dict(crops=len(crops),resolved=len(errors),
        median_error_um=float(np.median(errors)) if errors else None,
        p95_error_um=float(np.percentile(errors,95)) if errors else None,
        reference="visible-edge full-view fit; not independent anatomical truth",
        status="measured" if crops else "unavailable: no usable visible-disc crops"))
