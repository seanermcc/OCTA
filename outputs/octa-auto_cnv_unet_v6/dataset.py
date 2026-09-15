"""Freeze audited supervision and recover automatic inputs without GUI loaders."""
from common import *
from scipy import ndimage as ndi

def split(visit):
    day=visit['day_label']
    if day in ['D0','D7','D14','D28','D35','D42']: return 'train'
    if day=='D49': return 'validation'
    if day in ['D56','D98']: return 'holdout'
    raise ValueError('Unplanned visit needs an explicit partition: '+day)

def export_target(record, visit):
    shape=(512,512); positive=np.zeros(shape,bool); ignored=np.zeros(shape,bool)
    instances=[]; audit=[]; issues=[]; normal=np.zeros(shape,bool)
    if record is None:
        return dict(target=positive,known=positive.copy(),instances=np.zeros((0,*shape),bool)), dict(complete=False,issues=['No v5 review: no labels'],regions=[],positive_pixels=0,negative_pixels=0,ignored_pixels=512*512)
    if record['scan_id']!=visit['scan_id'] or Path(record['source_volume']).resolve()!=Path(visit['source']).resolve(): raise ValueError('Annotation identity mismatch')
    if record['native_shape']!=list(shape) or record['axis_order']!='B-scan,A-line': raise ValueError('Annotation grid mismatch')
    seen=set(); kept=0; unsure_ids=[]
    for r in record['regions']:
        if r['id'] in seen: raise ValueError('Duplicate region id')
        seen.add(r['id']); mask=decode(r['runs']); reviewed=decode(r.get('reviewed_runs',[]))
        for key in ('edited_runs','core_runs','core_edited_runs','unreviewed_runs'):
            decode(r.get(key,[]))
        reasons=[]; decision=r.get('decision'); cat=r.get('category')
        approved=decision=='approved' and bool(r.get('classification_complete'))
        events=[e for e in r.get('events',[]) if e.get('action')=='explicit CNV review']
        if approved and (not events or events[-1].get('category')!=cat): reasons.append('Missing or conflicting explicit classification event')
        if approved and not np.array_equal(mask,reviewed): reasons.append('Reviewed runs differ from footprint')
        if r.get('bscan_indices')!=np.flatnonzero(mask.any(1)).tolist(): reasons.append('B-scan index metadata inconsistent')
        if approved and not mask.any(): reasons.append('Empty approved footprint')
        if reasons:
            ignored |= mask | reviewed; issues.extend(r['id']+': '+x for x in reasons)
        elif approved and cat=='Full Lesion':
            kept+=1; instances.append(mask); positive |= mask
        elif approved and cat=='Normal': normal |= mask
        elif decision!='rejected':
            ignored |= mask | reviewed
            if approved and cat=='Other': unsure_ids.append(r['id'])
        # Removed proposals generate no labels; only complete-field coverage can supply background.
        audit.append(dict(id=r['id'],category=cat,decision=decision,approved=approved and not reasons,
                          pixels=int(mask.sum()),origin=r.get('origin'),seed_ids=r.get('seed_ids'),
                          reviewed_runs_equal=np.array_equal(mask,reviewed),issues=reasons,
                          connected_components=int(ndi.label(mask)[1]),events=r.get('events',[])))
    stack=np.stack(instances) if instances else np.zeros((0,*shape),bool)
    conflict=(stack.sum(0)>1) | (positive & (ignored|normal))
    if conflict.any():
        issues.append(f'Conflicting positive pixels ignored: {int(conflict.sum())}'); ignored |= conflict
    for key in ('excluded_runs','region_excluded_runs','ignore_runs'):
        if key in record: ignored |= decode(record[key])
    review=record.get('scan_review',{})
    complete=review.get('status')=='complete' and review.get('whole_field_checked') is True
    if complete and (review.get('confirmed_cnv_count')!=kept or set(review.get('uncertainty_region_ids',[]))!=set(unsure_ids) or bool(review.get('reviewed_absence')) != (kept==0 and not unsure_ids)):
        issues.append('Inconsistent completion metadata: background excluded'); complete=False
    positive &= ~ignored
    known=(np.ones(shape,bool) if complete else positive.copy()) & ~ignored
    stack &= known[None]
    return dict(target=positive,known=known,instances=stack),dict(complete=complete,scan_review=review,
        review_context=record.get('review_context',{}),issues=issues,regions=audit,
        positive_pixels=int(positive.sum()),negative_pixels=int((known&~positive).sum()),ignored_pixels=int((~known).sum()))

