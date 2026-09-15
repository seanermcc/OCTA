"""Frozen six-model inference. Every write is confined to all_samples.

Large immutable image/raw-neural arrays are referenced with full hashes instead
of duplicated. Only optical projections, native predictions and audits are new.
"""
from common import *
from dataset import automatic_thickness, tensor_inputs, export_target
from model import UNet, infer
from metrics import PROTOCOL, score, components
from scipy import ndimage as ndi
from collections import Counter
import argparse, traceback, shutil, torch, gc, re

PILOT=HERE.parent
BATCH=ROOT/'outputs/octa-seg_v1_batch'
V1=ROOT/'outputs/octa-seg/octa-seg_v1'
KEYS=[f'{e}_{s}' for e in 'BC' for s in (267,268,269)]

def array_hash(a):
    a=np.ascontiguousarray(a)
    return hashlib.sha256(str((a.shape,a.dtype.str)).encode()+a.tobytes()).hexdigest()

def csvread(p):
    with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def cached_full_fingerprint(p):
    p=Path(p).resolve();key=hashlib.sha256(str(p).encode()).hexdigest();cache=HERE/'verification/source_full_hashes'/f'{key}.json'
    if cache.exists():
        fp=read(cache);st=p.stat()
        if fp['bytes']==st.st_size and fp['mtime_ns']==st.st_mtime_ns:return fp
    progress('Hashing duplicate source content',source=str(p))
    fp=fingerprint(p);write(cache,fp);return fp

def preservation_inventory():
    paths=set(p for p in PILOT.rglob('*') if p.is_file() and not p.is_relative_to(HERE))
    for folder in ROOT.joinpath('outputs').rglob('*'):
        if folder.is_dir() and folder.name in ('cnv_labels','labels','surface_labels','regions') and not folder.is_relative_to(HERE):
            paths.update(p for p in folder.rglob('*') if p.is_file() and p.suffix in ('.json','.npz'))
    return {str(p):sha(p) for p in sorted(paths)}

