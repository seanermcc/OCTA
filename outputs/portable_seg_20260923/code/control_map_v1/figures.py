"""One deterministic figure registry and captions derived from each plotted selection."""
from pathlib import Path
import re
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from . import LAYERS,CAVEAT
from .io import read,npz,write


def slug(value):return re.sub(r"[^a-z0-9]+","_",value.lower()).strip("_")


def frame(path):
    try:return pd.read_csv(path)
    except pd.errors.EmptyDataError:return pd.DataFrame()


class Figures:
    def __init__(self,out,infos,cfg):
        self.out=Path(out);self.infos=infos;self.cfg=cfg;self.records=[];self.captions=[]

    def save(self,fig,family,title,ids,panels,definition,data,version="A/B",anatomical=True):
        number=len(self.records)+1;basename=f"fig_{number:03d}_{slug(title)}";filename=basename+".png"
        if anatomical:
            orientation=self.cfg["orientation"]
            foot=(f"Preliminary; orientation provisional: image N/S/E/W = {orientation['image_north']}/{orientation['image_south']}/"
                  f"{orientation['image_east']}/{orientation['image_west']}; atlas rotation {orientation['rotation_deg']:g} deg.")
        else:foot="Preliminary measurements; uncertainty and acquisition quality are separate."
        fig.suptitle(title,fontsize=13);fig.text(.5,.012,foot,ha="center",fontsize=8)
        fig.tight_layout(rect=[0,.045,1,.95]);fig.savefig(self.out/"fig"/filename,dpi=140,facecolor="white");plt.close(fig)
        selected=[self.infos[s] for s in ids]
        animals=sorted({i["animal"] for i in selected});eyes=sorted({i["animal"]+" "+i["eye"] for i in selected})
        dates=sorted({i["session_date"] for i in selected})
        counts=dict(acquisitions=len(ids),dates=len({(i["animal"],i["eye"],i["session_date"]) for i in selected}),
                    eyes=len(eyes),animals=len(animals))
        caption=(f"## Figure {number:03d} — {title}\n\nFilename: `{filename}`.\n\n"
                 f"{panels}\n\n{definition}\n\n"
                 f"Inclusion version: {version}. A excludes saved/proposed CNV with one maximum-Feret-diameter clearance, "
                 "major vessels with half-local-diameter clearance, sized ONH with half-disc-diameter clearance, "
                 "human image exclusions, shadows and unavailable measurements. B additionally requires full-retina "
                 f"thickness within {self.cfg['normal_sigma']:g} local robust SD of the masked "
                 f"{self.cfg['neighborhood_diameter_um']:g} µm diameter neighborhood median; at least "
                 f"{100*self.cfg['minimum_neighborhood_fraction']:g}% coverage, SD=1.4826×MAD with "
                 f"{self.cfg['local_sigma_floor_um']:g} µm floor. Unknown annotation coverage and unresolved ONH "
                 "exclusions remain flagged in tables/exclusion_coverage.csv; automatic proposals are not human labels.\n\n"
                 f"Sources: {', '.join(data)}. Animals: {', '.join(animals) or 'none'}. Eyes: {', '.join(eyes) or 'none'}. "
                 f"Dates: {', '.join(dates) or 'none'}. Selected acquisitions={counts['acquisitions']}, "
                 f"eye-dates={counts['dates']}, eyes={counts['eyes']}, animals={counts['animals']}; "
                 "pixelwise contributing counts can be lower and are reported in the supporting tables. "
                 f"Acquisition IDs: {', '.join(ids) or 'none'}.\n\n{foot} "
                 "Full retina means ILM→RPE. Photoreceptor composite includes ONL; isolated ONL and ILM→BM are unavailable.\n")
        self.captions.append(caption)
        self.records.append(dict(number=number,family=family,title=title,file="fig/"+filename,
                                 scan_ids=ids,counts=counts,version=version,data=data,caption=caption))

    def finish(self):
        (self.out/"fig/FIGURE_CAPTIONS.md").write_text("# Figure captions\n\n"+"\n".join(self.captions),encoding="utf-8")
        # Only remove obsolete figures produced by this registry, after all new
        # files exist. User-added images are never automatically deleted.
        old=read(self.out/"manifest.json").get("figures",[])
        current={r["file"] for r in self.records}
        for rec in old:
            p=(self.out/rec["file"]).resolve()
            if rec["file"] not in current and p.parent==(self.out/"fig").resolve() and p.name.startswith("fig_"):
                p.unlink(missing_ok=True)
        return self.records


