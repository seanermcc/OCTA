"""Read-only inventory refresh and frozen visit-aware queue. Never reshuffles on restart."""
from common import *
import csv, re, random
from collections import defaultdict, Counter

SEED=20260918

def day_value(r):
    label=str(r.get('day_label','')).strip()
    if r['animal']=='TS165' or re.search(r'WT|before|pre.?laser',label,re.I):return None,'WT or before laser'
    actual=r.get('days_post_laser','')
    if str(actual).strip():
        try:return float(actual),'verified indexed days_post_laser'
        except ValueError:return None,'unresolved actual day value'
    if re.search(r'laser.?day|^D0$',label,re.I):return 0.,'nominal laser day'
    indexed=str(r.get('day','')).strip()
    if indexed:
        try:return float(indexed),'indexed nominal day; actual interval unknown'
        except ValueError:pass
    match=re.fullmatch(r'D\s*(\d+)',label,re.I)
    if match:return float(match[1]),'parsed nominal '+label+'; actual interval unknown'
    match=re.fullmatch(r'(\d+(?:\.\d+)?)\s*(?:mo|months?)',label,re.I)
    if match:return float(match[1])*30.,'nominal months x 30 for eligibility only; actual interval unknown'
    return None,'unresolved timepoint'

def ordered_queue(eligible,seed=SEED):
    rng=random.Random(seed);pools={};visits={};exhaustion=[]
    animals=sorted({r['animal'] for r in eligible},key=lambda a:int(a[2:]))
    for animal in animals:
        groups=defaultdict(list)
        for r in sorted(eligible,key=lambda r:r['scan_id']):
            if r['animal']==animal:groups[r['session_date']].append(r)
        dates=sorted(groups);rng.shuffle(dates);visits[animal]=len(dates)
        for g in groups.values():rng.shuffle(g)
        pool=[]
        while any(groups.values()):
            for d in dates:
                if groups[d]:pool.append(groups[d].pop())
        pools[animal]=pool
    queue=[];cycle=0
    while any(pools.values()):
        for a in animals:
            if pools[a]:queue.append(dict(pools[a].pop(0),queue_position=len(queue)+1,animal_cycle=cycle+1,
                ordering_rationale='numeric animal cycle; seeded shuffled visit round robin; shuffled acquisition without replacement'))
            elif not any(e['animal']==a for e in exhaustion):exhaustion.append(dict(animal=a,cycle=cycle+1,reason='eligible pool exhausted'))
        cycle+=1
    for a in animals:
        if not any(e['animal']==a for e in exhaustion):exhaustion.append(dict(animal=a,cycle=cycle+1,reason='eligible pool exhausted'))
    return queue,dict(animals=animals,visit_counts=visits,exhaustion=exhaustion)

