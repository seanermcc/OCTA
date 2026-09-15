"""Descriptive six-output comparisons; accuracy only on audited known pixels."""
from batch import *
from metrics import aggregate,match
from itertools import combinations
from PIL import Image,ImageDraw
import html
from asset_storage import asset_bytes,save_assets,pack_existing_assets
COMPARISON_SCHEMA = 2

def native_iou(a,b):
    n,m=int(a.max()),int(b.max());aa=np.bincount(a.ravel(),minlength=n+1)[1:];bb=np.bincount(b.ravel(),minlength=m+1)[1:]
    joint=np.bincount((a.astype('int64')*(m+1)+b).ravel(),minlength=(n+1)*(m+1)).reshape(n+1,m+1)[1:,1:]
    return joint/np.maximum(1,aa[:,None]+bb[None,:]-joint)

def grey(a):
    valid=a[np.isfinite(a)];lo,hi=np.percentile(valid,[2,98]) if len(valid) else (0,1)
    return np.uint8(np.clip((np.nan_to_num(a,nan=lo)-lo)/max(hi-lo,1e-6),0,1)*255)

def outline(mask,color):
    a=np.zeros((*mask.shape,4),np.uint8);edge=mask&~ndi.binary_erosion(mask);a[edge]=color
    return Image.fromarray(a)

