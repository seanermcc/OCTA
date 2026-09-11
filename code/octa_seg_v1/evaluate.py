"""CPU-only calibration and evaluation. Human overrides excluded from scoring."""
import json
import time
import numpy as np
from eight_surface.config import SURFACE_NAMES,LAYER_DEFS
from .common import *
from .decisions import decide,thickness,runs

def choose_cutoff(p,target,required_retention=.7):
    pos=p[target==1];neg=p[target==0]
    if len(pos)<20:return dict(cutoff=1.01,positive=len(pos),negative=len(neg),retention=None,false_positive=None,passes=False)
    candidates=np.unique(np.r_[np.linspace(.01,.99,99),np.quantile(pos,np.linspace(0,1,51))])
    rows=[]
    for c in candidates:
        retention=float(np.mean(pos>=c));false=float(np.mean(neg>=c)) if len(neg) else None
        if retention>=required_retention:
            rows.append((false if false is not None else 0,-retention,float(c)))
    false,negative_retention,c=min(rows) if rows else (1,0,1.01)
    return dict(cutoff=c,positive=len(pos),negative=len(neg),retention=-negative_retention,
        false_positive=false if len(neg) else None,passes=bool(len(neg)>=20 and false<=.1 and -negative_retention>=required_retention))

def calibrate(records,data,preds):
    result=[]
    for k,name in enumerate(SURFACE_NAMES):
        prob=np.concatenate([preds[r["key"]]["probabilities"][k] for r in records],axis=-1)
        tr=np.concatenate([data[r["key"]]["trace_target"][k] for r in records])
        rel=np.concatenate([data[r["key"]]["reliability_target"][k] for r in records])
        tc=choose_cutoff(prob[0],tr);rc=choose_cutoff(prob[1],rel)
        # Separate conservative not-traceable cutoff: <=5% of affirmative
        # traceability marks may be classified as not traceable on calibration.
        yes=prob[0,tr==1];no=prob[0,tr==0]
        nc=float(min(np.quantile(yes,.05),np.quantile(no,.8))) if len(yes)>=20 and len(no)>=20 else -1.
        result.append(dict(boundary=name,trace_cutoff=tc["cutoff"],reliability_cutoff=rc["cutoff"],
            not_traceable_cutoff=nc,supported=bool(tc["positive"]>=20 and rc["positive"]>=20),
            passes_calibration=bool(tc["passes"] and rc["passes"]),trace=tc,reliability=rc))
    return result

def error_summary(error,eligible):
    error=np.asarray(error);finite=error[np.isfinite(error)]
    return dict(n_eligible=int(eligible),n_reported=len(finite),coverage=len(finite)/eligible if eligible else None,
        median_um=float(np.median(finite)) if len(finite) else None,
        p95_um=float(np.quantile(finite,.95)) if len(finite) else None,
        max_um=float(np.max(finite)) if len(finite) else None,
        error_over_20um=float(np.mean(finite>20)) if len(finite) else None)

