"""Comparable tables, per-boundary maps, blinded queue, and review report."""
import itertools
import numpy as np
from .common import *
from .metrics import *

def run():
    manifest=initialize();boundaries=[];thickness_rows=[];strata_rows=[];strip_rows=[];volumes=[];queue=[];onh_rows=[]
    for si,sid in enumerate(SCANS):
        print('Analyzing',sid,flush=True)
        out=OUT/'volumes'/sid;d=npz(out/'measurements.npz');g=npz(out/'geometry.npz');p=read(out/'prepared.json')
        vessel_prov=p['footprints'].get('vessel',p['footprints'])
        vessel_status=vessel_prov.get('status','unknown')
        vessel_known='no vessel mask' not in vessel_status and vessel_status!='unknown'
        cnv_status='annotated outline context' if g['cnv'].any() else 'unknown; no positive annotated outline'
        raw=d['raw_position_branch'];diag,failed,invalid,cross=diagnostic_thickness(raw,g['shadow'])
        dist,landmark=onh_distance(sid,g);clean=np.where(~invalid,raw,np.nan)
        j,dev=roughness(clean);solid=np.isfinite(d['reported_positions']);dash=np.isfinite(d['uncertain_estimates']);missing=~solid&~dash
        sj,sd=roughness(d['reported_positions']);dj,dd=roughness(d['uncertain_estimates'])
        displayed_spike=np.fmax(sd,dd);displayed_jump=np.fmax(sj,dj)
        save(out/'diagnostics.npz',diagnostic_thickness_um=diag,invalid_thickness=failed,invalid_positions=invalid,
             crossing_pairs=cross,jump_um=j,spike_um=dev,solid_jump_um=sj,solid_spike_um=sd,
             dashed_jump_um=dj,dashed_spike_um=dd,onh_distance_um=dist)
        for k,name in enumerate(SURFACE_NAMES):
            for group,mask,jump,spike in [('all_diagnostic',~invalid,j,dev),('solid',solid,sj,sd),('dashed',dash,dj,dd),('withheld_no_candidate',missing,j,dev)]:
                take=mask[:,k];r=dict(scan_id=sid,boundary=name,segment=group,coverage=float(take.mean()),
                      invalid_fraction=float(invalid[:,k].mean()),geometry_scope='raw diagnostic' if group in ('all_diagnostic','withheld_no_candidate') else 'displayed curve')
                r.update({f'entropy_{key}':v for key,v in stats(d['entropy'][:,k][take]).items()})
                for head,label in enumerate(('traceability','reliability')):
                    r.update({f'{label}_{key}':v for key,v in stats(d['probabilities'][:,k,head][take]).items()})
                r.update(warnings(np.where(take,jump[:,k],np.nan),np.where(take,spike[:,k],np.nan)));boundaries.append(r)
        # Joint context cells avoid conflating signal loss with anatomy.
        signal=np.where(g['local_cnr']<3,0,np.where(g['local_cnr']<10,1,2))
        distance_bin=np.where(np.isnan(dist),-1,np.digitize(dist,[250,500,1000]))
        masks=[('all',np.ones(g['shadow'].shape,bool))]
        for s,v,c,h in itertools.product(range(3),range(2),range(2),[-1,0,1,2,3]):
            mask=(signal==s)&(g['vessel']==v)&(g['cnv']==c)&(distance_bin==h)
            if mask.any():masks.append((f'signal={s};vessel_footprint={v if vessel_known else "unknown"};cnv_outline={c if g["cnv"].any() else "unknown"};onh_bin={h}',mask))
        for mode,t in [('primary',d['primary_thickness_um']),('model_implied_diagnostic',diag)]:
            tj,td=roughness(t,scale=1)
            for k,(name,_,_) in enumerate(LAYERS):
                for context,mask in masks:
                    vals=t[:,k][mask];r=dict(scan_id=sid,mode=mode,layer=name,context=context,context_columns=int(mask.sum()),
                        valid_coverage=float(np.isfinite(vals).mean()),invalid_crossing_fraction=float(failed[:,k][mask].mean()),
                        shadow_fraction=float(g['shadow'][mask].mean()),onh_landmark=landmark,
                        vessel_context_source=vessel_status,cnv_context_source=cnv_status,**stats(vals))
                    r.update({f'roughness_{key}':v for key,v in stats(td[:,k][mask]).items()})
                    r.update({f'adjacent_change_{key}':v for key,v in stats(tj[:,k][mask]).items()})
                    (thickness_rows if context=='all' else strata_rows).append(r)
        for h,label in enumerate(('0-250','250-500','500-1000','1000+')):
            mask=distance_bin==h
            if not mask.any():continue
            for k,name in enumerate(SURFACE_NAMES):
                onh_rows.append(dict(scan_id=sid,boundary=name,distance_bin_um=label,landmark=landmark,
                   n=int(mask.sum()),entropy_median=stats(d['entropy'][:,k][mask])['median'],
                   **warnings(j[:,k][mask],dev[:,k][mask])))
        for b in range(512):
            for lo in range(0,512,64):
                sl=np.s_[b,:,lo:lo+64]
                r=dict(scan_id=sid,bscan=b,lo=lo,hi=lo+64,entropy_median=stats(d['entropy'][sl])['median'],
                    entropy_p95=stats(d['entropy'][sl])['p95'],solid_coverage=float(solid[sl].mean()),
                    dashed_coverage=float(dash[sl].mean()),withheld_no_candidate=float(missing[sl].mean()),
                    signal_cnr_median=stats(g['local_cnr'][b,lo:lo+64])['median'],
                    vessel_fraction=float(g['vessel'][b,lo:lo+64].mean()),cnv_outline_fraction=float(g['cnv'][b,lo:lo+64].mean()),
                    onh_distance_median_um=stats(dist[b,lo:lo+64])['median'],onh_landmark=landmark,
                    **warnings(displayed_jump[sl],displayed_spike[sl]))
                strip_rows.append(r)
        chosen=select_strips(sid,d['entropy'],displayed_spike,20260910+si)
        for i,c in enumerate(chosen):
            r=next(r for r in strip_rows if (r['scan_id'],r['bscan'],r['lo'])==(sid,c['bscan'],c['lo']))
            queue.append(dict(c,id=f'{si+1}-{i+1}',metrics=r))
        q=p['acquisition'];v=dict(scan_id=sid,cohort='new acquisition' if si>=4 else 'original four',
            qualitative_review=NOTES[si],human_regional_assessment='pending',reported_fraction=float(solid.mean()),
            dashed_fraction=float(dash.mean()),withheld_no_candidate=float(missing.mean()),
            entropy_median=stats(d['entropy'])['median'],entropy_p95=stats(d['entropy'])['p95'],
            invalid_position_fraction=float(invalid.mean()),crossing_pair_fraction=float(cross.mean()),
            onh_landmark=landmark,**warnings(displayed_jump,displayed_spike))
        for key in ('retina_vitreous_contrast','retina_cnr','low_signal_frac','bscan_discontinuity_p95','brightness_stripe_power_frac',
                    'axial_centroid_jump_p95_px','axial_centroid_stripe_power_frac','repeat_comparable','repeat_disagreement'):
            v[key]=q[key]
        if q['repeat_comparable']!='True':v['repeat_disagreement']=''
        volumes.append(v)
        render_maps(sid,d,g,j,dev,dist)
    for name,data in [('volumes',volumes),('boundaries',boundaries),('thickness',thickness_rows),('thickness_contexts',strata_rows),('strips',strip_rows),('onh_warnings',onh_rows)]:
        csvwrite(OUT/'reports'/f'{name}.csv',data)
    # Randomize presentation, retaining sampling role only in hidden queue metadata.
    np.random.default_rng(20260910).shuffle(queue)
    atomic_json(OUT/'review_queue.json',dict(examples=queue,model_identity=manifest['fixed_files'][:3]))
    config=read(FROZEN/'launch_config.json');config.update(output=str(OUT/'reviewer'),
        segmentations=str(OUT/'review_packs/scan_queue'),quality_review_queue=str(OUT/'review_queue.json'),
        initial_scan=queue[0]['scan_id'],review_queue=None,manual_sources=[],region_sources=[],
        auto_sources=[dict(name='Frozen v1 automatic before human overrides',directory=str(OUT/'review_packs/automatic'))])
    atomic_json(OUT/'launch_config.json',config)
    write_report(volumes,thickness_rows)
    (OUT/'OPEN_QUALITY_REVIEW.cmd').write_text('@echo off\ncall D:\\Anaconda\\Scripts\\activate.bat octa\ncd /d "'+str(ROOT)+'"\nset "PYTHONPATH='+str(ROOT/'code')+'"\npython -m cnv_review_v1.main --config "'+str(OUT/'launch_config.json')+'"\nif errorlevel 1 pause\n')
    (OUT/'UPDATE_RATING_COMPARISON.cmd').write_text('@echo off\ncall D:\\Anaconda\\Scripts\\activate.bat octa\ncd /d "'+str(ROOT)+'"\nset "PYTHONPATH='+str(ROOT/'code')+'"\npython -m quality_pilot.evaluate_reviews\npause\n')