def initialize():
    import batch_segment
    if (HERE/'inventory.json').exists():return read(HERE/'inventory.json')
    progress('Reconciling disk and acquisition index')
    old=read(BATCH/'manifest.json');oldmap={r['scan_id']:r for r in old['scans']}
    pilot={r['scan_id']:r for r in read(PILOT/'data/manifest.json')['scans']}
    layer=read(V1/'data/manifest.json')['records']
    disk=sorted((ROOT.parent/'OCTA_RawData').rglob('*_processedVolumes.mat'))
    indexed=[];unavailable=[];mapped={}
    index_rows=csvread(ROOT/'outputs/scan_index.csv')
    for r in index_rows:
        sid=batch_segment.scan_id_for(r);source=batch_segment.resolve_volumes_path(r)
        if source is None:
            expected=r['raw_stem'].removesuffix('_OCTA')+'_processedVolumes.mat'
            matches=[p for p in disk if p.name==expected]
            if matches:source=sorted(matches,key=lambda p:(len(str(p)),str(p)))[0]
        if source is None:
            unavailable.append(dict(r,scan_id=sid,inference_status='excluded',reason='No processed volume; awaiting MATLAB reconstruction' if Path(r['raw_path']).exists() else 'No processed volume; indexed RAW path also absent (deleted or relocated; no reconstruction attempted)'))
            continue
        source=source.resolve();rec=dict(r,scan_id=sid,source=str(source))
        assert str(source).lower() not in mapped,'Duplicate indexed source'
        mapped[str(source).lower()]=rec
    aliases=[]
    prior_alias={a['duplicate']['path'].lower():a for a in read(BATCH/'duplicate_files.json')}
    for p in disk:
        if str(p.resolve()).lower() in mapped:continue
        candidates=[r for r in mapped.values() if Path(r['source']).name==p.name]
        if not candidates:
            identity=re.match(r'TS?(\d+)([MF]?)-([RL])0*(\d+)_(\d\d)_(\d\d)_(\d\d)_',p.name)
            session=p.relative_to(ROOT.parent/'OCTA_RawData').parts[0]
            date=re.match(r'(\d\d)\.(\d\d)\.(\d\d)',session);day=re.search(r'\b(D\d+)\b',session,re.I)
            if not identity or not date:raise ValueError('Unindexed identity cannot be parsed: '+str(p))
            animal,sex,eye,num,hh,mm,ss=identity.groups();yyyy,month,dd=date.groups()
            r=dict(animal='TS'+animal,sex=sex,eye='OD' if eye=='R' else 'OS',scan_no=str(int(num)),acq_time=f'{hh}:{mm}:{ss}',
                session_date=f'20{yyyy}-{month}-{dd}',day_label=day[1].upper() if day else 'unknown',days_post_laser='',
                session_folder=session,source=str(p),raw_stem=p.name.removesuffix('_processedVolumes.mat')+'_OCTA',raw_path='',
                index_origin='new acquisition discovered on disk; identity parsed from source filename and dated session folder',metadata_verification='filename/session-derived; actual laser interval unknown')
            r['scan_id']=batch_segment.scan_id_for(r);mapped[str(p.resolve()).lower()]=r;continue
        if len(candidates)!=1:raise ValueError('Ambiguous source version identity: '+str(p))
        r=candidates[0];a=cached_full_fingerprint(p);b=cached_full_fingerprint(r['source'])
        if a['sha256']==b['sha256']:aliases.append(dict(scan_id=r['scan_id'],duplicate=a,canonical=b,reason='Full SHA-256 identical file copy, not a repeat acquisition'))
        else:
            rec=dict(r,scan_id=r['scan_id']+'_source_'+a['sha256'][:8],source=str(p),source_variant_of=r['scan_id'])
            mapped[str(p.resolve()).lower()]=rec
    for r in mapped.values():
        sid=r['scan_id'];pr=pilot.get(sid)
        vp=Path(pr['fingerprints'][0]['path']).parent if pr else BATCH/'volumes'/sid
        if not (vp/'prepared.json').exists():vp=HERE/'upstream_automatic'/sid
        r.update(upstream_volume=str(vp),original_pilot=bool(pr),pilot_split=pr['split'] if pr else 'new_acquisition',
            cnv_animal_exposure='training animal TS267' if r['animal']=='TS267' else 'not in CNV training',
            cnv_scan_exposure=pr['split'] if pr else 'not in original CNV pilot',
            upstream_animal_exposure='ALL_LABELLED training animal' if any(x['animal']==r['animal'] for x in layer) else 'unknown',
            upstream_scan_exposure='contains upstream training B-scans' if any(x['scan_id']==sid for x in layer) else 'not listed in upstream training manifest',
            inference_status='pending',reason='',review_status='human evaluation pending',
            day_basis='actual days_post_laser' if r.get('days_post_laser') else 'nominal day_label; actual unavailable')
        indexed.append(r)
    indexed.sort(key=lambda r:(not r['original_pilot'],r['scan_id']))
    models=[];art={x['path'].lower():x for x in read(PILOT/'artifact_manifest.json')}
    for key in KEYS:
        ex,seed=key.split('_');seed=int(seed);p=PILOT/f'experiment_{ex}'
        if seed!=267:p=p/f'seed_{seed}'
        for f in (p/'best.pt',p/'config.json',p/'threshold.json',PILOT/'data/normalization.json'):
            assert sha(f)==art[str(f).lower()]['sha256'],str(f)+' differs from sealed pilot'
        ck=torch.load(p/'best.pt',map_location='cpu',weights_only=False);cfg=ck['config']
        assert cfg==read(p/'config.json') and cfg['seed']==seed and cfg['experiment']==ex
        assert cfg['normalization_sha256']==sha(PILOT/'data/normalization.json')
        assert cfg['manifest_sha256']==sha(PILOT/'data/manifest.json')
        assert cfg['model_code_sha256']==sha(HERE/'model.py')
        models.append(dict(key=key,experiment=ex,seed=seed,checkpoint=fingerprint(p/'best.pt'),config=cfg,
            threshold=read(p/'threshold.json')['selected']['threshold'],threshold_record=fingerprint(p/'threshold.json'),
            normalization=fingerprint(PILOT/'data/normalization.json'),channels=['structural OCT','actual OCTA']+[f'availability: {x[0]}' for x in LAYERS]+['automatic shadow']+([f'thickness um: {x[0]}' for x in LAYERS] if ex=='C' else [])))
    for fp in old['checkpoints']+[old['calibration']]:verify(fp)
    write(HERE/'models.json',models)
    write(HERE/'verification/protocol.json',PROTOCOL)
    write(HERE/'verification/duplicate_files.json',aliases)
    write(HERE/'verification/preservation_before.json',preservation_inventory())
    m=dict(scans=indexed,unavailable=unavailable,index=fingerprint(ROOT/'outputs/scan_index.csv'),
        reconciliation=dict(index_rows=len(index_rows),disk_processed_files=len(disk),eligible_inputs=len(indexed),distinct_acquisitions=len({r.get('source_variant_of',r['scan_id']) for r in indexed}),source_variants=sum('source_variant_of' in r for r in indexed),duplicate_files=len(aliases),unprocessed_acquisitions=len(unavailable)),
        upstream=old['checkpoints'],calibration=old['calibration'],upstream_final_audit=fingerprint(BATCH/'FINAL_VERIFIED.json'))
    write(HERE/'inventory.json',m);csv_write(HERE/'unprocessed_acquisitions.csv',unavailable);status(m)
    return m

