"""Measured release report and figures; never edits training data or labels."""
from collections import defaultdict,Counter
import csv
import json
import time
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from eight_surface.config import SURFACE_NAMES,LAYER_DEFS
from eight_surface.labels import load_label
from eight_surface import provenance as P
from .common import *
from .decisions import thickness,runs
from .evaluate import error_summary

def table(rows,keys):
    def s(x):
        if x is None:return "—"
        if isinstance(x,float):return f"{x:.3f}"
        return str(x)
    return "| "+" | ".join(keys)+" |\n|"+"|".join(["---"]*len(keys))+"|\n"+"\n".join("| "+" | ".join(s(r.get(k)) for k in keys)+" |" for r in rows)

def pooled_errors(m):
    groups=defaultdict(list);den=Counter();confusion=Counter()
    for r in m["records"]:
        if r["animal"] not in ("TS165","TS247","TS283","TS325"):continue
        d=load_npz(r["cache"]["path"])
        for variant in ("vessels","no_vessels"):
            raw=load_npz(OUT/"predictions/labels"/r["animal"]/variant/f"{r['key']}.npz")
            pred=load_npz(OUT/"evaluation/predictions"/r["animal"]/variant/f"{r['key']}.npz")
            cal=json.loads((OUT/"calibration"/f"{r['animal']}_{variant}.json").read_text())["thresholds"]
            for k,name in enumerate(SURFACE_NAMES):
                for head,target_name,cutoff in ((0,"trace_target","trace_cutoff"),(1,"reliability_target","reliability_cutoff")):
                    target=d[target_name][k];prediction=raw["probabilities"][k,head]>=cal[k][cutoff]
                    for truth in (0,1):
                        for guess in (0,1):
                            key=(variant,r["animal"],name,target_name,truth,guess)
                            confusion[key]+=int(((target==truth)&(prediction==guess)).sum())
            for mode,curve in (("reported",pred["reported"]),("raw_position_branch",raw["rows"])):
                gt=np.where(d["valid"],d["rows"],np.nan)
                errors=np.concatenate([np.abs(curve-gt)*1.12,np.abs(thickness(curve,d["shadow"])-thickness(gt,d["shadow"]))])
                eligible=np.concatenate([d["valid"],np.isfinite(thickness(gt,d["shadow"]))])
                names=SURFACE_NAMES+[x[0] for x in LAYER_DEFS]+["INNER_RETINA"]
                for i,name in enumerate(names):
                    for stratum,mask in (("all",np.ones(512,bool)),("vessel",d["vessel"]),("no_vessel",~d["vessel"]),("cnv_outline",d["cnv"]),("outside_cnv_outline",~d["cnv"])):
                        good=eligible[i]&mask
                        for animal in (r["animal"],"ALL"):
                            key=(variant,mode,animal,"boundary" if i<8 else "thickness",name,stratum)
                            groups[key].append(errors[i,good]);den[key]+=int(good.sum())
    rows=[dict(zip(("variant","mode","animal","kind","quantity","stratum"),key),**error_summary(np.concatenate(values),den[key])) for key,values in groups.items()]
    write_csv(OUT/"evaluation/position_thickness_pooled.csv",rows)
    write_csv(OUT/"evaluation/head_confusion.csv",[dict(zip(("variant","animal","boundary","head","human_target","predicted_class"),k),count=v) for k,v in confusion.items()])
    return rows

