"""Compact old/new full-volume measurement-map comparisons."""
import argparse
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def run(a):
    a.out.mkdir(parents=True, exist_ok=True)
    for new in sorted(p for p in a.new.iterdir() if p.is_dir() and p.name != "packs"):
        old=a.old/new.name
        with np.load(new/"experimental_measurements.npz") as d: nm=d["experimental_thickness_um"]
        with np.load(old/"experimental_measurements.npz") as d: om=d["experimental_thickness_um"]
        # Inner-retina is the third reported thickness band in this saved format.
        oi, ni=om[2], nm[2]; lim=np.nanpercentile(np.r_[oi.ravel(),ni.ravel()],(2,98))
        fig,ax=plt.subplots(1,3,figsize=(12,3.5),constrained_layout=True)
        for x,title,im in zip(ax,("Previous all-label","Updated all-label","Updated − previous"),(oi,ni,ni-oi)):
            h=x.imshow(im,aspect="auto",cmap="viridis" if title!="Updated − previous" else "coolwarm",vmin=lim[0] if title!="Updated − previous" else -20,vmax=lim[1] if title!="Updated − previous" else 20)
            x.set(title=title,xlabel="A-line",ylabel="B-scan"); fig.colorbar(h,ax=x,shrink=.8,label="um")
        fig.suptitle(new.name+" — experimental inner-retina thickness")
        fig.savefig(a.out/(new.name+"_old_vs_updated.png"),dpi=150); plt.close(fig)
if __name__=="__main__":
 p=argparse.ArgumentParser(); p.add_argument("--old",type=Path,required=True); p.add_argument("--new",type=Path,required=True); p.add_argument("--out",type=Path,required=True); run(p.parse_args())