def status(m):
    rows=[]
    for r in m['scans']:
        p=HERE/'records'/f"{r['scan_id']}.json"
        rec=read(p) if p.exists() else {}
        rows.append({k:v for k,v in dict(r,inference_status=rec.get('status','pending'),reason=rec.get('reason','')).items() if not isinstance(v,(dict,list))})
    csv_write(HERE/'scan_status.csv',rows+m['unavailable'])
    counts=Counter(r['inference_status'] for r in rows)
    write(HERE/'status.json',dict(counts=counts,eligible=len(rows),unprocessed=len(m['unavailable']),updated=time.strftime('%Y-%m-%dT%H:%M:%S'),human_evaluation='pending'))
    return counts

def annotations(r):
    sid=r['scan_id'];sources=[];issues=[]
    for folder in (ROOT/'outputs/octa-auto_cnv_v5/review/regions',ROOT/'outputs/octa-auto_cnv_v4/review/regions',ROOT/'outputs/octa-auto_cnv_v3/review/regions'):
        path=folder/f'{sid}_regions.json'
        if path.exists():
            sources.append(fingerprint(path))
            try:
                targets,audit=export_target(read(path),r)
                return targets,dict(audit,sources=sources,annotation_kind='audited explicit region decisions',instance_definition='saved individual lesion entries')
            except (ValueError,KeyError,AssertionError) as e:
                issues.append('Invalid region annotation: '+str(e));break
    targets,audit=export_target(None,r)
    p=ROOT/'outputs/cnv_labels'/f'{sid}_cnv.npz'
    if p.exists() and not sources:
        from eight_surface.cnv_labels import load_label
        a=load_label(p);sources.append(fingerprint(p))
        if a['scan_id']!=sid or Path(a['source_volume']).resolve()!=Path(r['source']).resolve() or a['native_shape']!=(512,512):
            issues.append('Legacy annotation source/grid mismatch; reference excluded')
        elif bool(a['reviewed_targets'][0]):
            target=a['cnv_mask'].copy();ignored=np.zeros_like(target)
            regionpath=ROOT/'outputs/cnv_review_v1/regions'/f'{sid}_regions.json'
            if regionpath.exists():
                rr=read(regionpath);sources.append(fingerprint(regionpath))
                if rr['scan_id']==sid and Path(rr['source_volume']).resolve()==Path(r['source']).resolve():
                    for region in rr['regions']:
                        mask=decode(region['runs']);cat=region['category']
                        if region.get('classification_complete') and cat=='Full Lesion':target|=mask
                        elif region.get('classification_complete') and cat=='Normal':target&=~mask
                        else:ignored|=mask
            target&=~ignored;_,inst=components(target)
            # Legacy 'reviewed' does not establish v5 whole-field completion.
            targets=dict(target=target,known=target.copy(),instances=np.stack(inst) if inst else np.zeros((0,512,512),bool))
            audit=dict(complete=False,positive_pixels=int(target.sum()),negative_pixels=0,ignored_pixels=int((~target).sum()),
                issues=['Legacy positive-only comparison: whole-field completion and original instance identity unavailable'],regions=[],
                annotation_kind='reviewed legacy en-face positives',instance_definition='connected footprint components, not original saved instances')
    audit.update(sources=sources,issues=audit.get('issues',[])+issues)
    if not sources:audit['annotation_kind']='no saved annotations'
    elif 'annotation_kind' not in audit:audit['annotation_kind']='unreviewed or invalid reference; excluded'
    return targets,audit