def compare_scan(r):
    sid=r['scan_id'];record=read(HERE/'records'/f'{sid}.json')
    preds={key:npz(HERE/'predictions'/key/f'{sid}.npz') for key in KEYS}
    masks=np.stack([preds[k]['mask'] for k in KEYS]);labels={k:preds[k]['candidate_labels'] for k in KEYS}
    pairrows=[];support={k:np.ones(int(labels[k].max()),int) for k in KEYS};crosssupport={k:{} for k in KEYS}
    disagreements={};matches={}
    for a,b in combinations(KEYS,2):
        ma=preds[a]['mask'];mb=preds[b]['mask'];inter=int((ma&mb).sum());union=int((ma|mb).sum());den=int(ma.sum()+mb.sum())
        diff=ma^mb;disagreements[a+'__'+b]=diff
        same=a[0]==b[0];paired=a.split('_')[1]==b.split('_')[1]
        pairs=match(native_iou(labels[a],labels[b]),.1);matches[(a,b)]=pairs
        if same:
            for i,j in pairs:support[a][i]+=1;support[b][j]+=1
        pairrows.append(dict(scan_id=sid,model_a=a,model_b=b,comparison='within experiment seeds' if same else 'B vs C matching seed' if paired else 'B vs C different seeds',
            dice=2*inter/den if den else None,iou=inter/union if union else None,empty_both=not union,
            disagreement_pixels=int(diff.sum()),disagreement_area_mm2=float(diff.sum()*UM**2/1e6),
            suggestion_count_delta_b_minus_a=int(labels[b].max()-labels[a].max()),suggested_area_delta_b_minus_a_mm2=float((int(mb.sum())-int(ma.sum()))*UM**2/1e6),matched_suggestion_pairs=len(pairs)))
    vote_b=masks[:3].sum(0).astype('uint8');vote_c=masks[3:].sum(0).astype('uint8');all_diff=masks.any(0)&~masks.all(0)
    save(HERE/'comparison/native'/f'{sid}.npz',votes_B=vote_b,votes_C=vote_c,all_six_disagreement=all_diff,**disagreements)
    unstable=[]
    for key in KEYS:
        for i,n in enumerate(support[key]):
            if n==3:continue
            mask=labels[key]==i+1;ys,xs=np.nonzero(mask)
            unstable.append(dict(scan_id=sid,model=key,suggestion_id=i+1,seeds_with_matched_suggestion=int(n),seeds_total=3,
                matching_definition='one-to-one component IoU >= 0.1; optimization variability, not truth',pixels=len(ys),
                centroid_bscan=float(ys.mean()),centroid_aline=float(xs.mean()),bbox=[int(ys.min()),int(xs.min()),int(ys.max()+1),int(xs.max()+1)]))
    assets={}
    opt=npz(HERE/'inputs'/f'{sid}.npz')['optical']
    for i,name in enumerate(('structural','octa')):asset_bytes(Image.fromarray(grey(opt[i])),f'{name}.jpg','JPEG',assets,quality=90)
    for key in KEYS:asset_bytes(outline(preds[key]['mask'],[255,176,66,255]),f'{key}.png','PNG',assets)
    ref=reference_arrays(sid)['target'];asset_bytes(outline(ref,[45,230,255,255]),'reference.png','PNG',assets)
    asset_bytes(outline(all_diff,[255,65,218,255]),'disagreement.png','PNG',assets)
    # Depth samples point to the exact native rows at disagreement/edge/random locations.
    vp=Path(r['upstream_volume']);images_path=vp/'images.npy'
    ys,xs=np.nonzero(all_diff);chosen=sorted(set([64,256,448]+([int(np.median(ys))] if len(ys) else [])))
    if images_path.exists():
        images=np.load(images_path,mmap_mode='r')
        for b in chosen:
            im=Image.fromarray(grey(images[b]))
            im=im.resize((512,max(1,round(images.shape[1]*1.12/UM))),Image.Resampling.BILINEAR)
            asset_bytes(im,f'bscan_{b}.jpg','JPEG',assets,quality=91)
    else:
        # New acquisitions retain on-demand full native B-scans in the dedicated GUI.
        chosen=[]
    save_assets(sid,assets)
    out=dict(scan_id=sid,disagreement_pixels=int(all_diff.sum()),within_B_disagreement_pixels=int(((vote_b>0)&(vote_b<3)).sum()),within_C_disagreement_pixels=int(((vote_c>0)&(vote_c<3)).sum()),
        inconsistent_suggestions=len(unstable),possible_misses_proxy=max((x['additions_proxy'] for x in record['evaluation'] if x['iou_cutoff']==.1),default=0),
        any_model_no_suggestions=any(int(labels[k].max())==0 for k in KEYS),all_models_no_suggestions=all(int(labels[k].max())==0 for k in KEYS),
        support_artifact_edge_priority=bool(min(record['available_fraction_by_layer'])<.5 or record['shadow_fraction']>.2 or record['low_signal_fraction']>.1 or any(x['edge_pixels'] for x in record['models'])),
        available_fraction_by_layer=record['available_fraction_by_layer'],shadow_fraction=record['shadow_fraction'],low_signal_fraction=record['low_signal_fraction'],
        field_edge_suggestion_pixels=max(x['edge_pixels'] for x in record['models']),
        depth_rows=chosen,models=record['models'],annotation_kind=record['annotation_audit']['annotation_kind'],annotation_complete=record['annotation_audit']['complete'],
        original_pilot=r['original_pilot'],pilot_split=r['pilot_split'],animal=r['animal'],eye=r['eye'],session_date=r['session_date'],day_label=r['day_label'],days_post_laser=r.get('days_post_laser',''),
        scan_no=r['scan_no'],acq_time=r['acq_time'],cnv_animal_exposure=r['cnv_animal_exposure'],upstream_animal_exposure=r['upstream_animal_exposure'],upstream_scan_exposure=r['upstream_scan_exposure'])
    return out,pairrows,unstable

