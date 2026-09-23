"""Offline review gallery, unblended date-specific mosaics and measured report."""
from collections import Counter,defaultdict
from pathlib import Path
import csv
import json
import numpy as np
from PIL import Image,ImageDraw
from scipy import ndimage as ndi
from skimage.morphology import skeletonize
from .io import read,write
from .geometry import apply,footprint,sample_native,build_components

def gray(array):
    finite=np.isfinite(array)
    lo,hi=np.percentile(array[finite],[2,98]) if finite.any() else (0,1)
    result=np.nan_to_num(np.clip((array-lo)/max(hi-lo,1e-6),0,1),nan=0)*255
    return result.astype('uint8')

def rgba(mask,color):
    im=np.zeros((*mask.shape,4),dtype='uint8');im[mask]=color
    return Image.fromarray(im)

def scan_assets(out,infos):
    folder=out/'assets';folder.mkdir(exist_ok=True)
    for s,i in infos.items():
        p=out/'prepared'/(s+'.npz')
        if i['status']=='blocked' or not p.exists():continue
        with np.load(p,allow_pickle=False) as z:
            for channel in ('enface','octa'):Image.fromarray(gray(z[channel])).save(folder/(s+'_'+channel+'.png'))
            rgba(z['vessel'],[20,230,150,140]).save(folder/(s+'_vessel.png'))
            onh=z['selected_onh_mask'] if 'selected_onh_mask' in z else np.zeros_like(z['vessel'])
            rgba(onh,[255,175,35,140]).save(folder/(s+'_onh.png'))
            sk=skeletonize(z['vessel']);im=np.zeros((*sk.shape,4),dtype='uint8');im[sk]=[0,255,255,255]
            im[ndi.binary_dilation(z['junction_mask'],iterations=2)]=[255,40,90,255]
            Image.fromarray(im).save(folder/(s+'_centerline.png'))
            rgba(z['registration_blocked'],[240,50,220,130]).save(folder/(s+'_blocked.png'))

