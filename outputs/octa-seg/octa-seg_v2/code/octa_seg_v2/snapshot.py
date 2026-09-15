"""Read-only feedback importer; immutable derived targets, never human labels."""
from .common import *
from .feedback import training_targets
from .policy import geometry_valid
from eight_surface.labels import load_label
from eight_surface import provenance as P

def freeze(name):
    dest=OUT/'datasets'/name
    if (dest/'manifest.json').exists():
        m=read(dest/'manifest.json')
        for r in m['records']:verify(r['targets'])
        return dest
    queue=read(ROUND/'review_queue.json')['examples'] if (ROUND/'review_queue.json').exists() else []
    assessment={(q['scan_id'],q['bscan']) for q in queue if q['data_role']=='assessment'}
    records=[]
    for path in sorted((OUT/'reviewer/regional_feedback').glob('*.json')):
        d=read(path)
        if d.get('format')!='octa-seg-v2-regional-1':raise ValueError('Unknown feedback format')
        sid=d['scan_id'];b=int(d['bscan'])
        if sid not in SCANS:raise ValueError('Feedback scan outside frozen cohort')
        t=training_targets(d['events'][:d['cursor']],model_id=d['model_id'])
        g=npz(ROUND/'volumes'/sid/'geometry.npz');valid=geometry_valid(t['rows'],int(g['label_offset']),int(np.diff(g['retina_band'])[0]))
        t['manual_valid']&=valid;t['approved_valid']&=valid
        role='assessment' if (sid,b) in assessment or d['data_role']=='assessment' else 'training'
        target=dest/'targets'/f'{sid}_b{b:04d}.npz';save(target,**t)
        records.append(dict(key=f'{sid}_b{b:04d}',scan_id=sid,bscan=b,animal=sid.split('_')[0],role=role,
            source=fingerprint(path),targets=fingerprint(target),events=d['events'][:d['cursor']],review_seconds=d['active_seconds'],origin='v2_explicit_events'))
    seen={(r['scan_id'],r['bscan']) for r in records}
    # The v1 journal has exact stroke coordinates, unlike unknown legacy spans.
    for path in sorted((V1/'reviewer/estimate_feedback').glob('*.json')):
        d=read(path);sid=d['scan_id'];b=d['bscan']
        if (sid,b) in seen or sid not in SCANS:continue
        lp=V1/'reviewer/surface_labels'/f'{sid}_b{b:04d}.npz'
        if not lp.exists():continue
        lab=load_label(lp);g=npz(ROUND/'volumes'/sid/'geometry.npz');offset=int(g['label_offset'])
        shape=lab['surfaces'].shape;t=dict(trace_target=np.full(shape,-1,np.int8),reliability_target=np.full(shape,-1,np.int8),rows=np.full(shape,np.nan,np.float32),manual_valid=np.zeros(shape,bool),approved_valid=np.zeros(shape,bool),excluded=lab['region_excluded'])
        trace=P.record_visibility(lab);rel=P.record_reliability(lab)
        for e in d['events']:
            k=list(lab['surface_names']).index(e['boundary']);cc=np.array(e['columns'],int)
            t['approved_valid'][k,cc]=False
            if e['action'] not in ('corrected_pending_approval','approved_for_future_positions'):continue
            yy=np.array(e['positions_crop_px']);same=np.isclose(lab['surfaces'][k,cc],yy,atol=1e-4,rtol=0)
            valid=same&~lab['local_displaced'][k,cc]&~lab['region_excluded'][cc]&(trace[k,cc]!=P.MARK_NO)
            if lab['verdict']=='rejected':valid[:]=False
            cc=cc[valid];yy=yy[valid];t['rows'][k,cc]=yy+offset
            t['manual_valid' if e['action']=='corrected_pending_approval' else 'approved_valid'][k,cc]=True
            t['trace_target'][k,cc]=1
            t['reliability_target'][k,cc]=np.where(rel[k,cc]==P.MARK_YES,1,np.where(rel[k,cc]==P.MARK_NO,0,-1))
        target=dest/'targets'/f'{sid}_b{b:04d}.npz';save(target,**t)
        records.append(dict(key=f'{sid}_b{b:04d}',scan_id=sid,bscan=b,animal=sid.split('_')[0],role='assessment' if (sid,b) in assessment else 'training',
           source=fingerprint(path),label_source=fingerprint(lp),targets=fingerprint(target),events=[],review_seconds=lab.get('seconds_active',0),origin='v1_exact_events_matched_to_current_label'))
    counts=[]
    for r in records:
        t=npz(r['targets']['path']);counts.append(dict(key=r['key'],role=r['role'],manual_columns=int(t['manual_valid'].sum()),approved_columns=int(t['approved_valid'].sum()),
          trace_positive=int((t['trace_target']==1).sum()),trace_negative=int((t['trace_target']==0).sum()),reliable_positive=int((t['reliability_target']==1).sum()),reliable_negative=int((t['reliability_target']==0).sum())))
    seen={(r['scan_id'],r['bscan']) for r in records}
    original=read(V1/'data/manifest.json')
    replay=[r for r in original['records'] if (r['scan_id'],r['bscan']) not in assessment and (r['scan_id'],r['bscan']) not in seen]
    m=dict(name=name,records=records,counts=counts,baseline_replay=[dict(key=r['key'],animal=r['animal'],scan_id=r['scan_id'],bscan=r['bscan'],cache=r['cache']) for r in replay],
       assessment_scope='whole B-scan held out of this round; seen checkpoint ancestry means development assessment, not animal-excluded generalization',
       exclusions=['pilot Good/Bad/Unsure','full-volume praise','unknown legacy stroke spans','tapers','displaced positions','unreviewed candidates','ILM working default'],
       initial_model=initialize()['checkpoints'])
    m['dataset_id']=digest(m);write(dest/'manifest.json',m);write(dest/'COMPLETE.json',dict(dataset_id=m['dataset_id'],manifest=fingerprint(dest/'manifest.json')))
    print('Frozen feedback snapshot',dest,'records',len(records),flush=True);return dest

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('name');freeze(p.parse_args().name)