def figures(examples,m):
    colours=plt.get_cmap("tab10").colors
    directory(OUT/"reports/images")
    saved=[]
    cache={}
    for index,g in enumerate(examples):
        sid=g["scan_id"];b=g["bscan"];k=SURFACE_NAMES.index(g["boundary"])
        if sid not in cache:cache[sid]=load_npz(OUT/"volumes"/sid/"measurements.npz")
        d=cache[sid];images=np.load(OUT/"volumes"/sid/"images.npy",mmap_mode="r")
        offset=int(d["label_offset"]);im=images[b];lo,hi=g["lo"],g["hi"]
        fig,axes=plt.subplots(2,1,figsize=(12,7),gridspec_kw={"height_ratios":[3,1]},constrained_layout=True)
        ax=axes[0];vmin,vmax=np.percentile(im,[2,99]);ax.imshow(im,cmap="gray",vmin=vmin,vmax=vmax,aspect="auto")
        for j in range(8):
            ax.plot(d["reported_positions"][b,j]-offset,color=colours[j],lw=1 if j!=k else 2,alpha=.4 if j!=k else 1)
        ax.plot(d["uncertain_estimates"][b,k]-offset,color="#ffba59",lw=2,ls="--",label="Uncertain contextual candidate")
        ax.axvspan(lo,hi,color="#ffba59",alpha=.1)
        ax.set(xlim=(max(0,lo-85),min(512,hi+85)),ylabel="Cropped canonical depth (px)",title=f"{g['queue_id']} · {sid} · B-scan {b} · {g['boundary']}\n{g['role']} · experimental, not validated measurements")
        finite=np.r_[d["reported_positions"][b,:,max(0,lo-85):min(512,hi+85)].ravel(),d["uncertain_estimates"][b,k,lo:hi]]
        finite=finite[np.isfinite(finite)]-offset
        if len(finite):ax.set_ylim(min(im.shape[0],np.max(finite)+35),max(0,np.min(finite)-35))
        ax.legend(loc="lower right",fontsize=8)
        axes[1].plot(d["probabilities"][b,k,0],label="P(traceable)",color="#2166ac")
        axes[1].plot(d["probabilities"][b,k,1],label="P(reliable)",color="#b2182b")
        for a,z in runs(d["state"][b,k]==2):axes[1].axvspan(a,z,color="#b34bd2",alpha=.25)
        for a,z in runs(d["vessel"][b]):axes[1].axvspan(a,z,color="#289fff",alpha=.15)
        axes[1].set(xlim=ax.get_xlim(),ylim=(0,1),xlabel="Native A-line",ylabel="Probability");axes[1].legend(loc="upper right",fontsize=8)
        path=OUT/"reports/images"/f"{g['queue_id']}.png";fig.savefig(path,dpi=130);plt.close(fig);saved.append(path)
    # An image sheet uses a readable small subset; all thirty full panels saved.
    chosen=[]
    for sid in cache:
        item=next((g for g in examples if g["scan_id"]==sid and g["role"]=="contextual estimate"),next(g for g in examples if g["scan_id"]==sid))
        chosen.append(item)
    fig,axes=plt.subplots(2,2,figsize=(16,10),constrained_layout=True)
    for ax,g in zip(axes.ravel(),chosen):
        im=plt.imread(OUT/"reports/images"/f"{g['queue_id']}.png");ax.imshow(im);ax.axis("off")
    fig.savefig(OUT/"reports/review_overview.png",dpi=130);plt.close(fig)

def classified_cnv_strata(m):
    from cnv_review_v1.data import decode_mask
    rows=[];sources=[]
    for path in (ROOT/"outputs/cnv_review_v1/regions").glob("*_regions.json"):
        source=json.loads(path.read_text());sid=source["scan_id"]
        if sid not in m["sources"]:continue
        expected=m["sources"][sid]
        if Path(source["source_volume"]).resolve()!=Path(expected["source"]["path"]).resolve() or source["native_shape"]!=expected["native_shape"][:2]:
            raise ValueError("Classified CNV review has incompatible native geometry")
        sources.append(dict(source=fingerprint(path),categories=Counter(region["category"] for region in source["regions"])))
        for region in source["regions"]:
            mask=decode_mask(region["runs"],tuple(source["native_shape"]))
            for r in [r for r in m["records"] if r["scan_id"]==sid and mask[r["bscan"]].any()]:
                d=load_npz(r["cache"]["path"]);columns=mask[r["bscan"]]
                for variant in ("vessels","no_vessels"):
                    pred=load_npz(OUT/"evaluation/predictions"/r["animal"]/variant/f"{r['key']}.npz")
                    for k,name in enumerate(SURFACE_NAMES):
                        nt=(d["trace_target"][k]==0)&columns;un=(d["reliability_target"][k]==0)&columns
                        rel=(d["reliability_target"][k]==1)&columns;finite=np.isfinite(pred["reported"][k])
                        valid=d["valid"][k]&columns;err=np.abs(pred["reported"][k,valid]-d["rows"][k,valid])*1.12
                        rows.append(dict(key=r["key"],animal=r["animal"],boundary=name,variant=variant,region_id=region["id"],
                            category=region["category"],n_not_traceable=int(nt.sum()),false_reports=int((nt&finite).sum()),
                            n_unreliable=int(un.sum()),unreliable_reports=int((un&finite).sum()),n_reliable=int(rel.sum()),reliable_reports=int((rel&finite).sum()),
                            **error_summary(err,int(valid.sum()))))
    write_json(OUT/"data/cnv_region_strata_provenance.json",sources)
    write_csv(OUT/"evaluation/classified_cnv_region_strata.csv",rows)

