"""Final artifact and preservation audit; never writes human annotations."""
from batch import *
from compare import native_iou
import ast

def run():
    inventory=read(HERE/'inventory.json');models={m['key']:m for m in read(HERE/'models.json')};checks=[];errors=[];input_modes=Counter();pilot_differences=[]
    disk={str(p.resolve()).lower() for p in (ROOT.parent/'OCTA_RawData').rglob('*_processedVolumes.mat')}
    accounted={str(Path(r['source']).resolve()).lower() for r in inventory['scans']}
    accounted.update(str(Path(a['duplicate']['path']).resolve()).lower() for a in read(HERE/'verification/duplicate_files.json'))
    assert disk==accounted,dict(new_or_unaccounted=sorted(disk-accounted),now_missing=sorted(accounted-disk))
    for p in HERE.glob('*.py'):ast.parse(p.read_text(encoding='utf-8-sig'),filename=str(p))
    for model in models.values():
        for name in ('checkpoint','threshold_record','normalization'):verify(model[name])
    for r in inventory['scans']:
        sid=r['scan_id'];rp=HERE/'records'/f'{sid}.json'
        try:
            rec=read(rp);assert rec['status']=='completed',rec.get('reason','unfinished')
            meta=read(HERE/'inputs'/f'{sid}.json');verify(meta['optical_cache']);verify(meta['source'])
            assert meta['automatic_only'] and meta['octa_channel']=='frame_OCTAAvg'
            input_modes['new_frozen_upstream' if meta.get('new_acquisition_upstream') else 'regenerated_without_human_vessel_or_ONH_masks' if meta.get('regenerated_neural') else 'verified_automatic_reuse']+=1
            assert meta['native_shape']==[512,512,1024]
            if meta.get('upstream_grid_audit'):
                verify(meta['upstream_grid_audit']);assert read(meta['upstream_grid_audit']['path'])['verified']
            else:assert meta['structural_three_bscan_max_abs_error_db']<1e-4
            references=reference_arrays(sid);assert references['target'].shape==(512,512)
            assert not (references['target']&~references['known']).any()
            for key,model in models.items():
                p=HERE/'predictions'/key/f'{sid}.npz';pr=prediction_provenance(HERE/'predictions',key,sid);verify(pr['prediction']);a=npz(p)
                assert pr['checkpoint']['sha256']==model['checkpoint']['sha256']
                assert pr['threshold']==model['threshold'] and float(a['threshold'])==model['threshold']
                assert a['score'].shape==a['mask'].shape==a['candidate_labels'].shape==(512,512)
                assert a['score'].dtype==np.float32 and np.isfinite(a['score']).all()
                assert np.array_equal(a['score']>=model['threshold'],a['mask'])
                assert np.array_equal(a['candidate_labels']>0,a['mask'])
                assert str(a['scan_id'])==sid and str(a['axis_order'])=='B-scan,A-line'
                labs,_=components(a['mask']);assert np.array_equal(labs,a['candidate_labels'])
                assert len(pr['candidates'])==int(labs.max())
                for c in pr['candidates']:assert np.array_equal(decode(c['runs']),labs==c['id'])
                if r['original_pilot']:
                    assert pr['pilot_score_max_abs_difference']<1e-5;pilot_differences.append(pr['pilot_score_max_abs_difference'])
            comp=npz(HERE/'comparison/native'/f'{sid}.npz')
            masks={k:npz(HERE/'predictions'/k/f'{sid}.npz')['mask'] for k in KEYS}
            assert np.array_equal(comp['votes_B'],sum(masks[k] for k in KEYS[:3]))
            assert np.array_equal(comp['votes_C'],sum(masks[k] for k in KEYS[3:]))
            from itertools import combinations
            for a,b in combinations(KEYS,2):assert np.array_equal(comp[a+'__'+b],masks[a]^masks[b])
            checks.append(dict(scan_id=sid,passed=True,models=6,source_grid_orientation=True,native_footprints=True))
        except Exception as e:errors.append(dict(scan_id=sid,error=f'{type(e).__name__}: {e}',traceback=traceback.format_exc()))
        write(HERE/'verification/native_output_checks.json',dict(checked=len(checks),errors=errors,scans=checks))
    before=read(HERE/'verification/preservation_before.json');changed=[]
    for path,expected in before.items():
        if not Path(path).exists() or sha(path)!=expected:changed.append(path)
    write(HERE/'verification/preservation_after.json',dict(files_checked=len(before),unchanged=not changed,changed=changed))
    gui=read(HERE/'verification/gui_tests.json');real=read(HERE/'verification/gui_real_data.json')
    assert read(HERE/'verification/frozen_implementation_contract.json')['passed']
    assert read(HERE/'verification/new_acquisition_inputs.json')['passed']
    assert read(HERE/'verification/new_acquisition_headers.json')['passed']
    index_test=read(HERE/'verification/index_tests.json')
    assert index_test['passed'] and index_test['acquisitions_in_index']==len(inventory['scans'])
    assert read(HERE/'verification/gui_new_acquisition.json')['passed']
    assert gui['passed'] and real['passed'] and not changed and not errors,dict(gui=gui,real=real,changed=changed,errors=errors)
    assert len(checks)==len(inventory['scans'])
    queue=read(HERE/'comparison/review_queue.json');assert len(queue)==len(checks)
    no=[r for r in queue if r['any_model_no_suggestions']]
    assert not no or any(r['any_model_no_suggestions'] and r['fixed_random_sample'] for r in queue)
    assert not any(r['all_models_no_suggestions'] for r in queue) or any(r['all_models_no_suggestions'] and r['fixed_random_sample'] for r in queue)
    files=[fingerprint(p) for pattern in ('*.py','*.cmd','*.js') for p in sorted(HERE.glob(pattern))]
    write(HERE/'verification/implementation_manifest.json',files)
    summary=read(HERE/'comparison/summary.json')
    result=dict(passed=True,**summary,source_inventory=inventory['reconciliation'],preserved_original_files=len(before),
        input_preparation_counts=input_modes,original_pilot_prediction_sets_checked=len(pilot_differences),pilot_max_abs_score_difference=max(pilot_differences),
        models_unchanged=True,all_native_prediction_footprints_verified=True,original_pilot_reproduced=True,isolated_gui_tests=gui['tests'],real_data_gui_verified=True,new_acquisition_gui_verified=True,offline_comparison_index_verified=True,
        completed=time.strftime('%Y-%m-%dT%H:%M:%S'))
    write(HERE/'FINAL_VERIFIED.json',result)
    guide=HERE/'START_HERE.md';content=guide.read_text(encoding='utf-8')
    content=content.replace('**Batch preparation is in progress.**',f"**Batch complete: {len(checks)} acquisitions, {len(checks)*6:,} individual predictions, 11 animals.**")
    content=content.replace('`FINAL_VERIFIED.json` is written only when the eligible batch and required checks are complete.','[FINAL_VERIFIED.json](FINAL_VERIFIED.json) records successful native-output, model, provenance, preservation and GUI checks.')
    guide.write_text(content,encoding='utf-8')
    print(json.dumps(result),flush=True)

if __name__=='__main__':run()