def historical_inventory(scans):
    records=[];by_sid={r['scan_id']:r for r in scans}
    folders=[('original',ROOT/'outputs/cnv_labels','*_cnv.npz')]
    folders += [(v,ROOT/f'outputs/octa-auto_cnv_{v}/review/regions','*_regions.json') for v in ('v3','v4','v5')]
    folders += [('v6',ROOT/'outputs/octa-auto_cnv_unet_v6/review/regions','*_regions.json'),
                ('original_classification',ROOT/'outputs/cnv_review_v1/regions','*_regions.json')]
    for version,folder,pattern in folders:
        for p in sorted(folder.glob(pattern)):
            fp=fingerprint(p);entry=dict(version=version,source=fp)
            if p.suffix=='.npz':
                with np.load(p,allow_pickle=False) as z:
                    def scalar(key,default=''):
                        return np.asarray(z[key]).reshape(-1)[0].item() if key in z else default
                    sid=scalar('scan_id');native=list(z['cnv_mask'].shape)
                    entry.update(scan_id=sid,source_volume=scalar('source_volume'),native_shape=native,
                        revision=scalar('format_version'),reviewed=bool(scalar('reviewed',False)),
                        positive_pixels=int(z['cnv_mask'].sum()),scope='positive-only; never infer whole-field background from legacy absence',
                        original_metadata={k:np.asarray(z[k]).tolist() for k in z.files if k not in ('cnv_mask','vasculature_mask','onh_mask','onh_edge_mask') and z[k].size<32})
            else:
                d=read(p);sid=d['scan_id'];regions=d.get('regions',[])
                pos=np.zeros((512,512),bool);unc=pos.copy();kept=0;unsure=0;issues=[]
                for r in regions:
                    try:m=decode(r.get('runs',[]))
                    except ValueError as exc:issues.append(str(exc));continue
                    if r.get('decision')=='approved' and r.get('category')=='Full Lesion' and r.get('classification_complete'):
                        pos|=m;kept+=int(m.any())
                    elif r.get('decision')!='rejected' and (r.get('category')=='Other' or not r.get('classification_complete') or r.get('decision')=='unreviewed'):
                        unc|=m;unsure+=int(r.get('category')=='Other')
                entry.update(scan_id=sid,source_volume=d.get('source_volume'),native_shape=d.get('native_shape'),
                    revision=d.get('revision'),reviewer_version=d.get('reviewer_version'),review_events=d.get('review_events',[]),active_error_ids=d.get('active_error_ids',[]),scope='whole-field' if version=='v5' and d.get('scan_review',{}).get('whole_field_checked') else 'partial; no implicit background',
                    whole_field=bool(version=='v5' and d.get('scan_review',{}).get('whole_field_checked')),kept_entries=kept,unsure_entries=unsure,
                    positive_pixels=int(pos.sum()),ignored_pixels=int(unc.sum()),conflict_pixels=int((pos&unc).sum()),
                    regions=regions,scan_review=d.get('scan_review'),review_context=d.get('review_context'),
                    model_ratings=d.get('model_ratings',d.get('ratings',{})),rating_review=d.get('rating_review',{}),issues=issues)
            r=by_sid.get(sid)
            entry['identity_matches']=bool(r and Path(entry['source_volume']).resolve()==Path(r['source']).resolve() and entry['native_shape']==[512,512])
            records.append(entry)
    atomic(HERE/'reports/historical_labels.json',dict(created=now(),records=records,
        rule='Sources are not unioned. Valid v7 confirmation supersedes older evidence for the same source. V7 draft blocks automatic fallback pending adjudication. Otherwise prefer v5 > v4 > v3 > original for footprints; v6 explicit human masks require adjudication; ratings/predictions never pixel truth.'))
    precedence=[]
    for r in scans:
        sources=[x for x in records if x['scan_id']==r['scan_id']]
        if sources:precedence.append(dict(scan_id=r['scan_id'],source_identity=r.get('source_identity'),sources=[x['source'] for x in sources],
            rule='v7 confirmed supersedes; v7 draft blocks fallback; otherwise newest valid v5/v4/v3/original scope',
            adjudication_required=any(x['version']=='v6' or not x['identity_matches'] or x.get('conflict_pixels',0) for x in sources),
            same_acquisition_one_sample=True))
    atomic(HERE/'reports/precedence.json',precedence)
    return records

