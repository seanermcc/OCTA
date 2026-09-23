"""Render actual OCT B-scans with old/new/manual inner-boundary overlays."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from octa.volio import ProcessedVolume
from eight_surface.segment import detect_orientation
from stage_a.geometry import preprocess, label_offset
from eight_surface.labels import load_label

CASES = {
    "TS165_OS_2025-04-29_WT_s02_121711": 80,
    "TS247_OD_2024-11-06_D21_s03_104157": 131,
    "TS283_OD_2025-01-29_D7_s02_123712": 350,
    "TS325_OD_2026-05-26_6mo_s01_112940": 106,
}

def run(root):
    root=Path(root); out=root/"actual_oct_overlays"; out.mkdir(exist_ok=True)
    manifest=json.loads((root/"data/manifest.json").read_text())
    old=root.parent/"20260909_full_labeled_cohort/review_queue"
    for sid,b in CASES.items():
        src=manifest["sources"][sid]
        # One complete-volume read is intentional: source HDF5 chunks make
        # single B-scan access slower and this re-derives orientation from data.
        with ProcessedVolume(src["source"]["path"]) as v: full=v.read_volume()
        vhi=bool(detect_orientation(full.mean(axis=(0,1))))
        _,image,_=preprocess(full[b],vhi)
        with np.load(old/sid/"experimental_measurements.npz") as d: before=d["canonical_rows"][b]
        with np.load(root/"review_queue"/sid/"experimental_measurements.npz") as d: after=d["canonical_rows"][b]
        key=f"{sid}_b{b:04d}"
        rec=next((r for r in manifest["records"] if r["key"]==key),None)
        manual=None
        if rec:
            lab=load_label(rec["label"]["path"]); manual=lab["surfaces"][:4]+label_offset(src["label_band"],full.shape[2],vhi)
        lo=max(0,int(np.floor(min(before.min(),after.min())-80)))
        hi=min(image.shape[0],int(np.ceil(max(before.max(),after.max())+100)))
        fig,axes=plt.subplots(1,2,figsize=(15,5),sharey=True,constrained_layout=True)
        for ax,rows,title,color in ((axes[0],before,"Previous all-label model","#ff9d00"),(axes[1],after,"Updated all-label model","#00e5ff")):
            ax.imshow(image[lo:hi].T,cmap="gray",aspect="auto",origin="upper",vmin=np.percentile(image,1),vmax=np.percentile(image,99.5))
            x=np.arange(image.shape[1])
            for i,row in enumerate(rows): ax.plot(x,row-lo,color=color,lw=1.2,label="model" if i==0 else None)
            if manual is not None:
                for i,row in enumerate(manual): ax.plot(x,row-lo,"w:",lw=1.3,label="manual" if i==0 else None)
            ax.set(title=title,xlabel="A-line",ylabel="canonical depth (cropped)"); ax.legend(loc="lower right",fontsize=8)
        kind="control" if sid.startswith("TS165") else "manually reviewed CNV-session candidate"
        fig.suptitle(f"{sid}, B-scan {b} — {kind}; white dotted = direct manual reference where eligible")
        fig.savefig(out/f"{sid}_b{b:04d}_actual_oct_overlay.png",dpi=180); plt.close(fig)

if __name__=="__main__":
 import argparse
 p=argparse.ArgumentParser(); p.add_argument("--root",type=Path,required=True); run(p.parse_args().root)