def build():
    m=read(HERE/'inventory.json');scans=[];pairs=[];unstable=[];rawrows=[];evalrows=[];annotation_rows=[]
    cache_path=HERE/'comparison/scan_cache.json';cache=read(cache_path) if cache_path.exists() else {}
    for r in m['scans']:
        sid=r['scan_id'];rp=HERE/'records'/f'{sid}.json'
        if not rp.exists() or read(rp).get('status')!='completed':continue
        cp=HERE/'comparison/scans'/f'{sid}.json'
        data=cache.get(sid) or (read(cp) if cp.exists() else {})
        if data.get('schema')==COMPARISON_SCHEMA:
            s,pp,uu=data['summary'],data['pairwise'],data['inconsistent_suggestions'];pack_existing_assets(sid)
        else:s,pp,uu=compare_scan(r)
        cache[sid]=dict(schema=COMPARISON_SCHEMA,summary=s,pairwise=pp,inconsistent_suggestions=uu)
        # Metadata may be refined after inference without invalidating spatial caches.
        s.update({k:r.get(k,'unknown') for k in ('cnv_scan_exposure','cnv_training_sample','cnv_normalization_source','upstream_scan_exposure','cnv_animal_exposure','upstream_animal_exposure')})
        for u in uu:u['matching_definition']='one-to-one component IoU >= 0.1; frozen seed-specific weights and validation thresholds; descriptive agreement'
        scans.append(s);pairs.extend(pp);unstable.extend(uu);rec=read(rp)
        audit=rec['annotation_audit']
        annotation_rows.append(dict(scan_id=sid,complete=audit['complete'],annotation_kind=audit['annotation_kind'],
            positive_pixels=audit['positive_pixels'],negative_pixels=audit['negative_pixels'],ignored_pixels=audit['ignored_pixels'],
            issues='; '.join(audit.get('issues',[])),reference_sources='; '.join(fp['path'] for fp in audit.get('sources',[])),
            historical_active_review_seconds=audit.get('review_context',{}).get('active_review_seconds'),
            instance_definition=audit.get('instance_definition','unknown / no usable instances')))
        strata={k:r[k] for k in ('animal','eye','session_date','day_label','pilot_split','cnv_animal_exposure','upstream_animal_exposure','upstream_scan_exposure')}
        strata.update(cnv_scan_exposure=r.get('cnv_scan_exposure','unknown'),cnv_training_sample=r.get('cnv_training_sample','unknown'),cnv_normalization_source=r.get('cnv_normalization_source','unknown'),days_post_laser=r.get('days_post_laser',''))
        strata.update(annotation_kind=rec['annotation_audit']['annotation_kind'],annotation_complete=rec['annotation_audit']['complete'])
        rawrows.extend(dict(scan_id=sid,**strata,**x) for x in rec['models'])
        evalrows.extend(dict(**strata,**x) for x in rec['evaluation'] if x['known_pixels']>0)
    ids=sorted(r['scan_id'] for r in m['scans']);rng=np.random.default_rng(6267)
    random_ids=set(rng.choice(ids,min(24,len(ids)),replace=False).tolist())
    empty_all=sorted(s['scan_id'] for s in scans if s['all_models_no_suggestions'] and s['scan_id'] not in random_ids)
    n_empty=min(4,len(empty_all));random_ids.update(rng.choice(empty_all,n_empty,replace=False).tolist())
    zero=sorted(s['scan_id'] for s in scans if s['any_model_no_suggestions'] and s['scan_id'] not in random_ids)
    random_ids.update(rng.choice(zero,min(8-n_empty,len(zero)),replace=False).tolist())
    for s in scans:
        s['fixed_random_sample']=s['scan_id'] in random_ids
        reasons=[]
        if s['disagreement_pixels']:reasons.append('B/C or seed disagreement')
        if s['possible_misses_proxy']:reasons.append('possible missed reference lesion (proxy)')
        if min(s.get('available_fraction_by_layer',[1]))<.5:reasons.append('low automatic support')
        if s.get('shadow_fraction',0)>.2:reasons.append('automatic shadow')
        if s.get('low_signal_fraction',0)>.1:reasons.append('low source signal')
        if s.get('field_edge_suggestion_pixels',0):reasons.append('field-edge suggestions')
        if s['fixed_random_sample']:reasons.append('fixed random control')
        if s['all_models_no_suggestions']:reasons.append('all six models have no suggestions')
        elif s['any_model_no_suggestions']:reasons.append('one or more models has no suggestions')
        s['review_reasons']='; '.join(reasons)
    write(HERE/'comparison/review_queue.json',scans)
    write(cache_path,cache)
    write(HERE/'comparison/random_sample_protocol.json',dict(seed=6267,uniform_all_acquisitions=24,additional_uniform_no_suggestion_acquisitions=8,up_to_four_additional_all_six_empty=True,selected=sorted(random_ids),definition='Sorted acquisition IDs; fixed RNG sample of 24, up to four further acquisitions empty in all six outputs, then remaining supplement slots from acquisitions empty in at least one output, without replacement. No quality-based exclusion.'))
    csv_write(HERE/'comparison/per_scan_six_models.csv',rawrows);csv_write(HERE/'comparison/pairwise_spatial_agreement.csv',pairs)
    csv_write(HERE/'comparison/annotation_inventory.csv',annotation_rows)
    csv_write(HERE/'comparison/inconsistent_suggestions.csv',unstable);csv_write(HERE/'comparison/annotation_evaluation.csv',evalrows)
    variability=[]
    for s in scans:
        for experiment in 'BC':
            rr=[r for r in rawrows if r['scan_id']==s['scan_id'] and r['model'].startswith(experiment)]
            counts=[r['suggestions'] for r in rr];areas=[r['suggested_area_mm2'] for r in rr]
            pp=[p for p in pairs if p['scan_id']==s['scan_id'] and p['model_a'].startswith(experiment) and p['model_b'].startswith(experiment)]
            dice=[p['dice'] for p in pp if p['dice'] is not None]
            variability.append(dict(scan_id=s['scan_id'],experiment=experiment,seed_count=3,suggestion_count_min=min(counts),suggestion_count_max=max(counts),
                suggestion_count_sd=float(np.std(counts)),area_min_mm2=min(areas),area_max_mm2=max(areas),area_sd_mm2=float(np.std(areas)),
                mean_pairwise_dice=float(np.mean(dice)) if dice else None,all_empty_pairs=sum(p['empty_both'] for p in pp),
                disagreement_pixels=s['within_'+experiment+'_disagreement_pixels']))
    csv_write(HERE/'comparison/per_scan_seed_variability.csv',variability)
    paired_summary=[]
    for seed in (267,268,269):
        for split in sorted({r['pilot_split'] for r in scans}):
            ids_in={r['scan_id'] for r in scans if r['pilot_split']==split}
            pp=[r for r in pairs if r['model_a']==f'B_{seed}' and r['model_b']==f'C_{seed}' and r['scan_id'] in ids_in]
            dice=[r['dice'] for r in pp if r['dice'] is not None]
            paired_summary.append(dict(seed=seed,pilot_split=split,acquisitions=len(pp),mean_spatial_dice=float(np.mean(dice)) if dice else None,
                both_empty_acquisitions=sum(r['empty_both'] for r in pp),total_count_delta_C_minus_B=sum(r['suggestion_count_delta_b_minus_a'] for r in pp),
                total_area_delta_C_minus_B_mm2=sum(r['suggested_area_delta_b_minus_a_mm2'] for r in pp),
                interpretation='Paired descriptive differences; no winning seed selected'))
    csv_write(HERE/'comparison/matched_seed_B_vs_C.csv',paired_summary)
    groups=[]
    for key in KEYS:
        for cutoff in PROTOCOL['iou_thresholds']:
            rows=[r for r in evalrows if r['model']==key and r['iou_cutoff']==cutoff]
            for axis in ('pilot_split','animal','eye','session_date','day_label','annotation_kind','cnv_animal_exposure','cnv_scan_exposure','upstream_animal_exposure','upstream_scan_exposure'):
                for value in sorted({str(r[axis]) for r in rows}):
                    subset=[r for r in rows if str(r[axis])==value]
                    borders=[r for r in subset if r['border_mean_um'] is not None and r['border_pairs']]
                    n_border=sum(r['border_pairs'] for r in borders)
                    groups.append(dict(model=key,iou_cutoff=cutoff,stratum=axis,value=value,
                        matched_boundary_pairs=n_border,mean_matched_boundary_error_um=sum(r['border_mean_um']*r['border_pairs'] for r in borders)/n_border if n_border else None,
                        **aggregate(subset)))
    csv_write(HERE/'comparison/evaluation_strata.csv',groups)
    cohorts=[]
    for key in KEYS:
        rows=[r for r in rawrows if r['model']==key]
        for axis in ('all','animal','eye','session_date','day_label','pilot_split','annotation_kind','cnv_animal_exposure','cnv_scan_exposure','upstream_animal_exposure','upstream_scan_exposure'):
            vals=['all'] if axis=='all' else sorted({str(r[axis]) for r in rows})
            for val in vals:
                rr=rows if axis=='all' else [r for r in rows if str(r[axis])==val]
                if not rr:continue
                cohorts.append(dict(model=key,stratum=axis,value=val,acquisitions=len(rr),animals=len({r['animal'] for r in rr}),
                    total_suggestions=sum(r['suggestions'] for r in rr),zero_suggestion_scans=sum(r['suggestions']==0 for r in rr),
                    median_suggestions=float(np.median([r['suggestions'] for r in rr])),total_suggested_area_mm2=sum(r['suggested_area_mm2'] for r in rr),
                    equal_animal_mean_suggested_area_mm2=float(np.mean([np.mean([r['suggested_area_mm2'] for r in rr if r['animal']==a]) for a in sorted({r['animal'] for r in rr})]))))
    csv_write(HERE/'comparison/prediction_strata.csv',cohorts)
    csv_write(HERE/'comparison/review_queue.csv',[{k:v for k,v in s.items() if not isinstance(v,(list,dict))} for s in scans])
    render_index(scans)
    summary=dict(completed_scans=len(scans),prediction_sets=len(scans)*6,animals=len({r['animal'] for r in scans}),
        annotated_comparison_scans=len({r['scan_id'] for r in evalrows}),completed_reference_fields=sum(s['annotation_complete'] for s in scans),
        disagreement_scans=sum(s['disagreement_pixels']>0 for s in scans),random_sample=len(random_ids),human_evaluation='pending')
    write(HERE/'comparison/summary.json',summary)
    text_report=['# Six-model comparison','',f"{len(scans)} acquisitions have all six outputs. {summary['animals']} animals. These are descriptive expanded-cohort predictions, not independent validation.",'',
        '| Model | Suggestions | No-suggestion scans | Median count | Total suggested area mm² |','|---|---:|---:|---:|---:|']
    for r in cohorts:
        if r['stratum']=='all':text_report.append(f"| {r['model']} | {r['total_suggestions']} | {r['zero_suggestion_scans']} | {r['median_suggestions']:g} | {r['total_suggested_area_mm2']:.4f} |")
    text_report+=['','[Navigable overlays](index.html) · [Every paired comparison](pairwise_spatial_agreement.csv) · [Inconsistent suggestions](inconsistent_suggestions.csv) · [Review queue](review_queue.csv)','',
        'Both-empty spatial comparisons are recorded as empty, with Dice/IoU undefined. All native predictions and components remain available; no lesion size, count or shape filters are applied. Total suggested area sums acquisition footprints, including repeated tissue; it is not unique disease burden. Seed variability includes both learned weights and each seed’s original validation-selected threshold (B: 0.7 / 0.1 / 0.8; C: 0.5 / 0.5 / 0.5 for seeds 267 / 268 / 269). Thresholds were not harmonized or tuned on these scans.',
        '', 'Area and boundary-distance units use the frozen approximate lateral scale of 1460 micrometers across 512 pixels; no per-animal magnification recalibration was performed.',
        '',f"Audited existing annotations support comparisons on {summary['annotated_comparison_scans']} scans; {summary['completed_reference_fields']} have v5 whole-field completion. Missing annotations never represent negative labels. Legacy references are positive-only and use connected footprint components when original instance identity is unavailable.",
        '', 'On positive-only references, high known-pixel overlap can mean that the prediction covers the labeled lesion; unreviewed surrounding tissue cannot establish false-suggestion or outline accuracy. Use the annotation-completeness strata when interpreting these values.',
        '','Evaluation follows the frozen v6 ignored-region, one-to-one matching and boundary definitions at IoU 0.1/0.25/0.5. Additions, removals and outline corrections in evaluation tables are comparison-derived proxies. No observed human actions or time savings are inferred. Some completed OS references have brief historical review times; their completion metadata is retained from v6, without new adjudication.',
        '','Seeds, repeated acquisitions and repeated visits are not independent animals. Pilot train, validation and development-holdout scans are identified separately. New acquisitions of TS267 retain exposure to the CNV training animal. The upstream ALL_LABELLED layer model contains all historically imaged animals; per-scan exposure and unknown values are retained.',
        '','Mean projections discard axial position and layer relationships. Disagreement alone cannot establish that depth is needed. Review native B-scans for persistent misses, artifacts, low support and field edges before proposing architectural expansion. The GUI supports every native B-scan; exported depth thumbnails are illustrative rows, not a substitute for whole-field review.']
    dest(HERE/'comparison/REPORT.md').write_text('\n'.join(text_report)+'\n',encoding='utf-8')
    print(json.dumps(summary),flush=True)