def automatic_thickness(rows, probabilities, geometry, calibration, depth):
    """Same available-position pilot policy, with human and contextual branches removed."""
    offset=int(geometry['label_offset']); valid=np.isfinite(rows)&(rows>=offset)&(rows<offset+depth)
    denied=np.zeros_like(valid)
    for a in range(8):
        for b in range(a+1,8):
            cross=np.isfinite(rows[:,a])&np.isfinite(rows[:,b])&(rows[:,a]>=rows[:,b])
            valid[:,a]&=~cross;valid[:,b]&=~cross
        c=calibration[a]
        if c['supported']: denied[:,a]=probabilities[:,a,0]<=c['not_traceable_cutoff']
    end=np.where(valid&~denied,rows-offset,np.nan)
    values=[];causes=[]
    for _,a,b in LAYERS:
        delta=(end[:,b]-end[:,a])*1.12
        reason=(denied[:,a]|denied[:,b]).astype('uint8')
        reason |= ((~valid[:,a]|~valid[:,b]).astype('uint8')*2)
        reason |= geometry['shadow'].astype('uint8')*4
        values.append(np.where((reason==0)&(delta>0),delta,np.nan))
        causes.append(reason)
    return np.stack(values).astype('float32'),np.stack(causes),end.astype('float32')

