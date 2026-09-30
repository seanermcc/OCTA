"""Read-only recovery of the interrupted atlas's prepared snapshot.

This deliberately produces a bounded preview, not a completed cohort release.
Run from the activated octa environment; all new artifacts stay beside this file.
"""
from pathlib import Path
import os
import sys
import json
import argparse
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))
if os.name == "nt" and os.environ.get("CONDA_PREFIX"):
    _dll = os.add_dll_directory(str(Path(os.environ["CONDA_PREFIX"]) / "Library/bin"))
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from control_map_v1.io import read, sha, write, table, npz, save
from control_map_v1.pipeline import localize, transfer_lesions
from control_map_v1.geometry import register
from control_map_v1.masks import exclusions
from control_map_v1.aggregate import acquisition_rows, balanced
from control_map_v1 import LAYERS

SOURCE = Path("F:/OCT_TreeShrew/octa/outputs/octa-seg/octa-seg_v1/control_map_v1")
OUT = Path(__file__).resolve().parent


def relocated(path):
    value = str(path).replace("\\", "/")
    for prefix in ("G:/OCT_TreeShrew/", "E:/OCT_TreeShrew/"):
        if value.startswith(prefix):
            return Path("F:/OCT_TreeShrew") / value[len(prefix):]
    return Path(path)