def run():
    start=time.monotonic();m=json.loads((OUT/"data/manifest.json").read_text())
    protocol=json.loads((OUT/"models/protocol.json").read_text())
    data={r["key"]:load_npz(r["cache"]["path"]) for r in m["records"]}
    summary=[];metrics=[];position=[];spatial=[];calibrations={}
    for fold in protocol["folds"]:
        if fold["name"]=="ALL_LABELLED":continue
        if set(fold["training"]) & set(fold["calibration"]+fold["evaluation"]):raise AssertionError("Animal leak")
        for variant in ("vessels","no_vessels"):
            preds={r["key"]:load_npz(OUT/"predictions/labels"/fold["name"]/variant/f"{r['key']}.npz") for r in m["records"]}
            calrecs=[r for r in m["records"] if r["animal"] in fold["calibration"]]
            c=calibrate(calrecs,data,preds);calibrations[(fold["name"],variant)]=c
            write_json(OUT/"calibration"/f"{fold['name']}_{variant}.json",dict(fold=fold,thresholds=c,
                policy="calibration animal only; minimize false-positive state classification subject to >=70% affirmative state retention; no volume percentile"))
            for r in [r for r in m["records"] if r["animal"] in fold["evaluation"]]:
                d=data[r["key"]];p=preds[r["key"]]
                # Evaluation must not use the held-out human decisions to gate
                # predictions. Actual deployment guards are measured separately.
                rep,state,reason=decide(p["rows"],p["probabilities"],c,d["vessel"],use_vessels=variant=="vessels")
                save_npz(OUT/"evaluation/predictions"/fold["name"]/variant/f"{r['key']}.npz",reported=rep,state=state,reason=reason)
                strata={"all":np.ones(rep.shape[-1],bool),"vessel":d["vessel"],"no_vessel":~d["vessel"],
                        "cnv_outline":d["cnv"],"outside_cnv_outline":~d["cnv"],"legacy_remote_scope":d["original_scope"]}
                for k,name in enumerate(SURFACE_NAMES):
                    for stratum,mask in strata.items():
                        tr=d["trace_target"][k];rel=d["reliability_target"][k]
                        reporting=np.isfinite(rep[k]);nt=(tr==0)&mask;yes=(tr==1)&mask;un=(rel==0)&mask;rr=(rel==1)&mask
                        metrics.append(dict(fold=fold["name"],variant=variant,animal=r["animal"],key=r["key"],boundary=name,stratum=stratum,
                            n_not_traceable=int(nt.sum()),false_report_not_traceable=int((nt&reporting).sum()),
                            n_traceable=int(yes.sum()),traceable_retained=int((yes&reporting).sum()),
                            n_unreliable=int(un.sum()),unreliable_reported=int((un&reporting).sum()),
                            n_reliable=int(rr.sum()),reliable_retained=int((rr&reporting).sum()),
                            trace_brier_sum=float(np.sum((p["probabilities"][k,0,(tr>=0)&mask]-tr[(tr>=0)&mask])**2)),
                            trace_known=int(((tr>=0)&mask).sum()),
                            reliability_brier_sum=float(np.sum((p["probabilities"][k,1,(rel>=0)&mask]-rel[(rel>=0)&mask])**2)),
                            reliability_known=int(((rel>=0)&mask).sum())))
                        valid=d["valid"][k]&mask
                        for mode,curve in (("reported",rep[k]),("raw_position_branch",p["rows"][k])):
                            err=np.abs(curve[valid]-d["rows"][k,valid])*1.12
                            position.append(dict(fold=fold["name"],variant=variant,key=r["key"],animal=r["animal"],quantity=name,kind="boundary",mode=mode,stratum=stratum,**error_summary(err,int(valid.sum()))))
                    failures=(d["trace_target"][k]==0)&np.isfinite(rep[k])
                    spatial.append(dict(fold=fold["name"],variant=variant,key=r["key"],boundary=name,
                        false_reporting_columns=int(failures.sum()),longest_false_reporting_run=max([hi-lo for lo,hi in runs(failures)],default=0),
                        unreliable_fraction=float(np.mean(state[k]==3)),not_traceable_fraction=float(np.mean(state[k]==2))))
                gt=np.where(d["valid"],d["rows"],np.nan);tgt=thickness(gt,d["shadow"])
                for mode,curves in (("reported",rep),("raw_position_branch",p["rows"])):
                    thick=thickness(curves,d["shadow"])
                    for j,(name,_,_) in enumerate(LAYER_DEFS+[("INNER_RETINA","ILM","IPL_INL")]):
                        valid=np.isfinite(tgt[j]);err=np.abs(thick[j,valid]-tgt[j,valid])
                        position.append(dict(fold=fold["name"],variant=variant,key=r["key"],animal=r["animal"],quantity=name,kind="thickness",mode=mode,stratum="all",**error_summary(err,int(valid.sum()))))
    # Frozen deployment cutoffs transfer by median from development calibration
    # models. They are not calibrated on the all-label model's own fit outputs.
    for variant in ("vessels","no_vessels"):
        transfer=[]
        for k,name in enumerate(SURFACE_NAMES):
            cc=[v[k] for (fold,vv),v in calibrations.items() if vv==variant and v[k]["supported"]]
            transfer.append(dict(boundary=name,supported=bool(cc),
                trace_cutoff=float(np.median([x["trace_cutoff"] for x in cc])) if cc else 1.01,
                reliability_cutoff=float(np.median([x["reliability_cutoff"] for x in cc])) if cc else 1.01,
                not_traceable_cutoff=float(np.median([x["not_traceable_cutoff"] for x in cc if x["not_traceable_cutoff"]>=0])) if any(x["not_traceable_cutoff"]>=0 for x in cc) else -1,
                passes_calibration=all(x["passes_calibration"] for x in cc) if cc else False,
                supported_calibration_folds=len(cc)))
        write_json(OUT/"calibration"/f"deployment_{variant}.json",dict(thresholds=transfer,experimental=True,
            caveat="Transferred from excluded models; all-label distribution shift not independently calibrated."))
    write_csv(OUT/"evaluation/state_counts.csv",metrics);write_csv(OUT/"evaluation/position_thickness_per_record.csv",position)
    write_csv(OUT/"evaluation/spatial_failures.csv",spatial)
    # Exact pooled counts, not a mean of ratios or mean of per-image quantiles.
    for variant in ("vessels","no_vessels"):
        for animal in ["ALL"]+sorted({r["animal"] for r in metrics}):
            for name in SURFACE_NAMES:
                for stratum in ("all","vessel","no_vessel","cnv_outline","outside_cnv_outline"):
                    rows=[r for r in metrics if r["variant"]==variant and r["boundary"]==name and r["stratum"]==stratum and (animal=="ALL" or r["animal"]==animal)]
                    totals={k:sum(r[k] for r in rows) for k in ("n_not_traceable","false_report_not_traceable","n_traceable","traceable_retained","n_unreliable","unreliable_reported","n_reliable","reliable_retained")}
                    ratios={out:totals[num]/totals[den] if totals[den] else None for out,num,den in
                        (("false_report_rate_not_traceable","false_report_not_traceable","n_not_traceable"),("traceable_retention","traceable_retained","n_traceable"),
                         ("unreliable_report_rate","unreliable_reported","n_unreliable"),("reliable_retention","reliable_retained","n_reliable"))}
                    summary.append(dict(variant=variant,animal=animal,boundary=name,stratum=stratum,**totals,**ratios))
    write_csv(OUT/"evaluation/state_summary.csv",summary)
    write_json(OUT/"evaluation/complete.json",dict(seconds=time.monotonic()-start,
        evaluated_animals=["TS165","TS247","TS283","TS325"],untouched_final_test=False,human_override_used_for_scoring=False,
        release_status="experimental regardless of apparent training/fit improvements"))
    progress("calibration and held-animal evaluation complete")

if __name__=="__main__":run()