def run():
    start=time.monotonic();m=json.loads((OUT/"data/manifest.json").read_text());census=json.loads((OUT/"data/census.json").read_text())
    examples=json.loads((OUT/"review_packs/queue.json").read_text())["examples"]
    protocol=json.loads((OUT/"models/protocol.json").read_text())
    roles=[]
    for fold in protocol["folds"]:
        for r in m["records"]:
            with np.load(r["cache"]["path"],allow_pickle=False) as cached:
                d={key:cached[key] for key in ("valid","trace_target","reliability_target")}
            role=next((role for role in ("evaluation","calibration","training") if r["animal"] in fold[role]),"unused")
            for k,name in enumerate(SURFACE_NAMES):
                roles.append(dict(fold=fold["name"],key=r["key"],animal=r["animal"],role=role,boundary=name,
                    positions=int(d["valid"][k].sum()),trace_positive=int((d["trace_target"][k]==1).sum()),
                    trace_negative=int((d["trace_target"][k]==0).sum()),reliability_positive=int((d["reliability_target"][k]==1).sum()),
                    reliability_negative=int((d["reliability_target"][k]==0).sum())))
    write_csv(OUT/"data/dataset_roles_and_support.csv",roles)
    summary=list(csv.DictReader((OUT/"evaluation/state_summary.csv").open()))
    errors=pooled_errors(m)
    classified_cnv_strata(m)
    state_rows=[]
    for r in summary:
        if r["animal"]=="ALL" and r["stratum"]=="all" and r["variant"]=="vessels":
            state_rows.append(dict(boundary=r["boundary"],not_traceable_false_report_pct=100*float(r["false_report_rate_not_traceable"]) if r["false_report_rate_not_traceable"] else None,
                reliable_retention_pct=100*float(r["reliable_retention"]) if r["reliable_retention"] else None,
                unreliable_report_pct=100*float(r["unreliable_report_rate"]) if r["unreliable_report_rate"] else None))
    rawcounts=Counter();saved_examples=[];support=defaultdict(Counter);changed=[]
    for r in m["records"]:
        try:verify(r["label"])
        except RuntimeError:changed.append(r["key"])
        l=load_label(r["label"]["path"]);d=load_npz(r["cache"]["path"])
        for k,name in enumerate(SURFACE_NAMES):
            v=P.record_visibility(l)[k];rel=P.record_reliability(l)[k]
            support[name]["position_columns"]+=int(d["valid"][k].sum())
            if d["valid"][k].any():support[name]["position_records"]+=1
            for state,mask in (("not_traceable",v==2),("unreliable",rel==2),("explicit_visible",v==1),("explicit_reliable",rel==1),
                ("visibility_unknown",v==0),("reliability_unknown",rel==0)):
                rawcounts[state]+=int(mask.sum());support[name][state]+=int(mask.sum())
                if mask.any() and state in ("not_traceable","unreliable","explicit_reliable") and sum(e["state"]==state for e in saved_examples)<4:
                    lo,hi=max(runs(mask),key=lambda z:z[1]-z[0]);saved_examples.append(dict(state=state,key=r["key"],boundary=name,lo=int(lo),hi=int(hi),verdict=l["verdict"],label=r["label"]["path"]))
        rawcounts["image_excluded_columns"]+=int(l["region_excluded"].sum())
        rawcounts["taper_boundary_columns"]+=int(l["local_taper"].sum());rawcounts["displaced_boundary_columns"]+=int(l["local_displaced"].sum())
        if not d["valid"].any() and ((d["trace_target"]==0).any() or (d["reliability_target"]==0).any()):rawcounts["state_negative_records_without_positions"]+=1
    write_json(OUT/"data/saved_state_counts.json",dict(raw_saved_effective_states=dict(rawcounts),training_states=census["counts"],examples=saved_examples,source_labels_changed_since_freeze=changed))
    support_rows=[dict(boundary=name,**support[name]) for name in SURFACE_NAMES];write_csv(OUT/"data/boundary_support.csv",support_rows)
    figures(examples,m)
    volumes=json.loads((OUT/"reports/volumes.json").read_text())
    coverage=[]
    for volume in volumes:
        d=load_npz(OUT/"volumes"/volume["scan_id"]/"measurements.npz")
        for k,name in enumerate(SURFACE_NAMES):
            coverage.append(dict(scan_id=volume["scan_id"],animal=volume["animal"],boundary=name,
                reported_fraction=float(np.mean(d["state"][:,k]==1)),not_traceable_fraction=float(np.mean(d["state"][:,k]==2)),
                uncertain_fraction=float(np.mean(d["state"][:,k]==3)),insufficient_calibration_fraction=float(np.mean(d["reason"][:,k]==9)),
                estimate_columns=int(np.isfinite(d["uncertain_estimates"][:,k]).sum())))
    write_csv(OUT/"reports/volume_boundary_coverage.csv",coverage)
    runtimes=[]
    for path in sorted((OUT/"models").glob("*/complete.json")):
        d=json.loads(path.read_text());runtimes.append(dict(stage="final explicit-state head training (paired)",item=path.parent.name,seconds=d["seconds"]))
    for path in sorted((OUT/"models").glob("*/position_history.csv")):
        rows=list(csv.DictReader(path.open()))
        if rows:runtimes.append(dict(stage="completed position training, reused unchanged",item=path.parent.name,seconds=float(rows[-1]["elapsed_this_invocation_s"])))
    for path in sorted((OUT/"development_rejected_state_assumption/models").glob("*/complete.json")):
        d=json.loads(path.read_text());runtimes.append(dict(stage="superseded development pass incl position/features/state (overlaps position time)",item=path.parent.name,seconds=d["seconds"]))
    for sid in [v["scan_id"] for v in volumes]:
        d=json.loads((OUT/"volumes"/sid/"neural_complete.json").read_text());runtimes.append(dict(stage="source read+neural volume+heldout context",item=sid,seconds=d["total_s"]))
    for v in volumes:runtimes.append(dict(stage="registration+estimates+exports",item=v["scan_id"],seconds=v["cpu_export_s"]))
    for path in sorted((OUT/"volumes").glob("*/alignment_runtime.json")):
        runtimes.append(dict(stage="registration precomputed separately",item=path.parent.name,seconds=json.loads(path.read_text())["seconds"]))
    runtimes.append(dict(stage="audit",item="199 records",seconds=census["runtime_s"]))
    runtimes.append(dict(stage="calibration+evaluation",item="4 excluded animals",seconds=json.loads((OUT/"evaluation/complete.json").read_text())["seconds"]))
    write_csv(OUT/"reports/runtimes.csv",runtimes)
    hidden_path=OUT/"evaluation/hidden_position_recovery.csv"
    hidden=list(csv.DictReader(hidden_path.open())) if hidden_path.exists() else []
    recovery=sum(int(x["recovered_columns"]) for x in hidden);eligible=sum(int(x["eligible_columns"]) for x in hidden)
    estimate_items=sum(g["role"]=="contextual estimate" for g in examples)
    report=f'''# octa-seg_v1 — START HERE

**Experimental review release. The learned reporting states FAILED validation. Do not treat these outputs as validated research measurements.**

Double-click [OPEN_OCTA_SEG_V1.cmd](OPEN_OCTA_SEG_V1.cmd) from Windows to activate `octa` and open the 30-example queue in `code/cnv_review_v1`. Codex's offscreen preview verifies rendering only; it does not establish that a launched window is visible on your desktop.

The queue contains **{estimate_items} contextual-estimate examples**, {26-estimate_items} withheld regions lacking sufficient context, and four controls. Use the queue bar at the top. All four volumes are complete (512 B-scans each); arbitrary native rows remain available.

![Four-volume overview](reports/review_overview.png)

## What to review

Solid lines are experimental reported segments. Amber dashes are optional uncertain candidates. A not-traceable boundary has a gap, with no candidate continuation. Choose a boundary and A-line to see its probabilities, state and reason. Blue footprints are lateral vessel context, never vessel depth.

Draw to correct the selected range. A new correction remains uncertain until **Approve selected estimate for future position training** is clicked. You can instead keep it uncertain or mark it not traceable. Generic Accept does not approve estimates. Approval of an unchanged automatic candidate is stored as explicit estimate approval, never claimed as a manual stroke. New labels go through the provenance-aware GUI writer to `reviewer/surface_labels`; separate decisions go to `reviewer/estimate_feedback`. They are for v2, not self-training v1. Existing boundary labels and CNV region classifications load with priority and remain intact in their original folders.

## Audit and supervision

The final snapshot has {census['records']} records from 11 animals: {census['verdicts']}. It includes the two latest linked-GUI saves after checking the source, crop, and freshly detected native orientation. {rawcounts['state_negative_records_without_positions']} records with negative state evidence have no eligible positions and are retained for state learning.

Saved field counts (boundary × A-line units): **{rawcounts['not_traceable']:,} not traceable; {rawcounts['unreliable']:,} unreliable; {rawcounts['explicit_visible']:,} explicit visible; {rawcounts['explicit_reliable']:,} explicit reliable**. Unknown visibility: {rawcounts['visibility_unknown']:,}; unknown reliability: {rawcounts['reliability_unknown']:,}. Image exclusions: {rawcounts['image_excluded_columns']:,} A-lines; local automatic joins: {rawcounts['taper_boundary_columns']:,}; local ordering displacement: {rawcounts['displaced_boundary_columns']:,} boundary locations. These categories can overlap and must not be added as mutually exclusive classes.

Exact-stroke positional supervision contains **{census['counts']['positions']:,} eligible boundary locations**. A direct correction does **not** create a positive reliability label: reliability remains masked unless explicitly judged. Positive state marks within an image exclusion are also masked; explicit negatives survive. [saved_state_counts.json](data/saved_state_counts.json) separates raw saved judgments from final training masks. All 160 legacy format-2 records are excluded from position supervision because their stroke extents cannot be recovered; explicit negative whole-boundary decisions remain useful. Rejected reviews supply no position targets. Automatic curves, reviewed-but-undrawn automatic lines, tapers, displacements, shadowed positions and excluded columns do not become position targets. Missing/default state flags stay masked.

Current code and both available historical Git revisions agree: Shift+right-drag means not visible; Alt+right-drag unreliable; Ctrl+right-drag clears image exclusion. No available evidence supports remapping Ctrl+right-drag to unreliable. Nothing was relabeled based on gesture memory. “Not visible” means not traceable in this image, not anatomical absence. [Gesture history](data/gesture_history.json), [per-record audit](data/label_audit.csv), and [saved-state examples](data/saved_state_counts.json).

{table(support_rows,['boundary','position_columns','position_records','not_traceable','unreliable','explicit_reliable'])}

All eight outputs are implemented. Evidence amount differs substantially, especially ILM; **none earns a validated reliability claim**. See [boundary support](data/boundary_support.csv) and calibration files for per-fold missing positives/negatives.

## Model and validation

The position branch retains the updated eight-head, base-8 U-Net architecture. Four evaluation models start from random weights and train for 1,800 steps on exact manual evidence, using native-depth 128-A-line crops. The separate all-label branch starts from the requested updated checkpoint and fine-tunes for 600 steps. Its inherited upstream weights were trained with the earlier legacy edited-surface approximation; v1 introduces no such position targets. This inherited all-label model is a fit/review provider, never the evaluation model.

Two separate sigmoid heads learn traceability and reliability from the predicted depth distribution, 17 local axial intensity samples, uncertainty and lateral context. The state branch is trained after freezing the position branch: negative-only records cannot move position targets. Its convolutions span 43 lateral columns. Nine hundred state steps are fixed in advance. Head scores are retained as probabilities, but they are **not proven probability-calibrated**; empirical operating thresholds are calibrated separately.

Animal roles rotate: evaluate TS165/calibrate TS247; evaluate TS247/calibrate TS283; evaluate TS283/calibrate TS325; evaluate TS325/calibrate TS165. Each pair is excluded from that fold's entire training set, including neighboring slices. The remaining animals supply only the evidence actually available. No evaluation network inherits an all-label checkpoint. These are development cross-validation results, not an untouched final test. [Protocol](models/protocol.json), [manifest](data/manifest.json).

Thresholds minimize false positive state decisions subject to at least 70% affirmative-state retention on the calibration animal. Specificity cannot be established when a calibration class is absent. Fewer than 20 affirmative calibration marks disable reporting for that boundary/fold; the CSV exposes these gaps rather than treating withholding as validation success. Thresholds are never set by withholding a fixed fraction of each volume. The all-label workflow transfers median calibration thresholds from supported excluded models, with a documented distribution-shift limitation. No validated reporting claim is made.

Held-animal results below apply **before** human overrides. A zero false-report rate after applying human denials would merely test the override rule, not learned performance. The joint reporting decision also requires a finite in-image noncrossing position; therefore joint retention can be lower than the per-head calibration constraint.

{table(state_rows,['boundary','not_traceable_false_report_pct','reliable_retention_pct','unreliable_report_pct'])}

False-report rates must be read with retention: zero reporting caused by missing calibration evidence is an abstention failure, not success. [State counts and strata](evaluation/state_summary.csv), [position and thickness errors including p95/max/>20 µm](evaluation/position_thickness_pooled.csv), [failure run lengths](evaluation/spatial_failures.csv). Tables include animal, boundary, vessel presence and available CNV-outline strata. CNV outlines are inspection context, not boundary measurability truth; outside a saved outline does not establish absence of CNV.

The paired vessel ablation omits both the vessel feature and vessel-derived defaults, with the same position branch, state architecture, initialization, sampling and training budget. Manual saved masks (including empty reviewed masks/drafts) take priority over automatic proposals. Source hashes/origins and native footprints are saved in the manifest. Vessel defaults only supervise unknown reliability at lower within-class weight (0.2); no vessel creates a not-traceable target or a positive target outside vessels. At inference, ILM still needs image evidence, RNFL/GCL and every deeper boundary default to unreliable under a footprint unless a manual per-boundary reliable judgment overrides that default. These are working rules, not human boundary annotations. The paired tables report both reductions in false reporting and losses of retention; no blanket benefit is claimed.

## Contextual candidates and measurements

The estimator requires finite reliable lateral anchors on both sides in the central slice and in both neighboring slices, and a gap no longer than 128 A-lines. Interior neighboring U-Net position proposals may themselves be uncertain: they supply context, not measurement truth. Adjacent canonical images are translation-registered in native coordinates; shifts exceeding 6 lateral or 12 axial pixels, image correlation below 0.65, local patch correlation below 0.45, neighbor disagreement above 12 px or central-model disagreement above 16 px stop estimation. Both neighboring shapes are endpoint-adjusted without smoothing their deformation. Not-traceable corridors, image exclusions, rejected images, missing context and crossings stop estimates. No generated candidate is reused as context for another estimate. These context thresholds are engineering settings, not tuned on evaluation targets. Agreement between neighboring proposals can reflect shared model error; it is not evidence of positional accuracy in true signal loss.

The held-animal hidden-position experiment recovered **{recovery}/{eligible} deliberately hidden eligible columns** across {len(hidden)} trials. This masks position output while leaving the image intact. It is **not** a simulation of biological signal loss and does not give real unreliable regions position ground truth. [Recovery table](evaluation/hidden_position_recovery.csv) reports abstentions as well as error where recovery was possible.

Each volume's `measurements.npz` stores full canonical `reported_positions`, separate `uncertain_estimates`, both state probabilities, decision and context reasons, raw diagnostic position outputs, native masks, and `primary_thickness_um`. The primary thickness array uses reported boundaries only and is NaN wherever either endpoint is withheld or a column is shadowed. No uncertain-estimate thickness is produced. Despite its primary-output role, this v1 thickness remains experimental. Raw position diagnostics must not be rendered as an estimated continuation in not-traceable regions. GUI compatibility packs put **only reported rows** in `surfaces`, so older consumers receive gaps safely.

{table(volumes,['scan_id','n_bscans','reported_fraction','unreliable_fraction','not_traceable_fraction','estimate_gaps','estimate_columns'])}

[Volume rankings](reports/volume_rankings.csv) use the fraction of all 8×512×512 locations in the uncertain state. [B-scan rankings](reports/bscan_rankings.csv) use uncertain fraction plus longest uncertain run/512. Withheld fraction includes both uncertain and not traceable and is reported separately. These are segmentation-review priorities; acquisition QC is saved separately and is never called scan quality here. Adjacent state disagreement is descriptive, since true CNV deformation and motion can both change states.

## Files and reproducibility

- [30-example queue](review_packs/queue.csv), full providers in `review_packs/automatic`, and selected image packs in `review_packs/selected`.
- [Launch configuration](launch_config.json); [runtime measurements](reports/runtimes.csv); [progress file](progress.json).
- Training weights and optimizer/RNG states are checkpointed every 100 steps. Native inference saves every completed B-scan. CPU volume exports and registration have separate completion markers.
- Original sources remain referenced with hashes; all new models, arrays, packs, reports and feedback stay inside this version folder. The 2-GB source array is never transposed; individual canonical images are prepared using detected orientation. Read input only from processedVolumes.mat.
- Existing human label bytes changed since the audit: {changed or 'none detected'}. Such external user changes, if any, are never folded silently into the frozen dataset.

From Command Prompt, `call D:\\Anaconda\\Scripts\\activate.bat octa`, then `cd /d G:\\OCT_TreeShrew\\octa` and `set PYTHONPATH=G:\\OCT_TreeShrew\\octa\\code`. Run `python -m octa_seg_v1.release` to resume missing stages under a single-process lock. A completed release verifies its saved artifacts and does not retrain or overwrite. Individual stage commands are documented in [implementation notes](IMPLEMENTATION.md). Use octa-seg_v2 for any new training or threshold decisions.
'''
    (OUT/"START_HERE.md").write_text(report,encoding="utf-8")
    notes='''# octa-seg_v1 implementation and commands

Versioned implementation: `code/octa_seg_v1`. Integration edits add an opt-in editor/queue hook, an initial-scan setting, and read-only fallback for existing CNV region classifications to `code/cnv_review_v1`. The existing vessel-proposal selector also now recognizes an empty manually brushed mask as saved work; this changed none of the frozen cohort's masks.

Activate octa before running Python. Stages, in order:

```
python -m octa_seg_v1.audit
python -m octa_seg_v1.train
python -m octa_seg_v1.predict labels
python -m octa_seg_v1.evaluate
python -m octa_seg_v1.predict volumes
python -m octa_seg_v1.export
python -m octa_seg_v1.queue
python -m octa_seg_v1.report
python -m octa_seg_v1.verify
```

Use the release runner for resuming, not multiple concurrent stage commands. Inspect progress.json and the runner lock before restarting. All completed position/state checkpoints are preserved. The source volume and neighboring context are read again only when a volume's neural stage was interrupted before its completion marker; completed per-B-scan network inference is reused.

Tests run in separate processes because this installation's Torch and NumPy BLAS libraries load incompatible OpenMP runtimes. No unsafe duplicate-runtime override is used. Neural training/inference use Torch and non-BLAS array operations. Registration, evaluation, plotting and GUI work are Torch-free.

Tests:
```
python -m unittest octa_seg_v1.test_contract -v
python -m unittest octa_seg_v1.test_neural -v
python -m unittest octa_seg_v1.test_reviewer cnv_review_v1.test_review -v
```

Operational state codes: 1 reliable (experimental); 2 not traceable; 3 uncertain. Reason codes are in `octa_seg_v1.decisions.REASONS`; context_reason 0 means a candidate met all context gates, 1 means insufficient/forbidden context. All arrays use B-scan,boundary,A-line except masks (B-scan,A-line), images (B-scan,depth,A-line), probabilities (B-scan,boundary,traceability/reliability,A-line), and thickness (B-scan,layer,A-line).

Feedback is intentionally outside the frozen dataset. `approved_position_mask` in the GUI adapter requires a latest explicit per-column approval, unchanged stored coordinates, affirmative current visibility/reliability, and no displacement/exclusion/rejection. An unchanged approved automatic candidate retains `local_reviewed`, not `local_drawn`; a v2 importer must opt into explicit approval events separately. Generic review verdicts never grant this approval. A later denial or changed position invalidates earlier approval.

Limitations: four evaluation animals; sparse clustered state annotations and very few direct ILM positions; state heads share evidence features across boundaries; all-label initialization inherits legacy approximation; no calibrated probability or clinical/research reliability guarantee; fixed motion/context gates can reject recoverable shapes; no OCTA intensity channel was trained (OCT image plus en-face OCTA-derived vessel context); automatic vessel seams/lesion artifacts remain possible; local rigid translations cannot resolve all nonrigid motion. No full 314-volume run was attempted.
'''
    (OUT/"IMPLEMENTATION.md").write_text(notes,encoding="utf-8")
    progress("reports and representative images ready",seconds=time.monotonic()-start)

if __name__=="__main__":run()
