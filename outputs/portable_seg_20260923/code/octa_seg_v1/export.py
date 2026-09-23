"""CPU-only measurements, constrained contextual estimates and native GUI packs."""
import json
import shutil
import time
import numpy as np
from eight_surface.config import SURFACE_NAMES,LAYER_DEFS,CASCADE_VERSION
from eight_surface.labels import load_label
from .common import *
from .audit import targets
from .decisions import *

def live_decisions(m,sid,geometry):
    """Read the frozen labels plus saved GUI denials; never write annotations."""
    records={r["bscan"]:Path(r["label"]["path"]) for r in m["records"] if r["scan_id"]==sid}
    for path in (ROOT/"outputs/cnv_review_v1/surface_labels").glob(f"{sid}_b*.npz"):
        lab=load_label(path);records[lab["bscan"]]=path
    out={};provenance=[]
    for b,path in records.items():
        lab=load_label(path)
        d=targets(lab,geometry["shadow"][b],int(np.diff(geometry["retina_band"])[0]),int(geometry["label_offset"]))
        out[b]=dict(trace=d["trace_target"],reliability=d["reliability_target"],excluded=d["excluded"],rejected=lab["verdict"]=="rejected")
        provenance.append(fingerprint(path))
    return out,provenance

def hidden_experiment(sid,m,images,geometry,shifts,scores):
    animal=m["sources"][sid]["metadata"]["animal"]
    cal=json.loads((OUT/"calibration"/f"{animal}_vessels.json").read_text())["thresholds"]
    experiments=[]
    for r in [r for r in m["records"] if r["scan_id"]==sid and sum(r["positions"])]:
        b=r["bscan"]
        if b==0 or b==len(images)-1:continue
        d=load_npz(r["cache"]["path"])
        pred=[load_npz(OUT/"predictions/context_heldout"/sid/f"b{j:04d}.npz") for j in (b-1,b,b+1)]
        rows=np.stack([p["rows"] for p in pred])
        decisions=[decide(p["rows"],p["probabilities"],cal,geometry["vessel"][j]) for p,j in zip(pred,(b-1,b,b+1))]
        rep=np.stack([a[0] for a in decisions]);state=np.stack([a[1] for a in decisions]);reason=np.stack([a[2] for a in decisions])
        for k,name in enumerate(SURFACE_NAMES):
            for length in (8,24,64):
                reliable_position=d["valid"][k] & (d["trace_target"][k]==1) & (d["reliability_target"][k]==1)
                candidates=[(lo,hi) for lo,hi in runs(reliable_position) if hi-lo>=length+2]
                if not candidates:continue
                lo,hi=max(candidates,key=lambda z:z[1]-z[0]);left=(lo+hi-length)//2;right=left+length
                # Deliberately hide position data, NOT image signal. The network
                # has never trained on this animal. Kept distinct from real loss.
                hidden_rep=rep.copy();hidden_state=state.copy();hidden_reason=reason.copy()
                hidden_rep[1,k,left:right]=np.nan;hidden_state[1,k,left:right]=UNCERTAIN;hidden_reason[1,k,left:right]=3
                est,_,_=estimate_context(rows,hidden_rep,hidden_state,hidden_reason,images[b-1:b+2],shifts[b-1:b+1],scores[b-1:b+1],offset=int(geometry["label_offset"]))
                good=np.isfinite(est[1,k,left:right]);err=np.abs(est[1,k,left:right][good]-d["rows"][k,left:right][good])*1.12
                experiments.append(dict(scan_id=sid,animal=animal,key=r["key"],bscan=b,boundary=name,lo=left,hi=right,length=length,
                    recovered_columns=int(good.sum()),eligible_columns=length,median_um=float(np.median(err)) if len(err) else None,
                    p95_um=float(np.quantile(err,.95)) if len(err) else None,max_um=float(np.max(err)) if len(err) else None,
                    experiment="hidden reliable position; image remains intact; animal excluded; no true-signal-loss accuracy claim"))
    return experiments

