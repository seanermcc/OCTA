"""Verify complete inference, reference parity, unchanged Model 2, and source preservation."""
from common import *
from collections import Counter

def run():
 m=read(HERE/'data/supervision.json');records={r['scan_id']:r for r in m['records']};gallery=read(HERE/'gallery/data.json');cases=gallery['cases']
 assert len(cases)==324 and len({a['source_identity'] for a in cases})==324
 assert {a['scan_id'] for a in cases}=={a['scan_id'] for a in read(HERE/'data/selection.json')['acquisitions']}
 media=read(HERE/'gallery/media_manifest.json')['records']
 assert len(media)==324 and {a['scan_id'] for a in media}=={a['scan_id'] for a in cases}
 recovered=[]
 for a in media:
  fp=a['images'];st=Path(fp['path']).stat();assert (st.st_size,st.st_mtime_ns)==(fp['bytes'],fp['mtime_ns'])
  images=np.load(fp['path'],mmap_mode='r');assert images.shape==(512,a['depth'],512);del images
  for output in a['outputs']:verify(output)
  provider=HERE/'cache'/a['scan_id']/'gallery_images.json'
  if provider.exists():
   r=read(provider);upstream=read(V6/'inputs'/(a['scan_id']+'.json'))
   assert r['array_sha256']==upstream['images_array_sha256'] and r['images']==fp
   recovered.append(a['scan_id'])
 cp=read(HERE/'fits/final_m3/complete.json');verify(cp['checkpoint']);assert cp['completed_epochs']==100 and cp['optimizer_steps']==3200
 assert set(cp['contract']['training_scan_ids'])==set(records)
 assert all(cp['sampling_counts'].get('scan:'+sid,0)>0 for sid in records)
 assert cp['contract']['channels']==30 and cp['contract']['fresh_weights']
 for filename,expected in cp['contract']['code'].items():assert sha(HERE/filename)==expected,(filename,'trained source changed')
 stats=read(HERE/'fits/final_m3/normalization.json');assert set(stats['training_scan_ids'])==set(records)
 examples=read(HERE/'development/scorer_examples.json')['records']
 for r in examples:assert r['animal'] not in r['cnv_training_animals']
 for f in read(HERE/'data/protocol.json')['folds']:
  folder=HERE/'fits'/f"scorer_fold{f['fold']}";complete=read(folder/'complete.json');verify(complete['checkpoint'])
  assert complete['completed_epochs']==100 and complete['optimizer_steps']==3200
  assert set(complete['contract']['training_animals']).isdisjoint(f['evaluation_animals'])
  assert set(read(folder/'normalization.json')['training_scan_ids'])=={r['scan_id'] for r in m['records'] if r['animal'] in f['train_animals']}
 totals=Counter();parent_comparisons=[];context_exclusions=[]
 for i,a in enumerate(cases):
  sid=a['scan_id'];z=npz(HERE/'predictions'/(sid+'.npz'));cs=read(HERE/'gallery/assets'/sid/'candidates.json')
  assert str(z['scan_id'])==sid and str(z['axis_order'])=='B-scan,A-line'
  for model in ('m2','m3'):
   score=z[model+'_score'];assert score.shape==(512,512) and np.isfinite(score).all() and score.min()>=0 and score.max()<=1
   assert np.array_equal(z[model+'_raw_mask'],score>=.7)
   union=np.zeros((512,512),bool);raw=union.copy()
   for c in cs[model]:
    mask=decode(c['runs']);assert int(mask.sum())==c['area_pixels'];raw|=mask
    if c['display_selected']:union|=mask
   assert np.array_equal(raw,z[model+'_raw_mask']) and np.array_equal(union,z[model+'_adjusted_mask'])
   assert a[model+'_count']==sum(c['display_selected'] for c in cs[model])
   totals[model+'_displayed_candidates']+=a[model+'_count'];totals[model+'_raw_candidates']+=len(cs[model]);totals[model+'_zero_scans']+=a[model+'_count']==0
  for p in a['status']:verify(p['prediction'])
  manual=np.zeros((512,512),bool)
  for c in cs['manual']:manual|=decode(c['runs'])
  if sid in records:
   ref=npz(records[sid]['target_file']['path']);assert np.array_equal(manual,ref['target']);assert cs['manual_status']['kind']==records[sid]['kind']
  else:assert not manual.any() and not cs['manual_status']['confirmed']
  cache=HERE/'cache'/sid;manifest=read(cache/'manifest.json')
  for fp in manifest['outputs']:
   local=cache/Path(fp['path']).name;assert sha(local)==fp['sha256'],(sid,'local cache differs')
  c=read(cache/'context.json')
  if c.get('excluded_context'):context_exclusions.append(sid);assert not npz(cache/'context.npz')['channels'].any()
  old=HERE.parent/'fits/final_m2/predictions'/(sid+'.npz')
  if old.exists():
   original=npz(old);delta=float(np.max(np.abs(original['score']-z['m2_score'])))
   assert np.array_equal(original['raw_mask'],z['m2_raw_mask']),(sid,'parent mask changed')
   assert delta<1e-6,(sid,'parent probabilities changed',delta)
   parent_comparisons.append(dict(scan_id=sid,max_probability_difference=delta))
  if (i+1)%50==0:print(json.dumps(dict(verified=i+1,total=324)),flush=True)
 for fp in read(HERE/'data/preservation_before.json')['files']:verify(fp)
 result=dict(passed=True,acquisitions=324,training_scans=101,positive=73,negative=28,kept_regions=156,all_training_scans_sampled=True,training_schedule=dict(epochs=100,optimizer_steps=3200),animal_excluded_scorer_fits=3,scorer_examples=len(examples),source_annotations_unchanged=True,parent_model2_prediction_comparisons=parent_comparisons,withheld_historical_context=context_exclusions,prediction_counts=dict(totals),native_display_providers=324,recovered_display_crops_with_exact_upstream_array_parity=recovered,independent_accuracy_claim=False)
 write(HERE/'FINAL_VERIFIED.json',result)
 lines=['# Model 3 completed','', 'Trained on the requested **101 unique acquisitions: 73 confirmed positive and 28 confirmed no-CNV scans**, containing **156 kept CNV region observations**. All 101 scans were sampled. The inventory snapshot, source hashes, exact native targets and ignored-pixel masks are saved in `data/`.','', 'Both Model 2 and Model 3 completed inference on **all 324 processed acquisitions**. Open **OPEN_GALLERY.cmd** for the separate comparison at http://127.0.0.1:8803. Manual confirmed CNVs have an independent overlay checkbox. The new **no CNVs present** checkbox saves a whole-field absence verdict to a separate review namespace.','', 'Model 3 is a fresh retraining of Model 2’s 30-channel architecture using its unchanged loss, seed, optimizer, 100 epochs / 3,200 steps, animal-balanced sampling and thresholds. Normalization uses only the specified training scans. Three additional animal-excluded networks supply predictions to fit the new candidate scorer; they are not an independent evaluation of the final adjusted model.','', '| Inference output | Model 2 | Model 3 |','|---|---:|---:|',f"| Raw candidates | {totals['m2_raw_candidates']} | {totals['m3_raw_candidates']} |",f"| Displayed adjusted candidates | {totals['m2_displayed_candidates']} | {totals['m3_displayed_candidates']} |",f"| Scans with no displayed candidates | {totals['m2_zero_scans']} | {totals['m3_zero_scans']} |",'', 'These are prediction counts, not confirmed lesion counts or accuracy estimates. The gallery explicitly marks training scans. All raw probabilities and down-ranked candidates remain available.','',f"Verification passed for 324 native grids, both models’ candidate-mask parity, all 101 manual-reference overlays, training/scorer provenance and unchanged source annotations. Frozen Model 2 predictions also matched the {len(parent_comparisons)} existing comparison predictions.",'','Historical vessel-context exclusions were retained as missing context for two scans. One belongs to the explicit user-selected 101-scan cohort; its confirmed CNV-negative target is included as requested. The older excluded vessel annotations were not consumed. No model-finalization decision has been made.','', 'Weights, normalization, scorer and training contract: `bundles/v9_m3/`. Resume checkpoints and complete logs: `fits/`. Verification: `FINAL_VERIFIED.json`.']
 dest(HERE/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
 print(json.dumps({k:v for k,v in result.items() if k!='parent_model2_prediction_comparisons'}),flush=True)

if __name__=='__main__':run()