def render_maps(sid,d,g,j,dev,dist):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    folder=OUT/'maps'/sid;folder.mkdir(parents=True,exist_ok=True)
    for k,name in enumerate(SURFACE_NAMES):
        category=np.where(np.isfinite(d['reported_positions'][:,k]),2,np.where(np.isfinite(d['uncertain_estimates'][:,k]),1,0))
        fig,axes=plt.subplots(2,3,figsize=(12,8),layout='constrained')
        arrays=[(d['entropy'][:,k],'Normalized depth entropy',0,1),
                (j[:,k],'Raw diagnostic adjacent jump (µm)',0,40),(dev[:,k],'Raw diagnostic 9-column excursion (µm)',0,40),
                (category,'0 gap / 1 dashed / 2 solid',0,2),
                (d['probabilities'][:,k,1],'Reliability head score (uncalibrated)',0,1),
                (dist,'ONH distance (µm); blank = unknown',0,1500)]
        for ax,(a,title,lo,hi) in zip(axes.flat,arrays):
            im=ax.imshow(a,origin='upper',vmin=lo,vmax=hi,interpolation='nearest',cmap='viridis');ax.set_title(title,fontsize=9)
            ax.set_xlabel('A-line');ax.set_ylabel('B-scan');fig.colorbar(im,ax=ax,shrink=.75)
            if g['cnv'].any():ax.contour(g['cnv'],levels=[.5],colors='magenta',linewidths=.5)
        fig.suptitle(f'{sid}\n{name} · automatic before human overrides · warnings are not correctness labels',fontsize=11)
        fig.savefig(folder/f'{name}.png',dpi=120);plt.close(fig)