def raw_arrays(vp):
    with np.load(vp/'measurements.npz',allow_pickle=False) as a:
        return a['raw_position_branch'],a['probabilities']

def new_upstream(r):
    """Same frozen v1 preparation/inference for newly reconstructed acquisitions.

    Native B-scans are recovered on demand, avoiding a redundant 0.5-GB crop
    per acquisition on the nearly full source drive.
    """
    from octa.volio import ProcessedVolume,find_retina_band
    from octa.segment import detect_orientation
    from eight_surface.segment import prepare_bscan
    from eight_surface.cnv_data import _mean_db_dataset
    from quality_pilot.prepare import shadow_only
    from vasculature_baseline import vessel_evidence,make_mask
    from vasculature_shape_gate import shape_gate,PARAMETERS
    sid=r['scan_id'];vp=Path(r['upstream_volume']);mp=HERE/'inputs'/f'{sid}.json'
    progress('Preparing newly processed acquisition with frozen upstream models',scan=sid)
    with ProcessedVolume(r['source']) as volume:
        if volume.angio is None:raise ValueError('Required frame_OCTAAvg channel absent')
        assert volume.struct.shape==volume.angio.shape==(512,512,1024)
        full=volume.read_volume();profile=full.mean((0,1));high=bool(detect_orientation(profile))
        if (vp/'geometry.npz').exists():g=npz(vp/'geometry.npz');lo,hi=map(int,g['retina_band']);assert high==bool(g['vitreous_high'])
        else:lo,hi=map(int,find_retina_band(profile)[:2])
        offset=1024-hi if high else lo
        images=np.stack([prepare_bscan(full[b],high)[offset:offset+hi-lo] for b in range(512)])
        if mp.exists():
            meta=read(mp);verify(meta['source']);verify(meta['geometry']);verify(meta['regenerated_neural']);verify(meta['optical_cache'])
            assert array_hash(images)==meta['images_array_sha256']
            optical=npz(meta['optical_cache']['path'])['optical']
            a=npz(meta['regenerated_neural']['path']);rows=a['rows'];prob=a['probabilities']
        else:
            optical=np.stack([images.mean(1,dtype=np.float32),_mean_db_dataset(volume.angio,slice(lo,hi))])
            shadow=np.stack([shadow_only(images[max(0,b-1):min(512,b+2)].mean(0)) for b in range(512)])
            evidence,_,_=vessel_evidence(optical[0]);vessel,vaudit=shape_gate(make_mask(evidence,.18,np.zeros((512,512),bool)),**PARAMETERS)
            # Independent raw acquisition signal policy used by the frozen batch.
            import scan_quality as sq
            class MemoryVolume:
                shape=full.shape
                def read_volume(self,depth_slice=slice(None)):return full[:,:,depth_slice]
            noise,side=sq._read_noise(MemoryVolume(),lo,hi)
            cnr=((np.percentile(full[:,:,lo:hi],75,axis=2)-np.median(noise,axis=2))/max(float(sq._mad(noise.ravel())),1e-6)).astype('float32')
            g=dict(shadow=shadow,vessel=vessel,low_signal=cnr<3,local_cnr=cnr,retina_band=np.array([lo,hi]),label_offset=np.array(offset),vitreous_high=np.array(high),native_shape=np.array(full.shape))
            from octa_seg_v1.predict import one,state_model
            from octa_seg_v1.train import load_position
            net,_=load_position(V1/'models/ALL_LABELLED/position.pt');states=state_model('ALL_LABELLED')
            values=[]
            for b in range(512):
                values.append(one(net,states,full[b],high,vessel[b])[0])
                if b%128==0:progress('Frozen upstream inference for new acquisition',scan=sid,bscans=b+1)
            rows=np.stack([a['rows'] for a in values]);prob=np.stack([a['probabilities'] for a in values])
            del values,net,states;torch.cuda.empty_cache()
            rp=vp/'raw_neural.npz';save(rp,rows=rows,probabilities=prob,vessel=vessel);save(vp/'geometry.npz',**g)
            cache=HERE/'inputs'/f'{sid}.npz';save(cache,optical=optical)
            meta=dict(scan_id=sid,source=fingerprint(r['source'],sampled=True),native_shape=[512,512,1024],axis_order='B-scan,A-line',retinal_crop_original_depth=[lo,hi],canonical_crop_offset=offset,
                orientation_fresh_detected=high,structural_three_bscan_max_abs_error_db=0.,structural_checked_rows=[64,256,448],
                octa_channel='frame_OCTAAvg',octa_projection='mean of 20*log10(max(channel,0.001)) across saved retinal crop; not a layer slab',
                optical_cache=fingerprint(cache),upstream_volume=str(vp),geometry=fingerprint(vp/'geometry.npz'),images_array_sha256=array_hash(images),
                images_storage='On-demand native processed-volume prepare_bscan reconstruction; no duplicate crop file',
                regenerated_neural=fingerprint(rp),automatic_only=True,new_acquisition_upstream=True,
                checkpoints=read(HERE/'inventory.json')['upstream'],
                human_input_exclusions=['manual boundaries','human vessel/ONH masks','human guards','contextual estimates','CNV annotations'])
            write(mp,meta)
    del full;gc.collect()
    thick,reasons,endpoints=automatic_thickness(rows,prob,g,read(V1/'calibration/deployment_vessels.json')['thresholds'],hi-lo)
    assert np.isnan(thick[:,g['shadow']]).all()
    return dict(optical=optical,thickness_um=thick,availability=np.isfinite(thick),shadow=g['shadow'],vessel=g['vessel'],low_signal=g['low_signal'],reason_bits=reasons,endpoints_crop_px=endpoints),meta,images

