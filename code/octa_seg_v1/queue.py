"""Diverse 30-example feedback queue; review packs only, no annotation writes."""
import json
import numpy as np
from eight_surface.config import SURFACE_NAMES,CASCADE_VERSION
from .common import *
from .decisions import runs

def choose(gaps,ranks,measurements):
    selected=[]
    def separated(g):return all(g["scan_id"]!=s["scan_id"] or abs(g["bscan"]-s["bscan"])>=16 for s in selected)
    available=[dict(g,role="contextual estimate") for g in gaps if not g["previously_reviewed"] and g["length"]>=4]
    # Greedy diversity bonus makes boundary, animal, vessel/CNV context and gap
    # size matter explicitly; fixed minimum B-scan spacing avoids near copies.
    counts={}
    while available and len(selected)<26:
        options=[g for g in available if separated(g)]
        if not options:break
        def score(g):
            categories=(g["animal"],g["boundary"],"cnv" if g["cnv_fraction"] else "no_cnv",
                "vessel" if g["vessel_fraction"] else "no_vessel","large" if g["length"]>=32 else "small")
            return g["length"]/128+sum(1/(1+counts.get(c,0)) for c in categories)
        g=max(options,key=score);selected.append(g);available.remove(g)
        for c in (g["animal"],g["boundary"],"cnv" if g["cnv_fraction"] else "no_cnv",
                  "vessel" if g["vessel_fraction"] else "no_vessel","large" if g["length"]>=32 else "small"):
            counts[c]=counts.get(c,0)+1
    # If safe contexts are scarce, include withheld regions with no estimate.
    # Do not relax registration or bridge forbidden regions to fill the queue.
    for r in sorted(ranks,key=lambda r:-r["priority"]):
        if len(selected)>=26:break
        if r["previously_reviewed"] or not separated(r):continue
        state=measurements[r["scan_id"]]["state"][r["bscan"]]
        spans=[(hi-lo,k,lo,hi) for k in range(8) for lo,hi in runs(state[k]==3)]
        if not spans:continue
        length,k,lo,hi=max(spans)
        selected.append(dict(scan_id=r["scan_id"],animal=r["animal"],bscan=r["bscan"],boundary=SURFACE_NAMES[k],
            lo=int(lo),hi=int(hi),length=int(length),role="withheld; insufficient context",vessel_fraction=r["vessel_fraction"],cnv_fraction=r["cnv_fraction"],previously_reviewed=False))
    for sid in sorted(measurements):
        options=[r for r in ranks if r["scan_id"]==sid and not r["previously_reviewed"] and separated(r)]
        if not options:continue
        r=min(options,key=lambda r:r["withheld_fraction"])
        state=measurements[sid]["state"][r["bscan"]]
        k=int(np.argmax((state==1).sum(1)))
        spans=runs(state[k]==1);lo,hi=max(spans,key=lambda v:v[1]-v[0]) if spans else (0,512)
        selected.append(dict(scan_id=sid,animal=r["animal"],bscan=r["bscan"],boundary=SURFACE_NAMES[k],lo=int(lo),hi=int(hi),length=int(hi-lo),
            role="control: highest reporting coverage in volume",vessel_fraction=r["vessel_fraction"],cnv_fraction=r["cnv_fraction"],previously_reviewed=False))
    return selected[:30]

def run():
    m=json.loads((OUT/"data/manifest.json").read_text());volumes=json.loads((OUT/"reports/volumes.json").read_text())
    measurements={v["scan_id"]:load_npz(OUT/"volumes"/v["scan_id"]/"measurements.npz") for v in volumes}
    ranks=[];gaps=[]
    for sid in measurements:
        ranks.extend(json.loads((OUT/"volumes"/sid/"rankings.json").read_text()))
        gaps.extend(json.loads((OUT/"volumes"/sid/"gaps.json").read_text()))
    examples=choose(gaps,ranks,measurements)
    if len(examples)!=30:raise ValueError(f"Only {len(examples)} queue items available")
    for i,g in enumerate(examples):g["queue_id"]=f"v1-{i+1:02d}"
    write_json(OUT/"review_packs/queue.json",dict(version="octa-seg_v1",examples=examples,
        selection="26 uncertainty-enriched items + 4 highest-coverage controls; minimum 16 B-scans apart per volume; diversity in animal/boundary/context/size",
        no_context_fallback="Withheld gap with no estimate is explicit; no safety thresholds relaxed to fill queue"))
    write_csv(OUT/"review_packs/queue.csv",examples)
    for sid,d in measurements.items():
        selected=[g for g in examples if g["scan_id"]==sid];indices=np.array([g["bscan"] for g in selected])
        images=np.load(OUT/"volumes"/sid/"images.npy",mmap_mode="r")
        offset=int(d["label_offset"])
        save_npz(OUT/"review_packs/selected"/f"{sid}_pack.npz",scan_id=np.array([sid]),surface_names=np.array(SURFACE_NAMES),
            cascade_version=np.array([CASCADE_VERSION]),images=images[indices],bscan_index=indices,
            surfaces=d["reported_positions"][indices]-offset,uncertain_estimates=d["uncertain_estimates"][indices]-offset,
            state=d["state"][indices],reason=d["reason"][indices],probabilities=d["probabilities"][indices],
            shadow=d["shadow"][indices],confidence=np.full_like(d["reported_positions"][indices],np.nan),
            is_control=np.array([g["role"].startswith("control") for g in selected]),suspect=np.ones(len(indices)),px_um=np.array([1.12]),
            selection_role=np.array([g["role"] for g in selected]),label_offset=np.array(offset))
    config=dict(octa_seg_version="octa-seg_v1",segmentations=str(OUT/"review_packs/scan_queue"),
        enface_labels=str(ROOT/"outputs/cnv_labels"),proposals=str(ROOT/"outputs/eight_surface/vasculature_proposals"),
        output=str(OUT/"reviewer"),review_queue=str(OUT/"review_packs/queue.json"),initial_scan=examples[0]["scan_id"],
        manual_sources=[str(ROOT/"outputs/cnv_review_v1/surface_labels"),str(ROOT/"outputs/stage_a/20260909_full_labeled_cohort/manual_review_36/labels"),str(ROOT/"outputs/eight_surface/labels")],
        region_sources=[str(ROOT/"outputs/cnv_review_v1/regions")],
        auto_sources=[dict(name="octa-seg_v1 (experimental; calibrated evidence states)",directory=str(OUT/"review_packs/automatic"))],compare_latest_auto=False)
    write_json(OUT/"launch_config.json",config)
    launcher='@echo off\ncall D:\\Anaconda\\Scripts\\activate.bat octa\nif errorlevel 1 (pause & exit /b 1)\ncd /d G:\\OCT_TreeShrew\\octa\npython code\\cnv_review_v1\\main.py --config "'+str(OUT/"launch_config.json")+'"\nif errorlevel 1 pause\n'
    (OUT/"OPEN_OCTA_SEG_V1.cmd").write_text(launcher,encoding="utf-8")
    progress("30-example review queue ready",contextual_estimate_items=sum(g["role"]=="contextual estimate" for g in examples))

if __name__=="__main__":run()