def run():
    m=json.loads((OUT/"data/manifest.json").read_text())
    cal=json.loads((OUT/"calibration/deployment_vessels.json").read_text())["thresholds"]
    rankings=[];gaps=[];summaries=[];hidden=[]
    for out in sorted((OUT/"volumes").iterdir()):
        if not out.is_dir():continue
        sid=out.name;start=time.monotonic();geometry=load_npz(out/"geometry.npz")
        images=np.load(out/"images.npy",mmap_mode="r")
        marker=out/"complete.json"
        if marker.exists():
            summary=json.loads(marker.read_text());summaries.append(summary)
            rankings.extend(json.loads((out/"rankings.json").read_text()));gaps.extend(json.loads((out/"gaps.json").read_text()))
            hidden.extend(json.loads((out/"hidden_experiment.json").read_text()));continue
        predictions=[load_npz(p) for p in sorted((out/"neural").glob("b*.npz"))]
        if len(predictions)!=512:raise ValueError("Incomplete volume")
        rows=np.stack([p["rows"] for p in predictions]);prob=np.stack([p["probabilities"] for p in predictions]);entropy=np.stack([p["entropy"] for p in predictions])
        guards,provenance=live_decisions(m,sid,geometry)
        # Save raw learned decisions as well as reviewer-aware operational ones.
        automatic=[decide(rows[b],prob[b],cal,geometry["vessel"][b]) for b in range(len(rows))]
        operational=[decide(rows[b],prob[b],cal,geometry["vessel"][b],**guards.get(b,{})) for b in range(len(rows))]
        reported=np.stack([a[0] for a in operational]);state=np.stack([a[1] for a in operational]);reason=np.stack([a[2] for a in operational])
        alignment_path=out/"alignment.npz"
        if alignment_path.exists():a=load_npz(alignment_path);shifts,scores=a["shifts"],a["scores"]
        else:
            progress("checking neighboring-slice registration",scan=sid)
            shifts,scores=alignment(images);save_npz(alignment_path,shifts=shifts,scores=scores)
        progress("estimating eligible uncertain gaps",scan=sid,comparable_adjacent_pairs=int((scores>=.65).sum()))
        estimates,context_reason,items=estimate_context(rows,reported,state,reason,images,shifts,scores,offset=int(geometry["label_offset"]))
        thick=thickness(reported,geometry["shadow"])
        if np.isfinite(thick.transpose(0,2,1)[geometry["shadow"]]).any():raise AssertionError("Shadow thickness")
        if np.isfinite(reported[state!=RELIABLE]).any() or np.isfinite(estimates[state==NOT_TRACEABLE]).any():raise AssertionError("Output contract")
        save_npz(out/"measurements.npz",reported_positions=reported,uncertain_estimates=estimates,state=state,
            reason=reason,context_reason=context_reason,probabilities=prob,entropy=entropy,
            primary_thickness_um=thick,thickness_names=np.array([x[0] for x in LAYER_DEFS]+["INNER_RETINA"]),
            raw_position_branch=rows,automatic_state=np.stack([a[1] for a in automatic]),
            shadow=geometry["shadow"],vessel=geometry["vessel"],cnv=geometry["cnv"],
            label_offset=geometry["label_offset"],surface_names=np.array(SURFACE_NAMES),validated=np.array(False))
        offset=int(geometry["label_offset"])
        # Export only measured rows in the conventional surfaces field. A
        # consumer unaware of the new schema therefore sees gaps, not guesses.
        dest=OUT/"review_packs/automatic"/f"{sid}.npz"
        save_npz(dest,surfaces=reported-offset,uncertain_estimates=estimates-offset,state=state,reason=reason,
            probabilities=prob,context_reason=context_reason,confidence=np.full_like(reported,np.nan),
            surface_names=np.array(SURFACE_NAMES),scan_id=np.array([sid]),cascade_version=np.array([CASCADE_VERSION]),
            source=np.array([m["sources"][sid]["source"]["path"]]),retina_band=geometry["retina_band"],label_offset=geometry["label_offset"],
            bscan_index=np.arange(len(rows)),prediction_checkpoint=np.array(str(OUT/"models/ALL_LABELLED/position.pt")),
            model_family=np.array("octa-seg"),model_version=np.array("octa-seg_v1"),experimental=np.array(True))
        directory(OUT/"review_packs/scan_queue")
        shutil.copy2(PREVIOUS/"cnv_gui/scan_queue"/f"{sid}.npz",OUT/"review_packs/scan_queue"/f"{sid}.npz")
        local_ranks=[]
        for b in range(len(rows)):
            unreliable=float(np.mean(state[b]==UNCERTAIN));withheld=float(np.mean(state[b]!=RELIABLE))
            longest=max([hi-lo for k in range(8) for lo,hi in runs(state[b,k]==UNCERTAIN)],default=0)
            local_ranks.append(dict(scan_id=sid,animal=m["sources"][sid]["metadata"]["animal"],bscan=b,
                unreliable_fraction=unreliable,withheld_fraction=withheld,not_traceable_fraction=float(np.mean(state[b]==NOT_TRACEABLE)),
                estimate_fraction=float(np.mean(np.isfinite(estimates[b]))),longest_unreliable_run=longest,
                priority=unreliable+longest/512,previously_reviewed=b in guards,cnv_fraction=float(geometry["cnv"][b].mean()),vessel_fraction=float(geometry["vessel"][b].mean())))
        for g in items:
            k=SURFACE_NAMES.index(g["boundary"]);b=g["bscan"]
            g.update(scan_id=sid,animal=m["sources"][sid]["metadata"]["animal"],vessel_fraction=float(geometry["vessel"][b,g["lo"]:g["hi"]].mean()),
                cnv_fraction=float(geometry["cnv"][b,g["lo"]:g["hi"]].mean()),previously_reviewed=b in guards)
        examples=hidden_experiment(sid,m,images,geometry,shifts,scores)
        summary=dict(scan_id=sid,animal=m["sources"][sid]["metadata"]["animal"],n_bscans=len(rows),
            unreliable_fraction=float(np.mean(state==UNCERTAIN)),not_traceable_fraction=float(np.mean(state==NOT_TRACEABLE)),
            reported_fraction=float(np.mean(np.isfinite(reported))),estimate_columns=int(np.isfinite(estimates).sum()),estimate_gaps=len(items),
            explicit_denials_overridden=False,primary_shadow_thickness_all_nan=True,not_traceable_estimates_all_nan=True,
            mean_adjacent_state_disagreement=float(np.mean(state[1:]!=state[:-1])),
            registration_comparable_fraction=float(np.mean(scores>=.65)),cpu_export_s=time.monotonic()-start,
            measurements=fingerprint(out/"measurements.npz"),review_pack=fingerprint(dest))
        write_json(out/"rankings.json",local_ranks);write_json(out/"gaps.json",items);write_json(out/"hidden_experiment.json",examples)
        write_json(out/"human_overrides_provenance.json",provenance)
        write_json(out/"acquisition_qc_separate.json",m["sources"][sid].get("qc",{}))
        write_json(marker,summary);summaries.append(summary);rankings.extend(local_ranks);gaps.extend(items);hidden.extend(examples)
        progress("complete volume exported",**summary)
    write_csv(OUT/"reports/volume_rankings.csv",sorted(summaries,key=lambda x:-x["unreliable_fraction"]))
    write_csv(OUT/"reports/bscan_rankings.csv",sorted(rankings,key=lambda x:-x["priority"]))
    write_csv(OUT/"reports/context_gaps.csv",gaps);write_csv(OUT/"evaluation/hidden_position_recovery.csv",hidden)
    write_json(OUT/"reports/volumes.json",summaries)

def align_ready():
    for out in sorted((OUT/"volumes").iterdir()):
        if not (out/"neural_complete.json").exists() or (out/"alignment.npz").exists():continue
        images=np.load(out/"images.npy",mmap_mode="r")
        start=time.monotonic();progress("precomputing registered slice context",scan=out.name)
        shifts,scores=alignment(images);save_npz(out/"alignment.npz",shifts=shifts,scores=scores)
        write_json(out/"alignment_runtime.json",dict(seconds=time.monotonic()-start,comparable_pairs=int((scores>=.65).sum())))
        progress("registration cached",scan=out.name,comparable_pairs=int((scores>=.65).sum()))

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("--align-ready",action="store_true")
    align_ready() if p.parse_args().align_ready else run()