def recover_inputs(r,verify_all=True):
    sid=r['scan_id'];vp=Path(r['upstream_volume'])
    if vp.is_relative_to(HERE):return new_upstream(r)
    p=read(vp/'prepared.json');nm=read(vp/'neural_complete.json');g=npz(vp/'geometry.npz')
    images=np.load(vp/'images.npy',mmap_mode='r');lo,hi=map(int,g['retina_band']);offset=int(g['label_offset'])
    assert tuple(g['native_shape'])==(512,512,1024) and images.shape==(512,hi-lo,512)
    assert offset==(1024-hi if bool(g['vitreous_high']) else lo)
    assert nm['scan_id']==sid and nm['n_bscans']==512 and nm['orientation_detected']==bool(g['vitreous_high'])
    assert Path(nm['source']['path']).resolve()==Path(r['source']).resolve()
    for key,fp in zip(('position_checkpoint','state_checkpoint'),read(HERE/'inventory.json')['upstream']):
        assert nm[key]['sha256']==fp['sha256']
    rows,prob=raw_arrays(vp)
    if verify_all:
        verify(nm['source'])
        if p.get('geometry'):verify(p['geometry'])
        if p.get('images_fingerprint'):verify(p['images_fingerprint'])
        complete=read(vp/'complete.json')
        verify(complete['measurements'])
        digest=hashlib.sha256()
        for b in range(512):
            path=vp/'neural'/f'b{b:04d}.npz';a=npz(path)
            assert np.array_equal(rows[b],a['rows'],equal_nan=True)
            assert np.array_equal(prob[b],a['probabilities'],equal_nan=True)
            digest.update(sha(path).encode())
        neural_digest=digest.hexdigest()
    else:neural_digest=None
    cache=HERE/'inputs'/f'{sid}.npz';meta_path=cache.with_suffix('.json')
    if cache.exists() and meta_path.exists():
        meta=read(meta_path);verify(meta['optical_cache']);a=npz(cache)
        if meta.get('regenerated_neural'):
            verify(meta['regenerated_neural']);reg=npz(meta['regenerated_neural']['path']);rows=reg['rows'];prob=reg['probabilities'];g['vessel']=reg['vessel']
        optical=a['optical']
    else:
        from octa.volio import ProcessedVolume
        from octa.segment import detect_orientation
        from eight_surface.segment import prepare_bscan
        from eight_surface.cnv_data import _mean_db_dataset
        progress('Checking source orientation and projecting actual OCTA',scan=sid)
        inventory=read(HERE/'inventory.json')
        representative=min(x['scan_id'] for x in inventory['scans'] if x['animal']==r['animal'] and not x['original_pilot'])
        vfp=p['footprints'];clean=vfp['status'].startswith('automatic vessel proposal') and not g.get('onh',np.zeros((512,512),bool)).any()
        direct=r['original_pilot'] or sid==representative or not clean
        # Reuse is supported by source fingerprint, full derived hashes, all 512
        # raw neural records, exact checkpoints and the upstream full-grid audit.
        # This is the newly detected neural-completion orientation, never the
        # legacy sample's vitreous_at_high_index flag. Mean OCTA is depth-order invariant.
        if not direct:
            assert p.get('orientation_fresh') is True
            qc=read(vp/'qc_complete.json');assert qc['verified'] and 'fresh orientation and crop offset' in qc['checks']
            assert nm['source']['sha256']==p['source']['sha256']
        full=None;err=None
        with ProcessedVolume(r['source']) as volume:
            if volume.angio is None:raise ValueError('Required frame_OCTAAvg channel absent')
            assert volume.struct.shape==volume.angio.shape==(512,512,1024)
            if direct:
                full=volume.read_volume();high=bool(detect_orientation(full.mean((0,1))))
                check=np.stack([prepare_bscan(full[b],high)[offset:offset+hi-lo] for b in (64,256,448)])
                err=float(np.max(np.abs(check-images[[64,256,448]])));assert err<1e-4
            else:high=bool(nm['orientation_detected'])
            assert high==bool(g['vitreous_high'])
            optical=np.stack([np.mean(images,axis=1,dtype=np.float32),_mean_db_dataset(volume.angio,slice(lo,hi))])
        assert optical.shape==(2,512,512) and np.isfinite(optical).all()
        if clean:
            vessel=npz(vfp['path']);assert sha(vfp['path'])==vfp['sha256']
            assert not bool(np.asarray(vessel['human_reviewed']).reshape(-1)[0])
            assert np.array_equal(vessel['predicted_vasculature_mask'],g['vessel'])
        regen=None
        if not clean:
            progress('Regenerating automatic-only upstream inputs with frozen v1 models',scan=sid)
            from vasculature_baseline import vessel_evidence,make_mask
            from vasculature_shape_gate import shape_gate,PARAMETERS
            from octa_seg_v1.predict import one,state_model
            from octa_seg_v1.train import load_position
            evidence,_,_=vessel_evidence(optical[0]);g['vessel'],vaudit=shape_gate(make_mask(evidence,.18,np.zeros((512,512),bool)),**PARAMETERS)
            net,_=load_position(V1/'models/ALL_LABELLED/position.pt');states=state_model('ALL_LABELLED')
            preds=[one(net,states,full[b],high,g['vessel'][b])[0] for b in range(512)]
            rows=np.stack([x['rows'] for x in preds]);prob=np.stack([x['probabilities'] for x in preds])
            rp=HERE/'upstream_automatic'/f'{sid}.npz';save(rp,rows=rows,probabilities=prob,vessel=g['vessel'])
            regen=fingerprint(rp);del preds,net,states;torch.cuda.empty_cache()
        del full;gc.collect()
        save(cache,optical=optical)
        meta=dict(scan_id=sid,source=nm['source'],native_shape=[512,512,1024],axis_order='B-scan,A-line',retinal_crop_original_depth=[lo,hi],canonical_crop_offset=offset,
            orientation_fresh_detected=high,orientation_evidence='fresh source detect_orientation/prepare_bscan recheck' if direct else 'verified frozen upstream detect_orientation/prepare_bscan export; legacy flags excluded',
            direct_source_rechecked=direct,upstream_grid_audit=fingerprint(vp/'qc_complete.json') if not direct else None,
            structural_three_bscan_max_abs_error_db=err,structural_checked_rows=[64,256,448] if direct else [],
            octa_channel='frame_OCTAAvg',octa_projection='mean of 20*log10(max(channel,0.001)) across saved retinal crop; not a layer slab',
            optical_cache=fingerprint(cache),upstream_volume=str(vp),geometry=fingerprint(vp/'geometry.npz'),images=p['images_fingerprint'] if verify_all else fingerprint(vp/'images.npy'),
            raw_neural_measurements=complete['measurements'] if verify_all else fingerprint(vp/'measurements.npz'),neural_files_combined_sha256=neural_digest,neural_file_count_checked=512,
            original_vessel_provenance=vfp,regenerated_neural=regen,automatic_only=True,
            human_input_exclusions=['manual boundaries','human vessel masks','human ONH masks','human reliability/visibility/exclusion guards','contextual estimates','CNV annotations'],
            checkpoints={k:nm[k] for k in ('position_checkpoint','state_checkpoint')})
        write(meta_path,meta)
    thick,reasons,endpoints=automatic_thickness(rows,prob,g,read(V1/'calibration/deployment_vessels.json')['thresholds'],hi-lo)
    assert np.isnan(thick[:,g['shadow']]).all()
    d=dict(optical=optical,thickness_um=thick,availability=np.isfinite(thick),shadow=g['shadow'],vessel=g['vessel'],low_signal=g.get('low_signal',np.zeros((512,512),bool)),reason_bits=reasons,endpoints_crop_px=endpoints)
    return d,meta,images

