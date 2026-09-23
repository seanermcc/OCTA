"""Resumable read-only analysis of completed octa-thick batch exports."""
from pathlib import Path
from itertools import combinations
import json
import os
import time
import numpy as np
import pandas as pd
from . import DEFAULTS,VERSION,LAYERS,CAVEAT
from .io import read,write,save,npz,sha,digest,fingerprint,table,Stage,analysis_inputs,unique_scans,source_paths,load_scan
from .geometry import fit_onh,branches,convergence,features,register,apply,xy_grid,sample_native,lesion_buffer
from .masks import candidates,exclusions,REASONS
from .aggregate import acquisition_rows,balanced,repeat_pair,repeated_component

ROOT=Path(__file__).resolve().parents[2]
DEFAULT_OUT=ROOT/"outputs/octa-seg/octa-seg_v1/control_map_v1"
DEFAULT_BATCH=ROOT/"outputs/octa-seg_v1_batch"


def initialize(out=DEFAULT_OUT,batch=DEFAULT_BATCH):
    out=Path(out); batch=Path(batch)
    for folder in ("fig","tables","maps","registration","qc","logs"):
        (out/folder).mkdir(parents=True,exist_ok=True)
    if not (out/"config.json").exists(): write(out/"config.json",DEFAULTS)
    if not (out/"manifest.json").exists():
        write(out/"manifest.json",dict(version=VERSION,status="awaiting_verified_batch",batch=str(batch),figures=[]))
    if not (out/"fig/FIGURE_CAPTIONS.md").exists():
        (out/"fig/FIGURE_CAPTIONS.md").write_text("# Figure captions\n\nNo cohort figures generated before batch verification.\n",encoding="utf-8")
    write_readme(out,batch)


def validate_config(cfg):
    if cfg["schema"]!=VERSION: raise ValueError("Unsupported atlas configuration")
    for key in ("field_um","grid_um","neighborhood_diameter_um","local_sigma_floor_um","radial_band_um","angular_sector_deg"):
        if not np.isfinite(cfg[key]) or cfg[key]<=0: raise ValueError("Invalid "+key)
    if not np.isclose(360/cfg["angular_sector_deg"],round(360/cfg["angular_sector_deg"])):
        raise ValueError("Angular sectors must divide 360 degrees")
    if not 0<cfg["minimum_neighborhood_fraction"]<=1: raise ValueError("Invalid local coverage fraction")
    if cfg["bootstrap_samples"]<20: raise ValueError("At least 20 bootstrap replicates required")
    if not isinstance(cfg["scan_workers"],int) or not 1<=cfg["scan_workers"]<=8:
        raise ValueError("scan_workers must be an integer from 1 to 8")


def prepare_one(batch,out,row,cfg,code_hash):
    sid=row["scan_id"]; paths=source_paths(batch,row)
    sig=digest([code_hash,cfg,[fingerprint(p) for p in paths]])
    stage=Stage(out,"prepare_"+sid,sig)
    dest=out/"maps"/(sid+"_prepared.npz"); info_path=out/"maps"/(sid+"_source.json")
    if stage.valid(): return read(info_path)
    data,info=load_scan(batch,row,cfg)
    print(f"Input checks passed; computing local screens: {sid}",flush=True)
    candidate,diagnostics=candidates(data,cfg)
    data.update(diagnostics);data["cnv_candidate"]=candidate
    buffered,_=lesion_buffer(data["cnv_human"]|candidate,data["spacing"],cfg["cnv_buffer_diameters"])
    data["registration_blocked"]=data["human_excluded"]|buffered|data["onh"]
    feat=features(data["enface"],data["vessel"],data["registration_blocked"],data["spacing"])
    data.update({"feature_"+k:v for k,v in feat.items()})
    branch,_=branches(data["vessel"]&~data["registration_blocked"],data["spacing"],cfg)
    info["branches"]=branch;info["visible_onh"]=fit_onh(data["onh"],data["onh_edge"],data["spacing"],cfg)
    info["input_fingerprints"]=[fingerprint(p) for p in paths]
    save(dest,**data);write(info_path,info);stage.finish([dest,info_path])
    return info