def freeze():
    out=HERE/'data'
    if (out/'manifest.json').exists():
        m=read(out/'manifest.json')
        for r in m['scans']:
            for fp in r['fingerprints']: verify(fp)
            verify(r['dataset'])
        progress('Frozen dataset verified',scans=len(m['scans'])); return m
    visits=[v for v in read(LONG/'manifest.json')['visits'] if v['animal']=='TS267']
    latest=list((V5/'review/regions').glob('*_regions.json'))
    selected_ids={v['scan_id'] for v in visits}
    extras=[p for p in latest if read(p)['scan_id'] not in selected_ids]
    if extras: raise ValueError('New v5 acquisitions found: refresh selected input inventory before fitting '+str(extras))
    annotation_before={str(p):sha(p) for p in latest}
    calpath=ROOT/'outputs/octa-seg/octa-seg_v1/calibration/deployment_vessels.json'
    cal=read(calpath)['thresholds']
    upstream=read(ROOT/'outputs/octa-seg/octa-seg_v1/data/manifest.json')
    records=[]
    for visit in visits:
        sid=visit['scan_id']; progress('Auditing and freezing native inputs',scan=sid)
        vp=volume_path(sid); g=npz(vp/'geometry.npz'); d=npz(vp/'measurements.npz'); base=npz(vp/'v1_matched_baseline.npz')
        neural=read(vp/'neural_complete.json'); prep=read(vp/'prepared.json')
        images=np.load(vp/'images.npy',mmap_mode='r'); lo,hi=map(int,g['retina_band']); offset=int(g['label_offset'])
        assert images.shape==(512,hi-lo,512) and tuple(g['native_shape'])==(512,512,1024)
        assert offset==(1024-hi if bool(g['vitreous_high']) else lo)
        assert neural['orientation_detected']==bool(g['vitreous_high']) and neural['label_offset']==offset
        assert list(d['surface_names'])==SURFACES and neural['scan_id']==sid
        assert Path(neural['source']['path']).resolve()==Path(visit['source']).resolve()
        verify(neural['source'])
        for name in ('position_checkpoint','state_checkpoint'): verify(neural[name])
        assert np.array_equal(base['raw_position_branch'],d['raw_position_branch'],equal_nan=True)
        assert np.array_equal(base['probabilities'],d['probabilities'],equal_nan=True)
        vessel_fp=prep['footprints']; vessel_path=Path(vessel_fp['path']); vessel=npz(vessel_path)
        assert vessel_fp['status'].startswith('automatic vessel proposal')
        assert sha(vessel_path)==vessel_fp['sha256'] and not bool(np.asarray(vessel['human_reviewed']).reshape(-1)[0])
        assert np.array_equal(vessel['predicted_vasculature_mask'],g['vessel'])
        assert not g['onh'].any(), 'Human ONH could affect automatic vessel proposal; regenerate first'
        # Verify saved raw output against neural files, not merely the operational export.
        neural_files=sorted((vp/'neural').glob('*.npz'))
        assert len(neural_files)==512
        neural_hash=hashlib.sha256()
        for b,p in enumerate(neural_files):
            a=npz(p)
            assert np.array_equal(a['rows'],base['raw_position_branch'][b],equal_nan=True)
            assert np.array_equal(a['probabilities'],base['probabilities'][b],equal_nan=True)
            neural_hash.update(sha(p).encode())
        thick,reasons,endpoints=automatic_thickness(base['raw_position_branch'],base['probabilities'],g,cal,images.shape[1])
        assert np.isnan(thick[:,g['shadow']]).all()
        enface=np.mean(images,axis=1,dtype=np.float32)
        octapath=V5/'octa_cache'/f'{sid}.npz'; oa=npz(octapath); om=read_json_scalar(oa['metadata_json']); key=read_json_scalar(oa['key_json'])
        source=Path(visit['source']); st=source.stat()
        assert Path(key['source']).resolve()==source.resolve() and key['bytes']==st.st_size and key['mtime_ns']==st.st_mtime_ns
        assert key['geometry_sha256']==sha(vp/'geometry.npz') and key['depth_crop']==[lo,hi]
        assert key['channel']=='frame_OCTAAvg' and key['axis_order']=='B-scan,A-line' and om['scan_id']==sid
        assert om['orientation_detected']==bool(g['vitreous_high'])
        # Header-level grid identity; fresh detected orientation is preserved by the hashed OCTA cache provenance.
        import h5py
        with h5py.File(source,'r') as h:
            assert h['frame_OCTAAvg'].shape==h['frame_3DAvg'].shape==tuple(g['native_shape'])
        assert oa['octa'].shape==enface.shape==(512,512) and np.isfinite(oa['octa']).all() and np.isfinite(enface).all()
        rp=V5/'review/regions'/f'{sid}_regions.json'; record=read(rp) if rp.exists() else None
        targets,audit=export_target(record,visit)
        save(out/f'{sid}.npz',optical=np.stack([enface,oa['octa']]),thickness_um=thick,
             availability=np.isfinite(thick),shadow=g['shadow'],reason_bits=reasons,
             endpoints_crop_px=endpoints,vessel=g['vessel'],low_signal=g.get('low_signal',np.zeros((512,512),bool)),**targets)
        original_heuristic=V3/'proposals'/f'{sid}.npz'
        fps=[fingerprint(p) for p in [vp/'geometry.npz',vp/'measurements.npz',vp/'v1_matched_baseline.npz',vp/'neural_complete.json',vp/'prepared.json',vp/'human_overrides_provenance.json',vp/'human_guard_provenance.json',octapath,vessel_path,original_heuristic,calpath]]
        fps.extend([fingerprint(vp/'images.npy'),neural['source'],neural['position_checkpoint'],neural['state_checkpoint']])
        if rp.exists(): fps.append(fingerprint(rp))
        cfg=read(LONG/'v2/launch_config.json')
        external=[]
        for folder in [V5/'review/surface_labels',ROOT/'outputs/octa-auto_cnv_v4/review/surface_labels',V3/'review/surface_labels',Path(cfg['output'])/'surface_labels',*map(Path,cfg['manual_sources'])]:
            external.extend(fingerprint(p) for p in folder.glob(f'{sid}_b*.npz'))
        records.append(dict(**visit,split=split(visit),audit=audit,annotation_source=str(rp) if rp.exists() else None,
            fingerprints=fps,dataset=fingerprint(out/f'{sid}.npz'),optical_provenance=om,
            neural_files_combined_sha256=neural_hash.hexdigest(),
            frozen_human_overrides=read(vp/'human_overrides_provenance.json'),
            frozen_human_guards=read(vp/'human_guard_provenance.json'),external_corrections_excluded=external,
            human_state_pixels_excluded_from_inputs=int(np.isin(d['reason'],[5,6,7,8,11,15]).sum()),
            vessel_provenance=vessel_fp,available_fraction_by_layer=np.isfinite(thick).mean((1,2)).tolist(),
            geometry_cnvs_present_but_not_used=bool(g['cnv'].any())))
    assert annotation_before=={p:sha(p) for p in annotation_before}
    m=dict(version='octa-auto_cnv_unet_v6',scans=records,annotation_hashes=annotation_before,
        target_policy='Explicit reviewed positives; completed-field background; unsure/drafts/conflicts excluded; rejected entries never independently negative',
        thickness_policy='Frozen raw neural positions; automatic supported trace denial, all-pair crossing/out-of-crop and automatic shadow guards. No contextual estimates, human strokes, human exclusions or reliability marks.',
        thickness_policy_limitation='Available does not mean validated reliable. Learned reliability threshold is not used by the established available-position pilot policy.',
        layers=[dict(name=n,top=SURFACES[a],bottom=SURFACES[b]) for n,a,b in LAYERS],
        reason_bits={1:'automatic supported not-traceable decision',2:'nonfinite/outside crop/crossing endpoint',4:'automatic shadow'},
        upstream_animals=sorted({r['animal'] for r in upstream['records']}),
        upstream_TS267_records=sum(r['animal']=='TS267' for r in upstream['records']),
        independence='Within TS267 visits only; repeated lesions and upstream ALL_LABELLED exposure; no new-animal generalization claim',
        paired_experiment_interpretation='B vs A adds availability AND shadow together; C vs B adds observed numerical thickness',
        source_integrity='Full hashes of derived inputs and models; processed MAT source verified with explicitly identified three-1MiB sampled hash',
        annotation_unchanged=True)
    train=[npz(out/f"{r['scan_id']}.npz") for r in records if r['split']=='train' and r['audit']['positive_pixels']+r['audit']['negative_pixels']>0]
    stats={}
    for name in ('optical','thickness_um'):
        centers=[]; scales=[]
        for k in range(2 if name=='optical' else 8):
            a=np.concatenate([d[name][k].ravel() for d in train]);a=a[np.isfinite(a)]
            if not len(a): centers.append(0.);scales.append(1.)
            else:
                q=np.percentile(a,[25,50,75]); centers.append(float(q[1]));scales.append(float(max((q[2]-q[0])/1.349,1e-3)))
        stats[name]=dict(center=centers,scale=scales)
    write(out/'normalization.json',stats); m['normalization']=fingerprint(out/'normalization.json')
    write(out/'manifest.json',m)
    csv_write(out/'annotation_audit.csv',[dict(scan_id=r['scan_id'],split=r['split'],complete=r['audit']['complete'],positive_pixels=r['audit']['positive_pixels'],negative_pixels=r['audit']['negative_pixels'],ignored_pixels=r['audit']['ignored_pixels'],issues='; '.join(r['audit']['issues'])) for r in records])
    progress('Dataset frozen',scans=len(records),labeled_scans=sum(r['audit']['positive_pixels']+r['audit']['negative_pixels']>0 for r in records))
    return m

def read_json_scalar(a): return json.loads(str(a))

def tensor_inputs(d,stats,experiment):
    optical=(d['optical']-np.array(stats['optical']['center'])[:,None,None])/np.array(stats['optical']['scale'])[:,None,None]
    parts=[np.clip(optical,-8,8)]
    if experiment in ('B','C'): parts += [d['availability'].astype('float32'),d['shadow'][None].astype('float32')]
    if experiment=='C':
        t=(d['thickness_um']-np.array(stats['thickness_um']['center'])[:,None,None])/np.array(stats['thickness_um']['scale'])[:,None,None]
        parts += [np.where(d['availability'],np.clip(t,-8,8),0)]
    a=np.concatenate(parts).astype('float32'); assert np.isfinite(a).all();return a

if __name__=='__main__': freeze()