def write_report(volumes,thick):
    lines=['# Six-volume frozen-v1 quality pilot','',
      'All six complete 512-B-scan exports use the same v1 weights, thresholds and candidate rules. The original four neural predictions were reused; reporting and candidates were recomputed before human overrides. No model was trained.',
      '', 'Open **OPEN_QUALITY_REVIEW.cmd** for 24 suggested vertical strips (about 15–30 minutes). Choose Good / Bad / Unsure and drag across the B-scan. Bad is the default. Metrics and sampling reasons remain hidden until that strip is rated. Free browsing works normally. Ratings are separate from boundary annotations.',
      '', '## Separate evidence axes','',
      '| Scan | CNR | Low signal % | Solid % | Dashed % | Entropy P95 | Displayed jump >20 µm % | Displayed spike >20 µm % | Original user review |',
      '|---|---:|---:|---:|---:|---:|---:|---:|---|']
    for v in volumes:
        lines.append(f"| {v['scan_id']} | {float(v['retina_cnr']):.2f} | {100*float(v['low_signal_frac']):.2f} | {100*v['reported_fraction']:.2f} | {100*v['dashed_fraction']:.2f} | {v['entropy_p95']:.3f} | {100*(v['jump_gt20_fraction'] or 0):.2f} | {100*(v['spike_gt20_fraction'] or 0):.2f} | {v['qualitative_review']} |")
    lines += ['', '## Definitions and limitations','',
      '- Acquisition axes come from scan_quality_metrics.csv: raw retinal/vitreous contrast, CNR, low signal, motion and stripes. Repeat disagreement is omitted unless repeat_comparable is true. They are not segmentation scores.',
      '- Entropy is Shannon entropy of the native depth softmax divided by log(depth); median and P95 are retained. Low entropy can accompany a confidently misplaced line. State-head scores are not established calibrated probabilities.',
      '- Adjacent jump is absolute depth change within a finite stretch, assigned to the right A-line. Its denominator is eligible adjacent pairs. Spike is absolute deviation from the nine-A-line median, padded with the endpoint inside each finite stretch; its denominator is finite positions. Neither calculation bridges gaps or changes a surface. Warnings use >20 µm, with identical >10 and >40 sensitivity summaries.',
      '- Solid and dashed curves are evaluated separately. Withheld/no-candidate geometry statistics refer only to raw diagnostic proposals, never displayed continuations. The displayed aggregate pools solid and dashed eligible locations without bridging between them.',
      '- Thickness tables report population SD, median, mean, IQR, coverage and local roughness. Primary thickness is the unchanged v1 definition. Diagnostic thickness uses raw finite in-image positions, rejects crossing/intermediate-invalid boundaries, and masks shadows. RNFL/TOTAL/INNER_RETINA primary coverage is zero because v1 withholds ILM. TOTAL ends at the eight-surface outer RPE edge.',
      '- ONH distances use native Euclidean lateral spacing (~1460/512 µm). TS165 distances are to its annotated mask, zero inside. TS283 uses a partial-edge proxy. All other distances remain unknown.',
      '- Context table cells jointly separate local signal CNR (<3, 3–10, ≥10), vessel footprint, CNV outline, and ONH distance (0–250, 250–500, 500–1000, ≥1000 µm; -1 unknown). Outside a mask is not confirmed absence. Missing vessel/CNV annotations remain unknown context; footprint provenance is in each prepared.json. Automatic vessel proposals are not human annotations.',
      '- CNV outlines and acquisition motion/stripe measurements provide context for deformations; warnings never assign an automatic wrong label. Distribution differences, smoothness and matching averages cannot establish correctness.',
      '', '## Files','',
      '- reports/volumes.csv: acquisition, model behavior and preserved full-volume feedback in separate columns.',
      '- reports/boundaries.csv: every boundary × solid/dashed/withheld/raw, with state scores, entropy and 10/20/40 µm warnings.',
      '- reports/thickness.csv and thickness_contexts.csv: primary and diagnostic thickness distributions, including invalid/crossing fractions and coverage.',
      '- reports/onh_warnings.csv, reports/strips.csv, maps/<scan>/<boundary>.png and volumes/<scan>/diagnostics.npz: native maps and spatial summaries.',
      '- volumes/<scan>/measurements.npz and review_packs: complete automatic exports. The four frozen source volumes and all existing human labels remain intact.',
      '- reviewer/quality_reviews: GUI-only Good/Bad/Unsure records with model identity, undo and clear history. No position targets, visibility marks, or exclusions are made by these ratings.',
      '', '## Assessment and next decision','',
      'Regional human judgments are pending. Run UPDATE_RATING_COMPARISON.cmd after review to compare entropy, jumps and spikes with Good/Bad, retaining Unsure and separating random from targeted samples. No regional failure rate or metric accuracy can yet be estimated.',
      '', 'Continue the focused review workflow if unseen acquisitions remain comparable by human assessment. If positions are good but solid/dashed choices are poor, prioritize reporting/candidates. Investigate training/preprocessing before architecture if major positional failures occur in good signal. Prioritize obscuration handling if failures cluster in low signal. This pilot does not independently establish unseen-animal generalization: these animals contributed other acquisitions to the labeled development cohort.',
      '', 'Evaluation follows the task-specific uncertainty principle in [ValUES (ICLR 2024)](https://proceedings.iclr.cc/paper_files/paper/2024/hash/1548d98b62d3a4382a31ba77d89186cd-Abstract-Conference.html); warning performance must be checked against independent human judgments rather than assumed from entropy.']
    (OUT/'START_HERE.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

if __name__=='__main__':run()