def predict_one(r,nets,models,stats):
    sid=r['scan_id'];t=time.monotonic();d,meta,images=recover_inputs(r)
    targets,audit=annotations(r);d.update(targets)
    save(HERE/'references'/f'{sid}.npz',**targets)
    inputs={ex:tensor_inputs(d,stats,ex) for ex in 'BC'}
    input_hashes={k:array_hash(v) for k,v in d.items() if k not in ('target','known','instances')};tensor_hashes={k:array_hash(v) for k,v in inputs.items()}
    if r['original_pilot']:
        pilot=npz(PILOT/'data'/f'{sid}.npz')
        for k in ('optical','thickness_um','availability','shadow'):assert np.array_equal(d[k],pilot[k],equal_nan=True),'Pilot input drift: '+k
    results=[];evaluation=[];all_details={}
    for model in models:
        key=model['key'];path=HERE/'predictions'/key/f'{sid}.npz'
        pr=prediction_provenance(HERE/'predictions',key,sid,missing_ok=True)
        if path.exists() and pr is not None:
            verify(pr['prediction']);assert pr['checkpoint']['sha256']==model['checkpoint']['sha256'] and pr['tensor_sha256']==tensor_hashes[model['experiment']]
            pred=npz(path);p=pred['score'];mask=pred['mask'];labels=pred['candidate_labels']
        else:
            p=infer(nets[key],inputs[model['experiment']],torch.device('cuda'),4)
            mask=p>=model['threshold'];labels,_=components(mask)
            assert p.shape==(512,512) and np.isfinite(p).all()
            save(path,score=p,mask=mask,candidate_labels=labels,threshold=np.array(model['threshold']),scan_id=np.array(sid),axis_order=np.array('B-scan,A-line'),checkpoint_sha256=np.array(model['checkpoint']['sha256']))
            candidates=[dict(id=int(i),runs=encode(labels==i),pixels=int((labels==i).sum())) for i in range(1,int(labels.max())+1)]
            pr=dict(scan_id=sid,model=key,checkpoint=model['checkpoint'],threshold_record=model['threshold_record'],threshold=model['threshold'],
                normalization=model['normalization'],channels=model['channels'],tensor_sha256=tensor_hashes[model['experiment']],input_array_hashes=input_hashes,
                input_provenance=fingerprint(HERE/'inputs'/f'{sid}.json'),prediction=fingerprint(path),candidates=candidates,
                native_shape=[512,512],axis_order='B-scan,A-line',human_reviewed=False,postprocessing='None',score_meaning='uncalibrated model score')
            if r['original_pilot']:
                old=Path(model['checkpoint']['path']).parent/'scores'/f'{sid}.npz'
                pp=npz(old)['score'];pr['pilot_score_max_abs_difference']=float(np.max(np.abs(p-pp)))
                assert pr['pilot_score_max_abs_difference']<1e-5,'Pilot inference drift'
            save_prediction_provenance(HERE/'predictions',key,sid,pr)
        results.append(dict(model=key,suggestions=int(labels.max()),suggested_pixels=int(mask.sum()),suggested_area_mm2=float(mask.sum()*UM**2/1e6),edge_pixels=int(mask[0].sum()+mask[-1].sum()+mask[1:-1,0].sum()+mask[1:-1,-1].sum()),prediction_sha256=pr['prediction']['sha256']))
        for cutoff in PROTOCOL['iou_thresholds']:
            values,detail=score(mask,d,audit['complete'],cutoff)
            evaluation.append(dict(model=key,scan_id=sid,complete=audit['complete'],iou_cutoff=cutoff,**values))
            if cutoff==.1:all_details[key]=detail
    out=dict(status='completed',scan_id=sid,models=results,evaluation=evaluation,details=all_details,annotation_audit=audit,
        available_fraction_by_layer=d['availability'].mean((1,2)).tolist(),shadow_fraction=float(d['shadow'].mean()),low_signal_fraction=float(d['low_signal'].mean()),
        input_array_hashes=input_hashes,elapsed_seconds=time.monotonic()-t,reason='',human_evaluation='pending')
    write(HERE/'records'/f'{sid}.json',out)
    return out