def render_index(scans):
    template='''<!doctype html><html><head><meta charset="utf-8"><title>CNV v6 · all acquisitions</title><style>
body{font:15px system-ui;background:#111720;color:#e6edf7;margin:24px}header{max-width:1100px}select,input,button{font:inherit;background:#213047;color:white;padding:9px;border:1px solid #5e718d;border-radius:5px}a{color:#78caff}.grid{display:grid;grid-template-columns:repeat(3,minmax(260px,1fr));gap:16px}.card{background:#1b2636;padding:12px;border-radius:8px}.im{position:relative;aspect-ratio:1}.im img{width:100%;height:100%;position:absolute;image-rendering:auto}.small{color:#b5c4d9}.depth img{max-width:480px;width:100%}.depth{display:flex;flex-wrap:wrap;gap:12px}h2{font-size:18px}table{border-collapse:collapse}td,th{padding:7px;text-align:left;border-bottom:1px solid #40506b}</style></head><body>
<header><h1>CNV v6 · six frozen models</h1><p>Orange: automatic footprint · cyan: existing reference · magenta: disagreement. Scores are uncalibrated model scores. Unreviewed scans have no accuracy labels.</p><p><a href="../START_HERE.md">Open the guide and CNV editor launcher instructions</a> · <a href="REPORT.md">Comparison report</a> · <a href="pairwise_spatial_agreement.csv">All paired measurements</a></p></header>
<p><input id="search" placeholder="Animal, eye, date or acquisition"><select id="filter"><option>All</option><option>Disagreements</option><option>Fixed random sample</option><option>Possible misses</option><option>No suggestions (any model)</option><option>Low support / artifacts / edges</option><option>No suggestions (all six)</option></select><select id="scan"></select></p>
<p><button id="prev">Previous</button> <button id="next">Next</button> <select id="background"><option value="structural">Structural OCT</option><option value="octa">Actual OCTA</option></select> <label><input type="checkbox" id="refs" checked>Reference</label> <label><input type="checkbox" id="diff">Disagreements</label></p>
<h2 id="title"></h2><p id="meta" class="small"></p><div class="grid" id="grid"></div><h2>Native depth examples</h2><p class="small">The dedicated CNV GUI provides linked selection of every native B-scan and editable footprints. These browser images are read-only.</p><div class="depth" id="depth"></div><script>
const scans=SCANDATA,keys=['B_267','B_268','B_269','C_267','C_268','C_269'];let visible=scans;
const $=id=>document.getElementById(id);function fill(){let q=$('search').value.toLowerCase(),f=$('filter').selectedIndex;visible=scans.filter(r=>JSON.stringify([r.scan_id,r.animal,r.eye,r.day_label]).toLowerCase().includes(q)&&[true,r.disagreement_pixels>0,r.fixed_random_sample,r.possible_misses_proxy>0,r.any_model_no_suggestions,r.support_artifact_edge_priority,r.all_models_no_suggestions][f]);$('scan').innerHTML=visible.map((r,i)=>`<option value="${i}">${r.scan_id}</option>`).join('');render()}
window.CNV_ASSETS={};let renderVersion=0;const assetPromises={};
function assetsFor(sid){if(window.CNV_ASSETS[sid])return Promise.resolve(window.CNV_ASSETS[sid]);if(assetPromises[sid])return assetPromises[sid];return assetPromises[sid]=new Promise((resolve,reject)=>{let s=document.createElement('script');s.src='assets/'+sid+'.js';s.onload=()=>resolve(window.CNV_ASSETS[sid]);s.onerror=()=>{delete assetPromises[sid];reject(new Error('Preview bundle could not be loaded.'));};document.head.appendChild(s)})}
async function render(){const version=++renderVersion;let r=visible[+$('scan').value];if(!r){$('title').textContent='No acquisitions match this filter';$('meta').textContent='';$('grid').innerHTML='';$('depth').innerHTML='';return;}location.hash=r.scan_id;$('title').textContent=r.scan_id;$('meta').textContent=`${r.pilot_split} · ${r.annotation_kind} · ${r.cnv_animal_exposure} · ${r.upstream_animal_exposure} · disagreement: ${r.disagreement_pixels} pixels. Human v6 evaluation pending.`;let assets;try{assets=await assetsFor(r.scan_id)}catch(e){if(version===renderVersion){$('meta').textContent=e.message;$('grid').innerHTML='';$('depth').innerHTML='';}return;}if(version!==renderVersion)return;$('grid').innerHTML=keys.map(k=>{let m=r.models.find(x=>x.model===k);return `<div class="card"><h2>${k.replace('_',' · seed ')}</h2><p>${m.suggestions} suggestions · ${m.suggested_area_mm2.toFixed(5)} mm²</p><div class="im"><img src="${assets[$('background').value+'.jpg']}"><img src="${assets[k+'.png']}">${$('refs').checked?`<img src="${assets['reference.png']}">`:''}${$('diff').checked?`<img src="${assets['disagreement.png']}">`:''}</div></div>`}).join('');$('depth').innerHTML=r.depth_rows.length?r.depth_rows.map(b=>`<div><p>B-scan ${b}</p><img src="${assets['bscan_'+b+'.jpg']}"></div>`).join(''):'<p>Open this acquisition in the CNV GUI for native B-scans recovered directly from the processed volume.</p>'}
['search','filter'].forEach(id=>$(id).addEventListener('input',fill));['scan','background','refs','diff'].forEach(id=>$(id).addEventListener('change',render));$('prev').onclick=()=>{$('scan').selectedIndex=Math.max(0,$('scan').selectedIndex-1);render()};$('next').onclick=()=>{$('scan').selectedIndex=Math.min(visible.length-1,$('scan').selectedIndex+1);render()};let initial=decodeURIComponent(location.hash.slice(1));fill();let idx=visible.findIndex(r=>r.scan_id===initial);if(idx>=0){$('scan').value=idx;render()}
</script></body></html>'''
    dest(HERE/'comparison/index.html').write_text(template.replace('SCANDATA',json.dumps(scans).replace('</','<\\/')),encoding='utf-8')

if __name__=='__main__':build()