def registration_group(out,ids,infos,cfg,code_hash):
    key=infos[ids[0]]["animal"]+"_"+infos[ids[0]]["eye"]
    paths=[out/"maps"/(sid+"_prepared.npz") for sid in ids]
    stage=Stage(out,"registration_"+key,digest([code_hash,cfg,[fingerprint(p) for p in paths]]))
    dest=out/"registration"/(key+"_matches.json")
    if stage.valid(): return read(dest)
    # At most one eye's compact en-face data, not full structural volumes.
    needed={"enface","vessel","spacing","registration_blocked","feature_points","feature_descriptors","feature_branches"}
    arrays={}
    for sid,p in zip(ids,paths):
        with np.load(p,allow_pickle=False) as z:arrays[sid]={k:z[k] for k in needed}
    matches=[]
    for a,b in combinations(ids,2):
        fa={k:arrays[a]["feature_"+k] for k in ("points","descriptors","branches")}
        fb={k:arrays[b]["feature_"+k] for k in ("points","descriptors","branches")}
        match=register(arrays[a],arrays[b],fa,fb,cfg)
        matches.append(dict(scan_a=a,scan_b=b,**match))
    write(dest,matches);stage.finish([dest]);return matches


def localize(ids,infos,matches,cfg):
    # Build a minimum-error forest; verify all other edges against its transforms.
    components={s:{s} for s in ids}; adjacency={s:[] for s in ids}
    edges=sorted([m for m in matches if m["verified"]],key=lambda m:(m["residual_um"],m["scan_a"],m["scan_b"]))
    for m in edges:
        a,b=m["scan_a"],m["scan_b"]
        if components[a] is components[b]: continue
        merged=components[a]|components[b]
        for sid in merged: components[sid]=merged
        matrix=np.array(m["matrix"])
        adjacency[a].append((b,matrix,m["residual_um"]))
        adjacency[b].append((a,np.linalg.inv(matrix),m["residual_um"]))
    result={};seen=set()
    for sid in ids:
        if sid in seen:continue
        members=sorted(components[sid]);seen.update(members); root=members[0]
        transforms={root:np.eye(3)};errors={root:0.}; todo=[root]
        while todo:
            a=todo.pop()
            for b,ab,error in adjacency[a]:
                if b in transforms:continue
                transforms[b]=transforms[a]@np.linalg.inv(ab)
                errors[b]=errors[a]+error;todo.append(b)
        inconsistent=False
        for m in edges:
            a,b=m["scan_a"],m["scan_b"]
            if a not in members or b not in members:continue
            corners=np.array([[0,0],[0,1000],[1000,0],[1000,1000]])
            difference=apply(corners,transforms[a])-apply(apply(corners,np.array(m["matrix"])),transforms[b])
            m["cycle_error_um"]=float(np.max(np.linalg.norm(difference,axis=1)))
            if m["cycle_error_um"]>3*cfg["registration_residual_um"]: inconsistent=True
        visible=[s for s in members if infos[s]["visible_onh"].get("resolved")]
        anchors=visible
        method="visible edge"
        if not anchors:
            for s in members: infos[s]["convergence"]=convergence(infos[s]["branches"],cfg)
            anchors=[s for s in members if infos[s]["convergence"].get("resolved")]
            method="vessel convergence"
        source=min(anchors,key=lambda s:infos[s]["visible_onh" if visible else "convergence"]["uncertainty_um"]+errors[s]) if anchors else None
        chosen=infos[source]["visible_onh" if visible else "convergence"] if source else {}
        center=apply(np.array(chosen["center_um"]),transforms[source]) if source else None
        if source:
            for other in anchors:
                loc=infos[other]["visible_onh" if visible else "convergence"]
                discrepancy=np.linalg.norm(apply(np.array(loc["center_um"]),transforms[other])-center)
                tolerance=max(cfg["onh_max_uncertainty_um"],chosen["uncertainty_um"]+loc["uncertainty_um"]+errors[other]+errors[source])
                if discrepancy>tolerance: inconsistent=True
        # Same-eye disc diameter may be transferred even to a separate component;
        # center and tissue registration never transfer across disconnected components.
        same_eye_diameters=[infos[s]["visible_onh"]["diameter_um"] for s in ids if infos[s]["visible_onh"].get("resolved")]
        diameter=float(np.median(same_eye_diameters)) if same_eye_diameters else None
        for s in members:
            uncertainty=chosen.get("uncertainty_um",0)+errors[s]+(errors[source] if source else 0)
            resolved=bool(source and not inconsistent and uncertainty<=cfg["onh_max_uncertainty_um"])
            native_center=apply(center,np.linalg.inv(transforms[s])).tolist() if center is not None else None
            result[s]=dict(resolved=resolved,center_um=native_center,component_center_um=center.tolist() if center is not None else None,
                component=root,matrix_to_component=transforms[s].tolist(),path_error_um=errors[s],
                uncertainty_um=uncertainty if source else None,diameter_um=chosen.get("diameter_um") or diameter,
                diameter_source="visible same-eye estimate" if diameter else "unresolved",
                method=(method if s==source else "registration transfer of "+method) if source else "unresolved",
                anchor_scan=source,component_consistent=not inconsistent,
                reason="conflicting localization or registration loop" if inconsistent else "adequate center" if resolved else "insufficient localization evidence")
    return result


