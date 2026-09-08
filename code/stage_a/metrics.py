"""Column-level risk/coverage. Missing outputs remain in eligible denominators."""
from collections import defaultdict
import numpy as np
from eight_surface.config import SURFACE_NAMES, LAYER_DEFS


def longest_run(mask):
    bounds=np.diff(np.r_[False,np.asarray(mask,bool),False].astype(int))
    start=np.flatnonzero(bounds==1)
    end=np.flatnonzero(bounds==-1)
    return int(np.max(end-start)) if len(start) else 0


def stats(delta, valid, retained, gross_um=25.0, aline_um=1460/512):
    delta,valid,retained=np.asarray(delta,float),np.asarray(valid,bool),np.asarray(retained,bool)
    if delta.shape!=valid.shape or retained.shape!=valid.shape:
        raise ValueError("Metric geometry mismatch")
    selected=valid & retained
    present=selected & np.isfinite(delta)
    n=int(valid.sum()); nr=int(present.sum())
    absolute=np.abs(delta[present])
    failures=valid & (~present | (np.abs(delta)>gross_um))
    gross=present & (np.abs(delta)>gross_um)
    quant=lambda q: float(np.quantile(absolute,q)) if nr else None
    # Missing/abstained values occupy +infinity in all-eligible quantiles.
    # null denotes an infinite/unavailable quantile, never a zero error.
    all_errors=np.where(present,np.abs(delta),np.inf)[valid]
    def all_quant(q):
        if not n:
            return None
        value=np.quantile(all_errors,q,method="inverted_cdf")
        return float(value) if np.isfinite(value) else None
    return dict(n_eligible=n,n_predicted=nr,n_missing_or_abstained=n-nr,
        coverage=nr/n if n else None,median_abs_um=quant(.5),p90_abs_um=quant(.9),
        p95_abs_um=quant(.95),p99_abs_um=quant(.99),max_abs_um=float(absolute.max()) if nr else None,
        mean_abs_um=float(absolute.mean()) if nr else None,
        mean_signed_um=float(delta[present].mean()) if nr else None,
        median_signed_um=float(np.median(delta[present])) if nr else None,
        all_eligible_p90_um=all_quant(.9),all_eligible_p95_um=all_quant(.95),
        gross_error_fraction_of_predictions=int(gross.sum())/nr if nr else None,
        gross_error_fraction_of_eligible=int(gross.sum())/n if n else None,
        failure_fraction_of_eligible=int(failures.sum())/n if n else None,
        longest_failure_columns=longest_run(failures),
        longest_failure_um=longest_run(failures)*aline_um,
        longest_gross_error_columns=longest_run(gross),
        longest_gross_error_um=longest_run(gross)*aline_um)


def components(rows, target, valid, retained, px_um):
    for k,name in enumerate(SURFACE_NAMES):
        yield "boundary",name,(rows[k]-target[k])*px_um,valid[k],retained[k]
    for name,top,bottom in LAYER_DEFS:
        i,j=SURFACE_NAMES.index(top),SURFACE_NAMES.index(bottom)
        yield "thickness",name,((rows[j]-rows[i])-(target[j]-target[i]))*px_um,valid[i]&valid[j],retained[i]&retained[j]


def evaluate(records, targets, predictions, sources, gross_um=25.0):
    """Predictions map keys -> {rows:[8,W], retained:[8,W]} in label coordinates.

    targets are the frozen derived arrays; human annotation stores are not read.
    """
    accum=defaultdict(list)
    per_bscan=[]
    decisions=[]
    for r in records:
        t=targets[r["key"]]
        truth=t["rows_label"]
        valid=t["valid"]
        p=predictions.get(r["key"])
        rows=np.full_like(truth,np.nan) if p is None else np.asarray(p["rows"])
        retained=np.zeros_like(valid) if p is None else np.asarray(p["retained"],bool)
        if rows.shape!=truth.shape or retained.shape!=truth.shape:
            raise ValueError(f"Prediction shape mismatch: {r['key']}")
        decisions.append(dict(key=r["key"],animal=r["animal"],verdict=r["verdict"],
            scope_status=r["scope_status"],eligible=bool(valid.any()),prediction_file_present=p is not None,
            raw_prediction_columns=int(np.isfinite(rows).sum()),
            retained_prediction_columns=int((retained & np.isfinite(rows)).sum()),
            total_boundary_columns=int(rows.size),
            note="Rejected verdict supplies no per-boundary visibility ground truth" if r["verdict"]=="rejected" else ""))
        aline_um=sources[r["scan_id"]]["aline_um"]
        for kind,name,delta,mask,keep in components(rows,truth,valid,retained,r["px_um"]):
            for mode,ret in [("raw",np.ones_like(mask)),("retained",keep)]:
                st=stats(delta,mask,ret,gross_um,aline_um)
                per_bscan.append(dict(key=r["key"],animal=r["animal"],qc_group=r["qc_group"],
                    scope_status=r["scope_status"],kind=kind,name=name,mode=mode,**st))
                for axis,group in [("pooled","all"),("animal",r["animal"]),("qc",r["qc_group"]),
                                   ("biology",r["biological_group"]),("scope",r["scope_status"])]:
                    accum[(axis,group,kind,name,mode)].append((delta,mask,ret,st))
    summaries=[]
    for (axis,group,kind,name,mode),parts in sorted(accum.items()):
        # Insert invalid gaps so runs cannot cross B-scans/animals.
        joined=[np.concatenate([np.r_[p[k],False if k else np.nan] for p in parts]) for k in range(3)]
        st=stats(*joined,gross_um=gross_um)
        st["longest_failure_um"]=max(p[3]["longest_failure_um"] for p in parts)
        st["longest_gross_error_um"]=max(p[3]["longest_gross_error_um"] for p in parts)
        medians=[p[3]["median_abs_um"] for p in parts if p[3]["median_abs_um"] is not None]
        st["historical_median_of_bscan_medians_um"]=float(np.median(medians)) if medians else None
        st["historical_p90_of_bscan_medians_um"]=float(np.quantile(medians,.9)) if medians else None
        summaries.append(dict(axis=axis,group=group,kind=kind,name=name,mode=mode,**st))
    macro=[]
    for kind,name in [("boundary",s) for s in SURFACE_NAMES]+[("thickness",s[0]) for s in LAYER_DEFS]:
        for mode in ("raw","retained"):
            items=[s for s in summaries if s["axis"]=="animal" and s["kind"]==kind and s["name"]==name and s["mode"]==mode and s["n_eligible"]]
            row=dict(kind=kind,name=name,mode=mode,n_animals=len(items))
            for field in ("mean_abs_um","mean_signed_um","coverage","failure_fraction_of_eligible"):
                values=[s[field] for s in items if s[field] is not None]
                row[field]=float(np.mean(values)) if values else None
                row[field+"_n_animals"]=len(values)
            macro.append(row)
    return dict(summary=summaries,animal_macro=macro,per_bscan=per_bscan,decisions=decisions,
        metric_convention="Errors conditional on available predictions; all_eligible quantiles include missing/abstained as infinity (JSON null). Failure fraction includes all missing/abstained. Historical B-scan summaries secondary. Gross cutoff provisional.",gross_um=gross_um)