def native(ax,arr,spacing,title,cmap="viridis",limits=None):
    h,w=arr.shape;sy,sx=spacing
    image=ax.imshow(arr,origin="upper",extent=[-.5*sx,(w-.5)*sx,(h-.5)*sy,-.5*sy],
                    interpolation="nearest",cmap=cmap,**(dict(vmin=limits[0],vmax=limits[1]) if limits else {}))
    ax.set(title=title,xlabel="Image x (µm; right)",ylabel="Image y (µm; down)")
    return image


def cellmap(ax,df,cfg,value="value_um",title="",limits=None):
    if df.empty or value not in df:
        ax.text(.5,.5,"No eligible observations",ha="center",va="center",transform=ax.transAxes)
        ax.set(title=title,xlabel="ONH-centered x (µm)",ylabel="ONH-centered y (µm; down)");return None
    # Rows are rectangular observed bins; no filling holes or interpolating values.
    lo=df[["cell_0","cell_1"]].min().to_numpy(int);hi=df[["cell_0","cell_1"]].max().to_numpy(int)
    if np.prod(hi-lo+1)>20_000_000:raise ValueError("Implausibly large map extent; inspect localization")
    arr=np.full((hi[1]-lo[1]+1,hi[0]-lo[0]+1),np.nan)
    arr[df.cell_1.to_numpy(int)-lo[1],df.cell_0.to_numpy(int)-lo[0]]=df[value]
    step=cfg["grid_um"]
    if not np.isfinite(arr).any():
        ax.text(.5,.5,"Insufficient observations for variability",ha="center",va="center",transform=ax.transAxes)
        ax.set(title=title,xlabel="ONH-centered x (µm)",ylabel="ONH-centered y (µm; down)",
               xlim=((lo[0]-.5)*step,(hi[0]+.5)*step),ylim=((hi[1]+.5)*step,(lo[1]-.5)*step))
        return None
    if limits is None and value in ("dates","acquisitions","animals","sd_um","range_um","animal_sd_um"):
        limits=(0,max(1,float(np.nanmax(arr))))
    im=ax.imshow(arr,origin="upper",interpolation="nearest",cmap="viridis",
        extent=[(lo[0]-.5)*step,(hi[0]+.5)*step,(hi[1]+.5)*step,(lo[1]-.5)*step],
        **(dict(vmin=limits[0],vmax=limits[1]) if limits else {}))
    ax.scatter([0],[0],c="red",marker="+",s=45)
    ax.set(title=title,xlabel="ONH-centered x (µm)",ylabel="ONH-centered y (µm; down)")
    return im