def transfer_lesions(data,infos,matches,cfg):
    """Date-specific propagation only through directly verified vessel matches.

    Union in a padded physical reference field recovers connected clipped extents;
    original human and automatic masks retain separate provenance.
    """
    records=[]
    for m in matches:
        a,b=m["scan_a"],m["scan_b"]
        if not m["verified"] or infos[a]["session_date"]!=infos[b]["session_date"]: continue
        for source,target,matrix in ((a,b,np.asarray(m["matrix"])),(b,a,np.linalg.inv(np.asarray(m["matrix"])))):
            s=data[source];t=data[target]
            source_mask=s["cnv_human"]|s["cnv_candidate"]
            if not source_mask.any():continue
            spacing=np.minimum(s["spacing"],t["spacing"])
            corners=apply(xy_grid(s["enface"].shape,s["spacing"])[np.ix_([0,-1],[0,-1])].reshape(-1,2),matrix)
            native_corners=xy_grid(t["enface"].shape,t["spacing"])[np.ix_([0,-1],[0,-1])].reshape(-1,2)
            both=np.r_[corners,native_corners]; origin=both.min(axis=0)-2*spacing[::-1]
            shape=np.ceil((both.max(axis=0)-origin)/spacing[::-1]).astype(int)[::-1]+3
            world=xy_grid(shape,spacing)+origin
            sm,sv=sample_native(source_mask,apply(world,np.linalg.inv(matrix)),s["spacing"])
            tm,tv=sample_native(t["cnv_human"]|t["cnv_candidate"],world,t["spacing"])
            union=(sm==1)|(tm==1)
            buffer,components=lesion_buffer(union,spacing,cfg["cnv_buffer_diameters"])
            # Extent is recovered only when the union lesion avoids the boundary
            # of the actually observed combined field, not merely the padded box.
            from scipy import ndimage as ndi
            boundary=(sv|tv)&~ndi.binary_erosion(sv|tv)
            incomplete=bool((union&boundary).any())
            labels,n=ndi.label(union);recovered=np.zeros_like(union)
            for k in range(1,n+1):
                component=labels==k
                if not (component&boundary).any():recovered|=component
            target_world=xy_grid(t["enface"].shape,t["spacing"])-origin
            footprint,_=sample_native(union,target_world,spacing)
            buf,_=sample_native(buffer,target_world,spacing)
            recovered_native,_=sample_native(recovered,target_world,spacing)
            t.setdefault("cnv_transferred",np.zeros(t["enface"].shape,bool))[:]|=footprint==1
            t.setdefault("cnv_transferred_buffer",np.zeros(t["enface"].shape,bool))[:]|=buf==1
            t.setdefault("cnv_extent_recovered",np.zeros(t["enface"].shape,bool))[:]|=recovered_native==1
            records.append(dict(source=source,target=target,date=infos[source]["session_date"],
                registration_error_um=m["residual_um"],extent_still_incomplete=incomplete,
                recovered_max_feret_um=max((r["diameter_um"] for r in components),default=0.)))
    return records