def inventory():
    cfg = read(SOURCE / "config.json")
    infos, rows, failures = {}, [], []
    for path in sorted((SOURCE / "maps").glob("*_source.json")):
        sid = path.name.removesuffix("_source.json")
        marker_path = SOURCE / "logs" / ("prepare_" + sid + ".json")
        try:
            marker = read(marker_path)
            expected_names = {path.name, sid + "_prepared.npz"}
            if {Path(f["path"]).name for f in marker["artifacts"]} != expected_names:
                raise ValueError("Unexpected marker artifacts")
            for fp in marker["artifacts"]:
                actual = SOURCE / "maps" / Path(fp["path"]).name
                if actual.stat().st_size != fp["bytes"] or sha(actual) != fp["sha256"]:
                    raise ValueError("Cached artifact checksum mismatch: " + str(actual))
            info = read(path)
            if info["scan_id"] != sid:
                raise ValueError("Scan identity mismatch")
            infos[sid] = info
            loc = localize([sid], {sid: info}, [], cfg)[sid]
            rows.append(dict(scan_id=sid, animal=info["animal"], eye=info["eye"],
                date=info["session_date"], visible_edge_resolved=info["visible_onh"].get("resolved", False),
                standalone_localized=loc["resolved"], method=loc["method"],
                reason=loc["reason"], cache_sha256_verified=True))
        except Exception as exc:
            failures.append(dict(scan_id=sid, error=str(exc)))
    table(OUT / "tables/recovered_inventory.csv", rows)
    write(OUT / "cache_audit.json", dict(source=str(SOURCE), verified=len(infos), failures=failures,
        scope="Saved preparation artifacts checked against their original SHA256 markers; historical snapshot, not current-label validation"))
    counts = Counter((x["animal"], x["eye"]) for x in infos.values())
    print(json.dumps(dict(verified=len(infos), groups={str(k):v for k,v in counts.items()},
        visible=sum(r["visible_edge_resolved"] for r in rows), standalone=sum(r["standalone_localized"] for r in rows), failures=failures)), flush=True)
    return cfg, infos, rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory-only", action="store_true")
    args = parser.parse_args()
    for folder in ("fig", "tables", "maps", "registration"):
        (OUT / folder).mkdir(parents=True, exist_ok=True)
    cfg, all_infos, inventory_rows = inventory()
    if args.inventory_only:
        return
    # Deliberately favor visible ONH anchors and one neighboring acquisition
    # from the same eye/date. This selection is not representative of the cohort.
    anchors = sorted(s for s,i in all_infos.items() if i["visible_onh"].get("resolved"))
    selected = set(anchors)
    for sid in anchors:
        i = all_infos[sid]
        neighbors = [s for s,j in all_infos.items() if s != sid and
            (j["animal"],j["eye"],j["session_date"]) == (i["animal"],i["eye"],i["session_date"])]
        if neighbors:
            selected.add(min(neighbors, key=lambda s:(abs(int(all_infos[s]["scan_no"])-int(i["scan_no"])),s)))
    infos = {s:all_infos[s] for s in sorted(selected)}
    write(OUT / "config.json", cfg)
    write(OUT / "selection.json", dict(scans=list(infos), rule="All three cached resolved visible-edge anchors plus nearest scan-number same-eye/date neighbor", snapshot=str(SOURCE)))
    input_checks = []
    for sid,info in infos.items():
        for fp in info["input_fingerprints"]:
            actual = relocated(fp["path"])
            matches = actual.is_file() and actual.stat().st_size == fp["bytes"] and sha(actual) == fp["sha256"]
            input_checks.append(dict(scan_id=sid, original_path=fp["path"], current_path=str(actual), unchanged=matches))
    table(OUT / "tables/current_input_comparison.csv", input_checks)
    data = {s:npz(SOURCE / "maps" / (s+"_prepared.npz")) for s in infos}
    for sid,d in data.items():
        if d["thickness"].shape != (8,*d["enface"].shape):
            raise ValueError("Invalid native thickness grid: " + sid)
        if np.isfinite(d["thickness"][:,d["shadow"].astype(bool)]).any():
            raise ValueError("Shadow NaNs lost: " + sid)
    groups = {}
    for sid,i in infos.items():
        groups.setdefault((i["animal"],i["eye"]), []).append(sid)
    matches, locations = [], {}
    from itertools import combinations
    for ids in groups.values():
        group_matches = []
        for a,b in combinations(ids,2):
            print("Registering",a,b,flush=True)
            fa = {k:data[a]["feature_"+k] for k in ("points","descriptors","branches")}
            fb = {k:data[b]["feature_"+k] for k in ("points","descriptors","branches")}
            group_matches.append(dict(scan_a=a,scan_b=b,**register(data[a],data[b],fa,fb,cfg)))
        loc = localize(ids,infos,group_matches,cfg)
        for m in group_matches:
            if not loc[m["scan_a"]]["component_consistent"] or not loc[m["scan_b"]]["component_consistent"]:
                m.update(verified=False,reason="Inconsistent localization component")
        transfer_lesions({s:data[s] for s in ids},infos,group_matches,cfg)
        locations.update(loc)
        matches.extend(group_matches)
    write(OUT / "registration/matches.json", matches)
    write(OUT / "registration/localizations.json", locations)
    cells, summaries = [], []
    for n,(sid,d) in enumerate(data.items(),1):
        write(OUT / "run_status.json", dict(status="running",stage="exclusions_and_maps",scan=sid,done=n-1,total=len(data)))
        print(f"A/B exclusion screens {n}/{len(data)}: {sid}",flush=True)
        masks, components, disc_known = exclusions(d,locations[sid],cfg)
        d.update(masks)
        c,s,coordinates = acquisition_rows(sid,d,infos[sid],locations[sid],cfg)
        cells.extend(c); summaries.extend(s)
        save(OUT / "maps" / (sid+"_preview.npz"), **d, **coordinates)
        write(OUT / "maps" / (sid+"_preview.json"), dict(localization=locations[sid],onh_exclusion_resolved=disc_known,lesion_components=components))
        fig,axs = plt.subplots(2,4,figsize=(15,8),layout="constrained")
        for k,ax in enumerate(axs.flat):
            values = np.where(d["eligible_A"],d["thickness"][k],np.nan)
            im=ax.imshow(values,cmap="viridis",extent=[0,1.46,1.46,0])
            ax.set_title(LAYERS[k][0]);ax.set_xlabel("Image x (mm)");ax.set_ylabel("Image y (mm)")
            fig.colorbar(im,ax=ax,label="µm",shrink=.75)
        fig.suptitle(f"{sid}\nExperimental thickness • A exclusions • blank = unavailable/excluded",fontsize=13)
        fig.savefig(OUT/"fig"/(f"{n:02d}_"+sid+"_layers.png"),dpi=130);plt.close(fig)
    table(OUT/"tables/local_summaries.csv",summaries)
    levels=balanced(cells)
    for name,df in levels.items():
        df.to_csv(OUT/"tables"/(name+"_cells.csv"),index=False)
    fig,axs=plt.subplots(len(data),3,figsize=(12,3.7*len(data)),layout="constrained")
    for row,(sid,d) in enumerate(data.items()):
        ax=axs[row,0];en=d["enface"]
        ax.imshow(en,cmap="gray",vmin=np.percentile(en,2),vmax=np.percentile(en,98),extent=[0,1460,1460,0])
        loc=locations[sid]
        if loc["resolved"]:
            x,y=loc["center_um"];ax.plot(x,y,"r+",markersize=12)
            if loc["diameter_um"]:
                ax.add_patch(plt.Circle((x,y),loc["diameter_um"]/2,fill=False,color="red",lw=1))
        ax.set_xlim(0,1460);ax.set_ylim(1460,0)
        ax.set_title(sid+"\nONH: "+loc["method"],fontsize=9)
        vals=d["thickness"][0];finite=vals[np.isfinite(vals)]
        lo,hi=np.percentile(finite,[2,98]) if finite.size else (0,1)
        for col,version in enumerate(("A","B"),1):
            valid=d["eligible_"+version]&np.isfinite(vals)
            im=axs[row,col].imshow(np.where(valid,vals,np.nan),cmap="viridis",vmin=lo,vmax=hi,extent=[0,1460,1460,0])
            axs[row,col].set_title(f"Full retina {version} · {valid.mean():.1%} of field measured")
            fig.colorbar(im,ax=axs[row,col],label="µm",shrink=.75)
        for ax in axs[row]:ax.set_xlabel("Image x (µm)");ax.set_ylabel("Image y (µm)")
    fig.suptitle("Recovered atlas pilot • six deliberately selected acquisitions\nA: tissue exclusions   B: A + local full-retina screen | preliminary snapshot",fontsize=15)
    fig.savefig(OUT/"fig/00_ONH_AND_AB_OVERVIEW.png",dpi=125);plt.close(fig)
    # Each eye is displayed separately. No representative cohort claim is made.
    for (animal,eye),ids in groups.items():
        df=levels["eye"]
        fig,axs=plt.subplots(2,4,figsize=(15,8),layout="constrained")
        for k,ax in enumerate(axs.flat):
            if not df.empty:
                q=df[(df.animal==animal)&(df.eye==eye)&(df.version=="A")&(df.kind=="cartesian")&(df.layer==LAYERS[k][0])]
            else:q=pd.DataFrame()
            if q.empty:
                ax.text(.5,.5,"No localized measurements",ha="center",transform=ax.transAxes)
            else:
                im=ax.scatter(q.cell_0*cfg["grid_um"],-q.cell_1*cfg["grid_um"],c=q.value_um,s=7,marker="s",cmap="viridis")
                fig.colorbar(im,ax=ax,label="µm",shrink=.75)
                ax.plot(0,0,"r+");ax.set_aspect("equal")
            ax.set_title(LAYERS[k][0]);ax.set_xlabel("ONH-relative image x (µm)");ax.set_ylabel("ONH-relative image up (µm)")
        fig.suptitle(f"{animal} {eye} • provisional ONH-centered A maps\nSelected two-acquisition pilot; unresolved scans withheld; anatomical axes unconfirmed",fontsize=13)
        fig.savefig(OUT/"fig"/(f"ATLAS_{animal}_{eye}.png"),dpi=130);plt.close(fig)
    status=dict(status="preview_complete", recovered_scans=len(all_infos), selected_scans=len(data),
        localized=sum(l["resolved"] for l in locations.values()), registration_pairs=len(matches),
        registration_passed=sum(m["verified"] for m in matches),
        changed_current_inputs=sum(not r["unchanged"] for r in input_checks),
        source_snapshot=str(SOURCE), full_cohort_complete=False)
    write(OUT/"run_status.json",status)
    images=sorted((OUT/"fig").glob("*.png"))
    intro=("<h1>Recovered control-map / ONH atlas preview</h1><p>72 checksum-verified prepared acquisitions recovered; "
        "six selected around three visible ONH anchors. Historical September 11 snapshot, processed September 15. "
        "Thickness and automatic exclusions are experimental; this is not a complete cohort or healthy-reference atlas. "
        "White areas retain unavailable/excluded measurements. A applies tissue exclusions; B additionally applies the original 500 µm local screen. "
        "Separate eye maps use provisional image axes and equal acquisition weighting within each date. Unresolved centers are withheld.</p>")
    gallery="<!doctype html><meta charset='utf-8'><title>ONH atlas preview</title><style>body{font:17px system-ui;margin:32px;background:#f3f5f7;color:#182335}p{max-width:1050px;line-height:1.6}img{width:100%;background:white}section{margin:30px 0}a{color:#145ca4}</style>"+intro
    gallery+="<p><a href='tables/recovered_inventory.csv'>Recovered inventory</a> · <a href='tables/local_summaries.csv'>Measurements</a> · <a href='run_status.json'>Run status</a></p>"
    for p in images:gallery+=f"<section><h2>{p.stem}</h2><img loading='lazy' src='fig/{p.name}'></section>"
    (OUT/"index.html").write_text(gallery,encoding="utf-8")
    (OUT/"README.md").write_text("# Recovered control-map / ONH atlas preview\n\nOpen [the image gallery](index.html).\n\n```json\n"+json.dumps(status,indent=2)+"\n```\n\nThis is a historical cached-input pilot, not the original full-cohort completion. All 72 recovered preparation artifacts matched their saved SHA256 checksums. The six-scan selection favors three visible ONH anchors and their nearest scan-number neighbors from the same eye/date. The registration and A/B screen settings are unchanged. Source annotations, segmentation and the external drive were not modified.\n\nCurrent upstream file comparisons are recorded in tables/current_input_comparison.csv. Changed inputs are not incorporated into this snapshot. Newer annotations are not validated by the cache audit. Full-cohort batch audit remains skipped under the original authorization. Provisional ONH coordinates and automatic masks require review. Unlocalized measurements remain in local summaries, but cannot contribute to ONH maps. Blank pixels remain missing.\n\nReproduce in activated octa: `python outputs/control_map_preview_20260915/build_preview.py`.\n",encoding="utf-8")
    print(json.dumps(status),flush=True)


if __name__=="__main__":
    main()