def review_queue(infos,pairs):
    queue={};eyes=defaultdict(list)
    for p in pairs:
        if p['status']=='automatic_proposal':eyes[infos[p['scan_a']]['animal']+'_'+infos[p['scan_a']]['eye']].append(p)
    def add(p,why):
        item=queue.setdefault(p['pair_id'],dict(pair_id=p['pair_id'],scan_a=p['scan_a'],scan_b=p['scan_b'],reasons=[],
            independent_landmarks=[],human_accuracy_um=None,annotation_status='pending independent human landmarks',
            suggested_annotation_regions=['overlap center','two separated peripheral overlap regions'],
            instruction='Mark at least three corresponding visible landmarks independently in native B-scan/A-line coordinates. Do not copy automatic junctions or transformed coordinates.'))
        item['reasons'].append(why)
    for eye,ps in eyes.items():
        ps.sort(key=lambda p:p['vessel_dice'])
        for idx,name in ((0,'lowest'),(len(ps)//2,'median'),(len(ps)-1,'highest')):add(ps[idx],eye+' '+name+' passing Dice')
    failures={}
    for p in pairs:
        if p['status']=='automatic_proposal':continue
        for reason in p.get('rejection_gates') or [p['status']+': '+p.get('reason','unknown')]:
            if reason not in failures:failures[reason]=p;add(p,'failure example: '+reason)
    return list(queue.values())

def mosaics(out,infos,components,transforms):
    folder=out/'mosaics';folder.mkdir(exist_ok=True);records=[]
    for c in components:
        if c['status']=='excluded_or_blocked':continue
        # Each component has its own unanchored coordinate system, never a cohort montage.
        for date in sorted({infos[s]['session_date'] for s in c['members']}):
            ids=[s for s in c['members'] if infos[s]['session_date']==date]
            pts=np.concatenate([np.asarray(transforms[s]['footprint_um']) for s in ids])
            low=pts.min(axis=0);high=pts.max(axis=0);step=4.
            w,h=np.ceil((high-low)/step).astype(int)+1
            if max(w,h)>3000:step=max(high-low)/2998;w,h=np.ceil((high-low)/step).astype(int)+1
            yy,xx=np.indices((h,w));world=np.stack([low[0]+xx*step,low[1]+yy*step],axis=-1)
            canvas=np.zeros((2,h,w),dtype='uint8');owner=np.full((h,w),-1,dtype='int16')
            for idx,s in enumerate(ids):
                native=apply(world,np.asarray(transforms[s]['matrix_from_component']))
                with np.load(out/'prepared'/(s+'.npz'),allow_pickle=False) as z:
                    for channel,key in enumerate(('enface','octa')):
                        val,valid=sample_native(gray(z[key]),native,z['spacing'])
                        finite,_=sample_native(np.isfinite(z[key]),native,z['spacing'])
                        valid &= finite==1
                        canvas[channel,valid]=val[valid].astype('uint8')
                    owner[valid]=idx
            name=c['component_id']+'__'+date
            for n,key in enumerate(('enface','octa')):
                image=Image.fromarray(canvas[n]).convert('RGB');draw=ImageDraw.Draw(image)
                for idx,s in enumerate(ids):
                    poly=(np.asarray(transforms[s]['footprint_um'])-low)/step
                    draw.line([tuple(p) for p in np.vstack([poly,poly[0]])],fill=(255,180,40),width=1)
                    draw.text(tuple(poly[0]+3),str(idx+1),fill=(255,180,40))
                if c['status']=='withheld_loop_inconsistent':draw.text((8,8),'DIAGNOSTIC ONLY - LOOP INCONSISTENT',fill=(255,70,70))
                image.save(folder/(name+'_'+key+'.png'))
            from .io import save
            save(folder/(name+'_coordinates.npz'),owner_scan_index=owner,origin_xy_um=low,step_um=np.array(step),scan_ids=np.array(ids))
            records.append(dict(component_id=c['component_id'],date=date,scan_ids=ids,status=c['status'],
                structural='mosaics/'+name+'_enface.png',octa='mosaics/'+name+'_octa.png',coordinate_map='mosaics/'+name+'_coordinates.npz',
                origin_xy_um=low.tolist(),step_um=step,composition='nearest native observations; last scan wins; outlines expose seams; no blending/interpolation'))
    write(out/'mosaics.json',records)

def breakdown(infos,pairs,key):
    groups=defaultdict(Counter)
    for p in pairs:groups[p.get(key,'unknown')][p['status']]+=1
    return {k:dict(v,total=sum(v.values())) for k,v in sorted(groups.items())}

def report(out,assets=True):
    out=Path(out);infos={i['scan_id']:i for i in read(out/'inventory.json')};pairs=read(out/'pairs.json')
    cfg=read(out/'config.json');components,transforms=build_components(infos,pairs,cfg)
    write(out/'components.json',components);write(out/'transforms.json',transforms);write(out/'pairs.json',pairs)
    queue=review_queue(infos,pairs);write(out/'human_review_queue.json',queue)
    if assets:scan_assets(out,infos);mosaics(out,infos,components,transforms)
    counts=Counter(p['status'] for p in pairs);connected={s for c in components if len(c['members'])>1 for s in c['members']}
    consistent={s for c in components if c['status']=='automatic_proposal' for s in c['members']}
    failures=Counter(g for p in pairs if p['status']=='rejected' for g in p.get('rejection_gates',[]))
    summary=dict(acquisitions=len(infos),animal_eye_groups=len({(i['animal'],i['eye']) for i in infos.values()}),candidate_pairs=len(pairs),
        scans_by_status=dict(Counter(i['status'] for i in infos.values())),mask_sources=dict(Counter(i.get('mask_source','unavailable') for i in infos.values())),
        selections=dict(Counter(i.get('selection','unavailable') for i in infos.values())),pair_status=dict(counts),connected_scans=len(connected),
        consistent_connected_scans=len(consistent),singletons=sum(len(c['members'])==1 for c in components),components=len(components),
        inconsistent_components=sum(c['status']=='withheld_loop_inconsistent' for c in components),onh_disagreement_components=sum(bool(c['onh_disagreements']) for c in components),
        rejection_gates=dict(failures),mask_source_performance=breakdown(infos,pairs,'mask_source_pair'),
        review_state_performance=breakdown(infos,pairs,'review_pair'),interval_performance=breakdown(infos,pairs,'interval'),
        pair_compute_seconds=sum(p.get('runtime_seconds',0) for p in pairs),preparation_compute_seconds=sum(i.get('preparation_seconds',0) for i in infos.values()),
        human_verified_registrations=0,review_queue_pairs=len(queue))
    write(out/'summary.json',summary)
    with (out/'pairs.csv').open('w',newline='',encoding='utf-8') as f:
        cols=['pair_id','scan_a','scan_b','status','interval','mask_source_pair','review_pair','matches','inliers','residual_um','overlap_fraction','vessel_dice','structural_correlation','branch_matches','branch_residual_um','cycle_error_um','runtime_seconds','reason']
        w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore');w.writeheader();w.writerows(pairs)
    state=read(out/'status.json') if (out/'status.json').exists() else {}
    lines=['# octa-reg_v1 — completed vessel-only experiment','',
        f"Run status: **{state.get('status','unknown')}**. {len(infos)} acquisitions, {summary['animal_eye_groups']} animal–eye groups, {len(pairs)} same-eye candidate pairs.",
        f"{counts['automatic_proposal']} pairs passed fixed internal gates; {counts['rejected']} rejected; {counts['blocked']} blocked; {counts['implementation_failure']} implementation failures.",
        f"{len(connected)} scans connect through passing edges; {len(consistent)} belong to consistent multi-scan components. {summary['singletons']} singletons remain independently positioned. {summary['inconsistent_components']} components are withheld for loop disagreement.",
        f"Elapsed wall time: {state.get('elapsed_seconds',0):.1f} s; summed pair compute {summary['pair_compute_seconds']:.1f} s; {state.get('pairs_resumed',0)} pairs resumed.",'',
        '## Measured strata','', '```json',json.dumps({k:summary[k] for k in ('mask_sources','selections','mask_source_performance','review_state_performance','interval_performance','rejection_gates')},indent=2),'```','',
        '## Review and interpretation','',
        'Open index.html or OPEN_GALLERY.cmd. Each component has its own coordinates. Select one date for imagery; across-date view shows footprints only. Pair view supplies alpha/flicker and selected vessel/ONH/centerline overlays. A rejected fit with a matrix is explicitly diagnostic. No-fit pairs appear side by side with no implied alignment. Click images to recover native B-scan/A-line indices.',
        f"The queue has {len(queue)} deduplicated pairs: highest, median and lowest passing Dice per eye, plus failure examples. independent_landmarks is deliberately empty, with three separated overlap regions suggested for later annotation. No human accuracy measurement exists.",
        'Automatic junctions, Dice, RANSAC residuals and loops are internal support only. The inherited baseline does not model bend sequences, crossings versus bifurcations, path lengths or full vascular topology. Lesion-related structural features can still influence descriptors despite vessel gating. CNV mode is off.',
        'ONH circle fits retain 150 degree arc, 25 um residual and 150 um uncertainty gates. Only assessable reviewed fits are anatomical evidence. Unreviewed fits and vessel convergence remain proposals. Straight branch fragments can share a trunk and are not necessarily independent; convergence cannot establish rotation or bridge components.',
        'Relative registration and ONH disagreement are separate: ONH disagreements prompt review without invalidating vessel-consistent components. Only registration cycle inconsistency withholds a connected component. The forest is not joint global optimization.',
        'The en-face cache sidecar documents fresh depth orientation; no en-face flips or resizing are applied. Physical calibration is approximate unless explicitly validated. Sources are read-only; source_integrity.json records post-run hashes of every consumed cache, sidecar and mask. Processed volume identities/fingerprints are inherited from verified cache sidecars, not rehashed as terabyte-scale raw inputs.',
        'Unavailable input is retained as blocked. Missing ONH is unknown. Empty selected vessels remain empty. Saved manual records include drafts and inherited automatic pixels; review states are shown independently. No CNV/lesion masks, layer measurements, model loaders or raw reconstruction are used.','',
        '## Prioritized next measurements','',
        '1. Annotate independent correspondences in the queued passing and rejected cases; inspect vessel mask omissions, motion stripes and cropped overlap before attributing matcher failures to anatomy.',
        ('2. Insufficient vessel-anchored inliers dominate rejections: compare corrected-mask support and curved-vessel/bend/topology descriptors on this frozen queue before changing matching gates.' if failures.get('insufficient_vessel_anchored_inliers',0)>=max([v for k,v in failures.items() if k!='insufficient_vessel_anchored_inliers'] or [0]) else '2. Inspect failed vessel/structure/junction gates in the queue to distinguish masks, motion artifacts and false feature matches; keep thresholds frozen for this release.'),
        '3. Evaluate global optimization only within independently validated connected components if loop inconsistency is substantial. It cannot resolve missing overlap or justify joining disconnected fields. ONH localization is a separate lower-priority experiment for components without reviewed disc evidence.','',
        '## Future CNV adapter contract','',
        'A separately versioned comparison may accept scan_id, source identity, native Boolean mask and [B-scan,A-line] grid, model/review provenance, revision/SHA256, and coverage/unknown status from a verified v9 or later export. The signature reserves cnv_snapshot=null. Import final policy-aware masks, never gallery thresholds/browser preferences. Missing masks mean unknown. CNV may be overlaid or evaluated as an alignment exclusion; do not match evolving lesions, propagate them across dates or alter this saved vessel-only baseline.','',
        '## Implementation notes','',
        'Pure control_map_v1.geometry functions are imported unchanged. The new forest wrapper uses actual image corners for cycle checking, keeps ONH disagreement separate, and stores explicit pixel→physical→component transforms/inverses. All matching constants and implementation hashes are frozen in snapshots/. Only pair artifacts resume; preparation, components and reports are rebuilt. Two compute threads and one atomic writer are used. No relaxed gates or alternative matcher is selected after seeing outcomes.']
    (out/'RUN_REPORT.md').write_text('\n\n'.join(lines),encoding='utf-8')
    (out/'START_HERE.md').write_text('# octa-reg_v1\n\nOpen **OPEN_GALLERY.cmd** (offline). Read RUN_REPORT.md for actual results and limitations.\n\nRUN_OR_RESUME.cmd activates octa and resumes the fixed experiment. From code/: `python -m octa_reg_v1 inventory|run|report`, with --output, --inventory, --vessel-export overrides.\n\nAll passing registrations are automatic proposals. Disconnected components have no known mutual placement. Select a date to view imagery; across-date maps retain separate footprints. Click any image for native B-scan/A-line coordinates (zero based).\n\nReview human_review_queue.json; independent human landmarks are pending. Source/configuration/code snapshots, inventory.json, pairs.csv/json, components.json, transforms.json, mosaics/, source_integrity.json and status.json provide reproducibility.\n',encoding='utf-8')
    payload=dict(infos=infos,pairs=pairs,components=components,transforms=transforms,queue=queue,summary=summary)
    # Inline JSON avoids local-file fetch/CORS and works completely offline.
    template=(Path(__file__).parent/'gallery.html').read_text(encoding='utf-8')
    (out/'index.html').write_text(template.replace('__DATA__',json.dumps(payload).replace('</','<\\/')),encoding='utf-8')