def generate(out,infos,loc,cfg):
    out=Path(out);registry=Figures(out,infos,cfg);ids=sorted(infos)
    groups={}
    for s in ids:groups.setdefault((infos[s]["animal"],infos[s]["eye"]),[]).append(s)
    local=frame(out/"tables/local_summaries.csv");exclusion=frame(out/"tables/exclusion_coverage.csv")
    fig,axes=plt.subplots(1,2,figsize=(12,5))
    keys=[a+" "+e for a,e in groups];counts=[len(v) for v in groups.values()]
    axes[0].bar(keys,counts,color="steelblue");axes[0].tick_params(axis="x",rotation=60)
    axes[0].set(title="A. Available acquisitions",ylabel="Acquisitions (count)",xlabel="Animal and eye")
    av=[]
    for name,_,_ in LAYERS:
        selected=local[(local.layer==name)&(local.version=="A")];av.append(selected.eligible_area_um2.sum()/1e6)
    axes[1].bar([x[0] for x in LAYERS],av,color="teal");axes[1].tick_params(axis="x",rotation=60)
    axes[1].set(title="B. Preliminary eligible measurement exposure",ylabel="Summed acquisition area (mm²)",xlabel="Measurement")
    registry.save(fig,1,"Cohort inventory and analysis coverage",ids,
        "A: blue bars count acquisitions by animal/eye. B: teal bars show summed eligible native-pixel area by measurement in mm²; repeats count repeatedly.",
        "Area is acquisition sampling exposure, not unique retinal area. No error bars; blanks mean no available measurements. Unlocalized acquisitions remain included here.",
        ["tables/inventory.csv","tables/local_summaries.csv"],"A",False)
    # Family 2: native registration context, partial edge/candidate overlays and actual linked B-scans.
    for (animal,eye),eye_ids in sorted(groups.items()):
        matches=[m for m in read(out/"registration/matches.json") if m["scan_a"] in eye_ids]
        fig,axes=plt.subplots(1,2,figsize=(11,5))
        measured=[m for m in matches if "residual_um" in m]
        for passed,color,label in ((False,"gray","withheld"),(True,"teal","verified")):
            chosen=[m for m in measured if m["verified"]==passed]
            axes[0].scatter([m["residual_um"] for m in chosen],
                            [m["structural_correlation"] for m in chosen],color=color,label=label,s=20)
        axes[0].set(title="A. Registration support",xlabel="Matched-feature RMS residual (µm)",ylabel="Structural correlation (unitless)")
        axes[0].legend(fontsize=8)
        verified=[m for m in matches if m["verified"]]
        axes[0].text(.03,.03,f"Verified {len(verified)}/{len(matches)} tested pairs",transform=axes[0].transAxes,fontsize=8)
        if verified:
            from .geometry import apply,xy_grid,sample_native
            best=min(verified,key=lambda m:m["residual_um"])
            a=npz(out/"maps"/(best["scan_a"]+"_analysis.npz"));b=npz(out/"maps"/(best["scan_b"]+"_analysis.npz"))
            bmask,bounds=sample_native(b["vessel"],apply(xy_grid(a["enface"].shape,a["spacing"]),np.array(best["matrix"])),b["spacing"])
            overlay=np.where(bounds,a["vessel"].astype(float)+2*(bmask==1),np.nan)
            im=native(axes[1],overlay,a["spacing"],"B. Best verified vessel overlay","viridis",[0,3])
            fig.colorbar(im,ax=axes[1],ticks=[0,1,2,3],label="0 neither; 1 first; 2 second; 3 both")
            detail=f"Panel B maps {best['scan_b']} onto {best['scan_a']} using their verified rigid transform; first-scan native origin/axes. "
        else:
            axes[1].text(.5,.5,"No verified vessel-supported match",ha="center",va="center",transform=axes[1].transAxes)
            axes[1].set(title="B. Vessel overlay unavailable");detail="No verified overlay is available. "
        registry.save(fig,2,f"{animal} {eye} registration diagnostics",eye_ids,
            "A: teal verified and gray withheld pairs, matched-feature RMS residual in µm versus structural correlation; only pairs with an estimated transform are plotted. Text counts all tested pairs. B: viridis vessel overlay, color codes 0=neither footprint, 1=first only, 2=second only, 3=both; white=outside overlap. "+detail,
            "Transforms are rigid in physical units and require independent vessel branches, structural correlation and sufficient overlap. No thickness values enter registration. Residuals are internal correspondence fit errors, not independently established registration accuracy. No error bars.",
            ["registration/matches.json"])
        for start in range(0,len(eye_ids),4):
            subset=eye_ids[start:start+4];fig,axes=plt.subplots(1,len(subset),figsize=(5*len(subset),5),squeeze=False)
            for j,s in enumerate(subset):
                d=npz(out/"maps"/(s+"_analysis.npz"));ax=axes[0,j]
                native(ax,d["enface"],d["spacing"],f"{chr(65+j)}. {s}\n{loc[s]['method']}","gray")
                center=loc[s].get("center_um")
                if center and loc[s]["resolved"]:
                    ax.scatter(*center,c="red",marker="+");ax.add_patch(plt.Circle(center,loc[s]["uncertainty_um"],fill=False,color="orange"))
                    ax.update_datalim(np.array([center]));ax.autoscale_view()
                else:ax.text(.03,.03,"ONH unresolved",transform=ax.transAxes,color="orange")
            registry.save(fig,2,f"{animal} {eye} localization diagnostics {start//4+1}",subset,
                "Panels A onward follow acquisition order. Grayscale is structural en-face reflectance in saved arbitrary units, individually contrast-scaled; native origin is pixel (0,0). Red + is ONH center; orange circle is bootstrap/path uncertainty in µm. Unresolved centers are not plotted.",
                "Visible-edge fitting precedes registration transfer, followed by vessel convergence. Registration uses structural features near vessels and independent vessel branch checks; it never uses thickness similarity. Residuals and branch agreement are in registration tables. No error bars other than the stated circle.",
                ["registration/localizations.json","registration/matches.json"])
        for s in eye_ids:
            d=npz(out/"maps"/(s+"_analysis.npz"))
            if not d["cnv_candidate"].any():continue
            y,x=np.argwhere(d["cnv_candidate"])[len(np.argwhere(d["cnv_candidate"]))//2]
            fig,axes=plt.subplots(1,2,figsize=(11,5))
            native(axes[0],d["enface"],d["spacing"],"A. Automatic lesion proposals","gray")
            overlay=np.where(d["cnv_candidate"],1.,np.nan)
            native(axes[0],overlay,d["spacing"],"A. Cyan = automatic lesion proposals","cool",[0,1])
            axes[0].axhline(y*d["spacing"][0],color="yellow",ls="--")
            image_path=next(Path(fp["path"]).parent/"images.npy" for fp in infos[s]["input_fingerprints"] if Path(fp["path"]).name=="prepared.json")
            image=np.load(image_path,mmap_mode="r")[y]
            axes[1].imshow(image,cmap="gray",origin="upper",aspect="auto",
                extent=[0,image.shape[1]*d["spacing"][1],image.shape[0]*1.12,0])
            axes[1].set(title=f"B. Native B-scan {y} (zero-based)",xlabel="Image x (µm)",ylabel="Canonical cropped depth (µm)")
            registry.save(fig,2,s+" linked lesion candidates",[s],
                f"A: gray structural en-face, cyan automatic candidate footprints, yellow dashed line links to B-scan {y} (zero-based). B: saved canonical structural B-scan; vitreous at top, depth relative to export crop, 1.12 µm/pixel. Grayscale contrast is arbitrary reflectance, not thickness.",
                "Candidates are localized full-retina deviations or outer-composite deviations. They are exploratory proposals, not confirmed CNV or human annotations. Every connected proposal's B-scan span and link location is recorded in lesion_components.csv. No error bars.",
                ["maps/"+s+"_analysis.npz","tables/lesion_components.csv"])
    # Family 3: per-eye acquisition coverage and independent overlapping exclusions.
    for (animal,eye),eye_ids in sorted(groups.items()):
        for start in range(0,len(eye_ids),4):
            subset=eye_ids[start:start+4];fig,axes=plt.subplots(2,len(subset),figsize=(5*len(subset),8),squeeze=False)
            for j,s in enumerate(subset):
                d=npz(out/"maps"/(s+"_analysis.npz"))
                im=native(axes[0,j],d["eligible_A"].astype(float)+d["eligible_B"],d["spacing"],f"{chr(65+j)}. {s}","viridis",[0,2])
                fig.colorbar(im,ax=axes[0,j],label="0 excluded; 1 A only; 2 A+B",ticks=[0,1,2])
                n=sum(((d["exclusion_reasons"]&bit)>0).astype(int) for bit in (1,2,4,8,16,32,64,1024))
                im=native(axes[1,j],n,d["spacing"],f"{chr(65+len(subset)+j)}. Overlapping reasons","magma",[0,8])
                fig.colorbar(im,ax=axes[1,j],label="Exclusion reasons (count)")
            registry.save(fig,3,f"{animal} {eye} coverage and exclusions {start//4+1}",subset,
                "Panels run left-to-right across each row. Top: native inclusion, viridis 0=excluded, 1=A only, 2=A+B. Bottom: magma shows the number of overlapping spatial exclusion reasons (0–8). Axes in µm from native pixel (0,0); y increases down. These panels preserve native unobserved/excluded locations.",
                "Masks precede date aggregation. Bottom counts human exclusions, shadows, saved CNV, automatic CNV, CNV buffer, vessels, ONH and transferred CNV separately. Full-retina unavailability and B screening are stored as additional bits, not included in the bottom count. No uncertainty bars; missing annotations are separately flagged.",
                ["maps/"+s+"_analysis.npz" for s in subset]+["tables/exclusion_coverage.csv"])
    # Family 4: per-eye mosaics; one figure per measurement/version, always all eight.
    for (animal,eye),eye_ids in sorted(groups.items()):
        df=frame(out/"tables"/(animal+"_"+eye+"_cells.csv"))
        for name,top,bottom in LAYERS:
            for version in ("A","B"):
                selected=df[(df.kind=="cartesian")&(df.layer==name)&(df.version==version)] if not df.empty else df
                fig,axes=plt.subplots(1,2,figsize=(11,5))
                im=cellmap(axes[0],selected,cfg,title=f"A. {name}: {top}→{bottom}")
                if im is not None:fig.colorbar(im,ax=axes[0],label="Thickness (µm)")
                im=cellmap(axes[1],selected,cfg,"dates",title="B. Contributing dates")
                if im is not None:fig.colorbar(im,ax=axes[1],label="Eye-dates (count)")
                registry.save(fig,4,f"{animal} {eye} {name} version {version}",eye_ids,
                    "A: viridis thickness in µm with labeled color bar. B: viridis contributing eye-date count. Axes are ONH-centered physical x/y in µm; red + marks origin; y increases down.",
                    f"Within each {cfg['grid_um']:g} µm cell, eligible native pixels are averaged per acquisition, then acquisitions within dates, then dates equally. White cells have no eligible localized observation; no interpolation or gap filling. Disconnected registration components can contribute to an ONH atlas cell without being called repeated tissue. Dates and acquisition counts are cell-specific; no error bars.",
                    ["tables/"+animal+"_"+eye+"_cells.csv","registration/localizations.json"],version)
    # Family 5: equal-animal cohort and polar estimates, counts and uncertainty.
    cohort=frame(out/"tables/cohort_cells.csv")
    for name,top,bottom in LAYERS:
        for version in ("A","B"):
            selected=cohort[(cohort.layer==name)&(cohort.version==version)] if not cohort.empty else cohort
            cart=selected[selected.kind=="cartesian"] if not selected.empty else selected
            polar=selected[selected.kind=="polar"] if not selected.empty else selected
            fig,axes=plt.subplots(1,3,figsize=(15,5))
            for ax,val,title,label in [(axes[0],"value_um",f"A. {top}→{bottom}","Thickness (µm)"),
                                     (axes[1],"animals","B. Contributing animals","Animals (count)"),
                                     (axes[2],"animal_sd_um","C. Between-animal SD","SD (µm)")]:
                im=cellmap(ax,cart,cfg,val,title)
                if im is not None:fig.colorbar(im,ax=ax,label=label)
            registry.save(fig,5,f"Cohort {name} version {version}",ids,
                "A: viridis equal-animal mean thickness (µm). B: contributing animal count. C: sample SD of contributing animal means (µm), undefined/white for fewer than two animals. Each panel has its own labeled color-bar scale. ONH-centered axes in µm, y down, red + at origin.",
                "Hierarchy: acquisitions equally within dates, dates equally within eyes, eyes equally within animals, animals equally. White cells lack eligible localized data. SD expresses animal dispersion, not measurement accuracy; SEM is separately saved. Polar 250 µm radial/30° sector estimates retain the same hierarchy in the source table. No thickness interpolation.",
                ["tables/cohort_cells.csv","tables/animal_cells.csv"],version)
    # Family 6: tissue variation only from actual verified matches.
    repeats=frame(out/"tables/repeated_tissue.csv")
    for (animal,eye),eye_ids in sorted(groups.items()):
        sampled=frame(out/"tables"/(animal+"_"+eye+"_repeated_cells.csv"))
        components=sorted(sampled.component.unique()) if not sampled.empty else ["unresolved"]
        for component in components:
            for interval in ("same_session","across_date"):
                fig,axes=plt.subplots(1,3,figsize=(15,5))
                selected=sampled[(sampled.component==component)&(sampled.interval==interval)&(sampled.layer=="Full retina")&(sampled.version=="A")] if not sampled.empty else sampled
                # Component origin is the native origin of the reference scan; NOT ONH.
                for ax,val,title,label in [(axes[0],"acquisitions","A. Repeated tissue","Acquisitions (count)"),
                                         (axes[1],"sd_um","B. Full-retina variation","SD (µm)"),
                                         (axes[2],"range_um","C. Full-retina variation","Range (µm)")]:
                    if not selected.empty:
                        selected=selected.groupby(["cell_0","cell_1"],as_index=False).agg({"acquisitions":"max","sd_um":"mean","range_um":"mean"})
                    im=cellmap(ax,selected,cfg,val,title)
                    for artist in ax.collections:artist.remove()
                    ax.set(xlabel="Registered component x (µm)",ylabel="Registered component y (µm; down)")
                    if im is not None:fig.colorbar(im,ax=ax,label=label)
                registry.save(fig,6,f"{animal} {eye} repeated tissue {component} {interval}",eye_ids,
                    "A: maximum contributing acquisition count per sampled location. B/C: full-retina sample SD/range in µm. For same-session panels, SD/range are averaged over dates with repeats at that location. Viridis scales are separately labeled. Origin is the native top-left of the named registration reference, not ONH; x right, y down, µm.",
                    f"Only consistent vessel-connected components establish tissue. Native observations are sampled by nearest pixel on a {cfg['grid_um']:g} µm physical lattice; white locations have fewer than two eligible observations/dates. Same-session variation compares acquisitions within dates; across-date variation compares equally averaged date means. No interpolation; all layers and both versions are in repeated-cell and pairwise tables. Pairwise signed differences and exact eligible native overlap are stored separately. SD/range describe variation, not localization accuracy.",
                    ["tables/"+animal+"_"+eye+"_repeated_cells.csv","tables/repeated_tissue.csv"],"A")
    # Family 7.
    for name,_,_ in LAYERS:
        fig,axes=plt.subplots(1,2,figsize=(11,5))
        df=cohort[(cohort.layer==name)&(cohort.kind=="polar")] if not cohort.empty else cohort
        if not df.empty:
            joined=df[df.version=="A"].merge(df[df.version=="B"],on=["cell_0","cell_1"],suffixes=("_A","_B"))
            axes[0].scatter(joined.value_um_A,joined.value_um_B,s=12,color="teal")
            if len(joined):
                limits=[min(joined.value_um_A.min(),joined.value_um_B.min()),max(joined.value_um_A.max(),joined.value_um_B.max())]
                axes[0].plot(limits,limits,color="gray",ls="--")
            axes[1].hist(joined.value_um_B-joined.value_um_A,bins=25,color="teal")
        axes[0].set(title="A. Matched polar bins",xlabel="A thickness (µm)",ylabel="B thickness (µm)")
        axes[1].set(title="B. B−A differences",xlabel="Thickness difference (µm)",ylabel="Polar bins (count)")
        registry.save(fig,7,name+" A versus B",ids,
            "A: teal points are matched radial-sector cohort bins, A on x and B on y (µm); dashed gray line is equality. B: histogram of B−A thickness (µm), bin count on y. No spatial axes or anatomical origin.",
            "Only polar bins present in both versions appear. Each version recomputes the full equal-animal hierarchy over its own eligible observations, so contributor composition may differ. Empty panels mean no common localized bins. No error bars; these are exploratory inclusion-policy sensitivity comparisons.",
            ["tables/cohort_cells.csv"],"A/B",False)
    # Family 8.
    val=frame(out/"tables/hidden_onh_validation.csv");sensitivity=frame(out/"tables/sensitivity.csv")
    fig,axes=plt.subplots(1,2,figsize=(12,5))
    if not val.empty:
        ok=val[val.resolved.astype(bool)]
        axes[0].scatter(np.arange(len(ok)),ok.error_um,color="teal",s=15)
        axes[0].text(.03,.97,f"Resolved {len(ok)}/{len(val)} crops",transform=axes[0].transAxes,va="top")
    axes[0].set(title="A. Hidden-ONH crop self-consistency",xlabel="Resolved crop index",ylabel="Center error (µm)")
    if not sensitivity.empty:
        for policy,g in sensitivity.groupby("policy"):
            axes[1].scatter(g.parameter,g.eligible_fraction,label=policy,s=12)
        axes[1].legend(fontsize=7)
    axes[1].set(title="B. Exploratory mask sensitivity",xlabel="Policy multiplier or sigma threshold",ylabel="Eligible native fraction (0–1)")
    registry.save(fig,8,"Validation and exclusion sensitivity",ids,
        "A: teal points show Euclidean center difference (µm) for resolved artificially cropped vessel-convergence estimates; x is ordered crop index. Resolution fraction includes failed crops. B: colored points show eligible native-pixel fraction under CNV clearance multipliers or B sigma thresholds, with legend. No anatomical axes; no error bars.",
        "Real crop references are full-view visible-edge fits, not independent human center truth; errors measure self-consistency. Failed crops remain in the table with no invented center. Synthetic known-geometry validation is separately saved under qc. Sensitivity points are scan-level; uncertainty and preliminary measurement availability are reported on separate axes.",
        ["tables/hidden_onh_validation.csv","tables/sensitivity.csv","qc/analysis_axes.json"],"A/B",False)
    return registry.finish()


def audit_figures(out):
    out=Path(out);m=read(out/"manifest.json");records=m["figures"]
    numbers=[r["number"] for r in records]
    if numbers!=list(range(1,len(records)+1)):raise ValueError("Nonsequential figure registry")
    captions=(out/"fig/FIGURE_CAPTIONS.md").read_text(encoding="utf-8")
    pngs={p.relative_to(out).as_posix() for p in (out/"fig").glob("*.png")}
    if pngs!={r["file"] for r in records}:raise ValueError("Unregistered or missing figure")
    for r in records:
        if captions.count("## Figure "+f"{r['number']:03d}"+" —")!=1 or Path(r["file"]).name not in captions:
            raise ValueError("Missing or duplicate caption")
        if not r["data"] or any(not (out/p).exists() for p in r["data"]):raise ValueError("Figure data mapping missing")
    stray=[str(p) for p in out.rglob("fig_*.png") if p.parent!=out/"fig"]
    if stray:raise ValueError("Figures outside single fig folder: "+str(stray))
    write(out/"qc/figure_audit.json",dict(passed=True,figures=len(records),sequential=True,
        captions_match=True,data_links_exist=True,all_figures_in_single_folder=True))