def run():
    existing=HERE/'queue/queue.json'
    if existing.exists():
        print('Frozen queue exists; unchanged:',len(read(existing)['acquisitions']));return
    old=read(V6/'inventory.json');scans=old['scans'];raw=ROOT.parent/'OCTA_RawData'
    disk=sorted(raw.rglob('*_processedVolumes.mat'))
    print('Fresh disk inventory:',len(disk),'processed files',flush=True)
    # Sample every source, including different names, to detect possible duplicates.
    fps={str(p.resolve()).lower():fingerprint(p,True) for p in disk}
    prior_alias=read(V6/'verification/duplicate_files.json')
    aliases={x['duplicate']['path'].lower():x for x in prior_alias};known={r['source'].lower() for r in scans}
    discoveries=[fp for key,fp in fps.items() if key not in known and key not in aliases]
    excluded=[];eligible=[];refreshed=[];sample_groups=defaultdict(list)
    for key,fp in fps.items():sample_groups[(fp['bytes'],fp['sha256'])].append(key)
    duplicate_groups=[]
    for group in sample_groups.values():
        if len(group)<2:continue
        full=[]
        for key in group:
            saved=next((x[t] for x in prior_alias for t in ('duplicate','canonical') if x[t]['path'].lower()==key),None)
            st=Path(fps[key]['path']).stat()
            if saved and saved['mtime_ns']==st.st_mtime_ns and saved['bytes']==st.st_size:
                full.append(dict(saved,verification='prior full SHA256; current size/mtime and fresh sampled digest checked'))
            else:full.append(fingerprint(fps[key]['path']))
        duplicate_groups.append(full)
    for r0 in scans:
        r=dict(r0);key=r['source'].lower();sid=r['scan_id'];meta_path=V6/'inputs'/(sid+'.json')
        day,basis=day_value(r);r.update(eligibility_day=day,eligibility_day_basis=basis,native_shape=[512,512])
        reason=''
        if key not in fps:reason='processed source missing; recover provider/source'
        elif not meta_path.exists():reason='native provider missing; prepare validated optical/native cache'
        else:
            meta=read(meta_path);fp=fps[key]
            if fp['sha256']!=meta['source']['sha256'] or fp['bytes']!=meta['source']['bytes']:reason='source changed since validated provider'
            else:
                vp=Path(r['upstream_volume']);image_path=Path(meta.get('images',{}).get('path',vp/'images.npy'))
                r.update(source_fingerprint=fp,source_identity=digest([fp['bytes'],fp['sha256']]),input_manifest=fingerprint(meta_path),
                    image_provider='recover native processed structural volume' if meta.get('new_acquisition_upstream') else str(image_path))
                if not Path(meta['optical_cache']['path']).exists() or not Path(meta['geometry']['path']).exists():reason='optical/geometry provider missing'
                elif not meta.get('new_acquisition_upstream') and not image_path.exists():reason='native images missing'
        if not reason:
            if r['animal']=='TS165':reason='WT excluded'
            elif day is None:reason=basis
            elif day<=7:reason='not strictly after day 7'
        r['eligibility_status']='excluded' if reason else 'eligible';r['eligibility_reason']=reason
        refreshed.append(r)
        (excluded if reason else eligible).append(r)
    # Collapse any content duplicates beyond the eight known path aliases.
    unique={}
    for r in eligible:
        if r['source_identity'] in unique:
            excluded.append(dict(r,eligibility_reason='duplicate sampled identity; full-hash group retained for adjudication'))
        else:unique[r['source_identity']]=r
    eligible=list(unique.values())
    history=historical_inventory(refreshed)
    for r in eligible:
        r['historical_evidence']=[dict(version=h['version'],source=h['source'],scope=h['scope'],identity_matches=h['identity_matches']) for h in history if h['scan_id']==r['scan_id']]
    queue,info=ordered_queue(eligible)
    config=dict(schema='cnv-queue-v7.1',version='20260918-1',seed=SEED,strict_day_threshold=7,
        positive_image_target=30,selection_independent_of_predictions_and_labels=True,created=now(),**info)
    atomic(HERE/'queue/config.json',config)
    atomic(HERE/'queue/inventory.json',dict(scans=refreshed,excluded=excluded,unmapped_discoveries=discoveries,
        indexed_unprocessed=old['unavailable'],disk_sources=list(fps.values()),duplicate_groups=duplicate_groups,
        inventory_source=fingerprint(V6/'inventory.json'),scan_index=fingerprint(ROOT/'outputs/scan_index.csv')))
    atomic(existing,dict(config=config,acquisitions=queue))
    p=destination(HERE/'queue/queue.csv')
    keys=['queue_position','animal','eye','session_date','day_label','eligibility_day','eligibility_day_basis','scan_no','acq_time','scan_id','source_identity','source','metadata_note','ordering_rationale']
    with p.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,keys,extrasaction='ignore');writer.writeheader();writer.writerows(queue)
    lines=['# Inventory and queue','',f'Fresh disk scan: {len(disk)} processed files; {len(scans)} known distinct acquisitions; {len(set(r["animal"] for r in scans))} animals total.',
        f'{len(queue)} eligible acquisitions across {len(info["animals"])} non-WT animals. TS165 is WT and excluded. Strictly after day 7; D7 excluded.',
        f'Unmapped discoveries: {len(discoveries)}. Indexed unavailable processed acquisitions: {len(old["unavailable"])}.',
        '','Queue membership means eligible for inspection, never known CNV-positive. Full reserve persists beyond the first 30 candidates.',
        'Fresh sampled source fingerprints cover every disk file. Potential duplicates are grouped across names; known duplicate groups retain earlier full-file hashes with current size/mtime checks. This is not a fresh full-volume hash audit.',
        '',f'Seed {SEED}. Numeric animal cycles; each animal cycles seeded visit order before repeating visits; shuffled acquisitions within visits. Selection uses neither labels nor model scores.',
        '','| Animal | Candidates | Visits |','|---|---:|---:|']
    for a in info['animals']:lines.append(f'| {a} | {sum(r["animal"]==a for r in queue)} | {info["visit_counts"][a]} |')
    lines+=['','One-visit animals have acquisition diversity only. Repeats are not independent animals/lesions. Pool exhaustion is recorded in config.json.',
        'TS336 July 28 retains indexed D56 identity although its folder says D77. Both are nominal post-D7 labels; actual interval is unknown. The discrepancy remains in every applicable queue record.',
        'D92 is parsed if numeric day is missing; 6 mo means nominal 180 days solely for eligibility, not a recovered laser date.',
        'An active queue is never regenerated automatically. New discoveries require an explicit new queue version; restarting prepare_queue.py preserves this one.']
    destination(HERE/'reports/INVENTORY.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(dict(candidates=len(queue),**info),indent=2))

if __name__=='__main__':run()