def run(out=DEFAULT_OUT,batch=DEFAULT_BATCH,skip_batch_audit=False):
    out=Path(out).resolve();batch=Path(batch).resolve();initialize(out,batch)
    manifest,batch_audit=analysis_inputs(batch,skip_batch_audit)
    cfg=read(out/"config.json");validate_config(cfg)
    rows,duplicates=unique_scans(manifest["scans"])
    code_hash=digest({p.name:sha(p) for p in Path(__file__).parent.glob("*.py")})
    started=time.time()
    write(out/"qc/batch_audit_policy.json",batch_audit)
    write(out/"logs/run_status.json",dict(status="running",stage="preparation",pid=os.getpid(),
        started=started,prepared=0,total=len(rows),code_hash=code_hash,batch_audit=batch_audit))
    running_manifest=read(out/"manifest.json")
    running_manifest.update(status="analysis_running_preliminary",batch_audit=batch_audit)
    write(out/"manifest.json",running_manifest);write_readme(out,batch)
    table(out/"tables/duplicate_inventory.csv",duplicates)
    if (batch/"duplicate_files.json").exists():write(out/"qc/upstream_duplicate_files.json",read(batch/"duplicate_files.json"))
    table(out/"tables/unavailable_acquisitions.csv",manifest.get("unavailable",[]))
    from concurrent.futures import ThreadPoolExecutor,as_completed
    infos={}
    with ThreadPoolExecutor(max_workers=cfg["scan_workers"]) as pool:
        pending={pool.submit(prepare_one,batch,out,row,cfg,code_hash):row["scan_id"] for row in rows}
        for future in as_completed(pending):
            info=future.result();infos[info["scan_id"]]=info
            print(f"Prepared atlas input {len(infos)}/{len(rows)}: {info['scan_id']}",flush=True)
            write(out/"logs/run_status.json",dict(status="running",stage="preparation",pid=os.getpid(),
                started=started,prepared=len(infos),total=len(rows),last_scan=info["scan_id"],batch_audit=batch_audit))
    infos=dict(sorted(infos.items()))
    groups={}
    for sid,info in infos.items():groups.setdefault((info["animal"],info["eye"]),[]).append(sid)
    all_matches=[];all_loc={};all_local=[];all_eyes=[];all_repeat=[];all_exclusions=[];all_components=[];all_transfers=[]
    for (animal,eye),ids in sorted(groups.items()):
        print(f"Registering and summarizing {animal} {eye} ({len(ids)} acquisitions)",flush=True)
        write(out/"logs/run_status.json",dict(status="running",stage="registration_and_summaries",pid=os.getpid(),
            animal=animal,eye=eye,prepared=len(infos),total=len(rows),batch_audit=batch_audit))
        matches=registration_group(out,ids,infos,cfg,code_hash)
        loc=localize(ids,infos,matches,cfg);all_matches.extend(matches);all_loc.update(loc)
        for m in matches:
            if not loc[m["scan_a"]]["component_consistent"] or not loc[m["scan_b"]]["component_consistent"]:
                m["verified"]=False;m["reason"]="inconsistent registration/localization component; withheld"
        signature=digest([code_hash,cfg,matches,loc,[fingerprint(out/"maps"/(s+"_prepared.npz")) for s in ids]])
        stage=Stage(out,"summaries_"+animal+"_"+eye,signature)
        summary_path=out/"tables"/(animal+"_"+eye+"_summary.json")
        eye_path=out/"tables"/(animal+"_"+eye+"_cells.csv")
        if stage.valid():
            summary=read(summary_path)
        else:
            data={sid:npz(out/"maps"/(sid+"_prepared.npz")) for sid in ids}
            transfers=transfer_lesions(data,infos,matches,cfg);component_rows=[];exclusion_rows=[];local=[];eye_cells=[];artifacts=[]
            for sid in ids:
                mask,components,disc_known=exclusions(data[sid],loc[sid],cfg)
                data[sid].update(mask)
                cells,summary_local,coordinates=acquisition_rows(sid,data[sid],infos[sid],loc[sid],cfg)
                local.extend(summary_local)
                # Collapse repeats into date means per eye without retaining all
                # native-pixel records. CSVs preserve reproducible bin assignments.
                eye_cells.extend(cells)
                dest=out/"maps"/(sid+"_analysis.npz");save(dest,**data[sid],**coordinates);artifacts.append(dest)
                from scipy import ndimage as ndi
                native_lesion=data[sid]["cnv_human"]|data[sid]["cnv_candidate"]|data[sid].get("cnv_transferred",False)
                labels,_=ndi.label(native_lesion)
                for c in components:
                    recovered=data[sid].get("cnv_extent_recovered",np.zeros_like(native_lesion))
                    native_component=labels==c["component"]
                    c["extent_recovered_same_session"]=bool(c["truncated"] and np.all(recovered[native_component]))
                    c["extent_incomplete"]=c["truncated"] and not c["extent_recovered_same_session"]
                    component_rows.append(dict(scan_id=sid,**c))
                exclusion_rows.append(dict(scan_id=sid,animal=animal,eye=eye,date=infos[sid]["session_date"],
                    localized=loc[sid]["resolved"],onh_exclusion_resolved=disc_known,
                    cnv_reviewed=infos[sid]["annotation_reviewed"][0],vessels_reviewed=infos[sid]["annotation_reviewed"][1],
                    cnv_extent_incomplete=any(c["extent_incomplete"] for c in components),
                    annotation_absence_is_not_lesion_absence=True,
                    eligible_A_um2=float(mask["eligible_A"].sum()*np.prod(data[sid]["spacing"])),
                    eligible_B_um2=float(mask["eligible_B"].sum()*np.prod(data[sid]["spacing"])),
                    **{key+"_pixels":int(((mask["exclusion_reasons"]&bit)>0).sum()) for key,bit in REASONS.items()}))
            levels=balanced(eye_cells)
            levels["eye"].to_csv(eye_path,index=False)
            date_path=out/"tables"/(animal+"_"+eye+"_date_cells.csv");levels["date"].to_csv(date_path,index=False)
            artifacts.extend([eye_path,date_path]);repeat=[]
            # Explicit per-eye map artifacts contain observed cells and support
            # counts for all eight measurements; native maps remain separate.
            for version in ("A","B"):
                eye_df=levels["eye"]
                selected=eye_df[(eye_df.version==version)&(eye_df.kind=="cartesian")] if not eye_df.empty else eye_df
                dest=out/"maps"/(animal+"_"+eye+"_atlas_"+version+".npz")
                arrays={k:np.array(selected[k],dtype=str if k=="layer" else float) for k in
                        ("cell_0","cell_1","layer","value_um","dates","acquisitions","observed_area_sum_um2") if k in selected}
                save(dest,grid_um=np.array(cfg["grid_um"]),**arrays);artifacts.append(dest)
            del eye_cells,levels
            for m in matches:
                a,b=m["scan_a"],m["scan_b"]
                if not m["verified"]: continue
                rr,maps=repeat_pair(data[a],data[b],infos[a],infos[b],m,cfg);repeat.extend(rr)
                dest=out/"maps"/(a+"__"+b+"_repeat.npz");save(dest,**maps);artifacts.append(dest)
            safe={s:d for s,d in data.items() if loc[s]["component_consistent"]}
            repeated=repeated_component(safe,infos,loc,cfg)
            dest=out/"tables"/(animal+"_"+eye+"_repeated_cells.csv");repeated.to_csv(dest,index=False);artifacts.append(dest)
            summary=dict(local=local,repeat=repeat,exclusions=exclusion_rows,components=component_rows,transfers=transfers)
            write(summary_path,summary);artifacts.append(summary_path);stage.finish(artifacts)
        all_local.extend(summary["local"]);all_repeat.extend(summary["repeat"])
        all_exclusions.extend(summary["exclusions"]);all_components.extend(summary["components"]);all_transfers.extend(summary["transfers"])
        try:all_eyes.append(pd.read_csv(eye_path))
        except pd.errors.EmptyDataError:pass
    write(out/"registration/localizations.json",all_loc);write(out/"registration/matches.json",all_matches)
    table(out/"tables/local_summaries.csv",all_local);table(out/"tables/exclusion_coverage.csv",all_exclusions)
    table(out/"tables/lesion_components.csv",all_components);table(out/"tables/lesion_transfers.csv",all_transfers)
    table(out/"tables/repeated_tissue.csv",all_repeat)
    from .aggregate import KEYS
    if all_eyes:
        eyes=pd.concat(all_eyes,ignore_index=True)
        animals=eyes.groupby(KEYS+["animal"],as_index=False).agg(value_um=("value_um","mean"),eyes=("eye","nunique"),
            dates=("dates","sum"),acquisitions=("acquisitions","sum"),observed_area_sum_um2=("observed_area_sum_um2","sum"))
        cohort=animals.groupby(KEYS,as_index=False).agg(value_um=("value_um","mean"),animals=("animal","nunique"),
            eyes=("eyes","sum"),dates=("dates","sum"),acquisitions=("acquisitions","sum"),
            animal_sd_um=("value_um","std"),observed_area_sum_um2=("observed_area_sum_um2","sum"))
        cohort["animal_sem_um"]=cohort.animal_sd_um/np.sqrt(cohort.animals)
    else:animals=pd.DataFrame();cohort=pd.DataFrame()
    animals.to_csv(out/"tables/animal_cells.csv",index=False);cohort.to_csv(out/"tables/cohort_cells.csv",index=False)
    inventory=[{k:r.get(k) for k in ("scan_id","animal","eye","session_date","days_post_laser","source")} for r in rows]
    for r in inventory:r.update(all_loc[r["scan_id"]])
    table(out/"tables/inventory.csv",inventory)
    write(out/"qc/analysis_axes.json",dict(localization=dict(resolved=sum(l["resolved"] for l in all_loc.values()),total=len(rows)),
        registration=dict(verified=sum(m["verified"] for m in all_matches),tested=len(all_matches)),
        exclusion=dict(cnv_reviewed=sum(r["cnv_reviewed"] for r in all_exclusions),
                       onh_resolved=sum(r["onh_exclusion_resolved"] for r in all_exclusions)),
        thickness=dict(policy="exclude_unreliable_um; preliminary",table="tables/local_summaries.csv")))
    from .validation import validate_real
    validate_real(out,infos,all_loc,cfg)
    from .figures import generate,audit_figures
    figure_records=generate(out,infos,all_loc,cfg)
    # A long run must not publish a completion claim if reviewed inputs changed
    # while its stages were executing. Newly added region files also invalidate it.
    for sid,info in infos.items():
        current=[fingerprint(p) for p in source_paths(batch,info)]
        if current!=info["input_fingerprints"]:
            raise ValueError("Source changed during atlas run; resume against the updated exports: "+sid)
    result=dict(version=VERSION,status="analysis_complete_preliminary",config=fingerprint(out/"config.json"),
        batch_verification=batch_audit["verification"],batch_audit=batch_audit,batch_manifest=fingerprint(batch/"manifest.json"),
        code_hash=code_hash,measurements=LAYERS,orientation=cfg["orientation"],exclusion_reasons=REASONS,
        figures=figure_records,sources={s:i["input_fingerprints"] for s,i in infos.items()},
        limitations=[CAVEAT,"Automatic CNV/vessel candidates are unvalidated; missing annotation is unknown.",
                     "25 um Cartesian bins average observed eligible pixels; native masks and coordinates are preserved.",
                     "Repeated-cell variation samples a physical lattice by nearest native pixel; no interpolation.",
                     "Observed area sums across acquisitions are sampling exposure, not unique retinal area."])
    write(out/"manifest.json",result);audit_figures(out);write_readme(out,batch)
    write(out/"logs/run_status.json",dict(status="complete",completed=time.time(),batch_audit=batch_audit))
    return result


def write_readme(out,batch):
    source=Path(__file__).parent/"README.md"
    if source.exists():
        text=source.read_text(encoding="utf-8")
        status=read(out/"manifest.json")["status"]
        audit=read(out/"manifest.json").get("batch_audit",{}).get("status","not yet checked")
        (out/"README.md").write_text(f"# control_map_v1\n\nCurrent status: **{status}**.\n\nBatch audit: **{audit}**.\n\nBatch: `{batch}`.\n\n"+text,encoding="utf-8")