def run(limit=None,worker=0,workers=1,scan_id=None):
    m=initialize();models=read(HERE/'models.json');stats=read(PILOT/'data/normalization.json')
    if scan_id is not None and not any(r['scan_id']==scan_id for r in m['scans']):raise ValueError('Unknown acquisition: '+scan_id)
    torch.set_num_threads(4);torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
    if not torch.cuda.is_available():raise RuntimeError('CUDA unavailable; original mixed-precision inference policy requires CUDA')
    nets={}
    for model in models:
        verify(model['checkpoint']);verify(model['normalization']);verify(model['threshold_record'])
        net=UNet(model['config']['channels']).cuda();net.load_state_dict(torch.load(model['checkpoint']['path'],map_location='cpu',weights_only=False)['model']);net.eval();nets[model['key']]=net
    count=0
    for index,r in enumerate(m['scans']):
        if scan_id is not None and r['scan_id']!=scan_id:continue
        if index%workers!=worker:continue
        sid=r['scan_id'];rp=HERE/'records'/f'{sid}.json'
        if rp.exists() and read(rp).get('status')=='completed':continue
        if limit is not None and count>=limit:break
        count+=1
        if shutil.disk_usage(HERE).free<200*1024**2:raise RuntimeError('Less than 200 MiB remains; free space within requested drive, then resume')
        lock=dest(HERE/'locks'/f'{sid}.lock')
        try:
            fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,str(os.getpid()).encode());os.close(fd)
        except FileExistsError:
            print('Another worker holds scan lock',sid,flush=True);continue
        try:
            out=predict_one(r,nets,models,stats)
            progress('Six predictions completed',scan=sid,seconds=round(out['elapsed_seconds'],1),suggestions={a['model']:a['suggestions'] for a in out['models']})
        except Exception as e:
            error=dict(status='failed',scan_id=sid,reason=f'{type(e).__name__}: {e}',traceback=traceback.format_exc(),action='Resolve the recorded source/provenance/runtime failure and rerun RUN_ALL.cmd; completed acquisitions are retained')
            write(rp,error);write(HERE/'failures'/f'{sid}.json',error);print(error['traceback'],flush=True)
        finally:lock.unlink(missing_ok=True)
        status(m)
        if (HERE/'PAUSE_AFTER_SCAN').exists():break
    status(m)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--limit',type=int);p.add_argument('--init',action='store_true');p.add_argument('--worker',type=int,default=0);p.add_argument('--workers',type=int,default=1);p.add_argument('--scan');args=p.parse_args()
    initialize() if args.init else run(args.limit,args.worker,args.workers,args.scan)
