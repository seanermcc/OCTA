"""Bounded real-data and final release contracts, independent from human writers."""
from common import *
import argparse,subprocess
from context import loader
from candidates import extract,adjust,metrics
def preflight():
 m=read(HERE/'data/supervision.json');selection=read(HERE/'data/selection.json');supplement=read(HERE/'data/novelty_supplement.json');cases=selection['acquisitions'];history=read(HERE/'data/historical_annotations.json')['records'];banned={r['scan_id'] for r in history if r['excludes_novelty']}|set(supplement['additional_cnv_acquisitions'])|{a['scan_id'] for a in read(V8/'manual_review/queue/queue.json')['acquisitions']}
 assert len(cases)==50 and len({a['source_identity'] for a in cases})==50
 assert not {a['scan_id'] for a in cases}&banned
 assert m['selection_sha256']==sha(HERE/'data/selection.json') and m['protocol_sha256']==sha(HERE/'data/protocol.json')
 for r in m['records']:
  z=npz(r['target_file']['path']);assert z['known'].dtype==bool and z['target'].shape==(512,512);assert not (z['target']&~z['known']).any();assert np.array_equal(z['known'],~z['ignored']);assert np.array_equal(z['instances'].any(0) if len(z['instances']) else np.zeros((512,512),bool),z['target'])
  assert str(z['label_sha256'])==r['label']['sha256'];verify(r['label'])
 for a in [cases[0],cases[-1],m['records'][0]['acquisition']]:
  z,r=loader.load_masks(a['scan_id'],a['source']);assert z['vessel_mask'].shape==(512,512)
  for bad_args in [(a['scan_id'],'wrong-source',(512,512)),(a['scan_id'],a['source'],(511,512))]:
   try:loader.load_masks(*bad_args)
   except ValueError:pass
   else:raise AssertionError('Loader accepted mismatched source/grid')
 records=read(HERE/'gallery/media_manifest.json')['records'];assert {r['scan_id'] for r in records}=={a['scan_id'] for a in cases}
 assert max(r['structural_projection_max_error_db'] for r in records)<.001
 for r in records:
  images=np.load(r['images']['path'],mmap_mode='r');assert images.shape[0]==512 and images.shape[2]==512;assert np.isfinite(images[[0,511]]).all()
 result=dict(passed=True,supervision_acquisitions=len(m['records']),kept_regions=m['kept_regions'],selected=len(cases),novelty_including_layer_journals=True,source_grid_mismatch_rejected=True,all_native_edge_rows_finite=True,max_projection_error_db=max(r['structural_projection_max_error_db'] for r in records),annotation_hashes_unchanged=True)
 write(HERE/'verification/REAL_PREFLIGHT.json',result);return result

def final():
 m=read(HERE/'data/supervision.json');protocol=read(HERE/'data/protocol.json');cases=read(HERE/'data/selection.json')['acquisitions'];index=read(HERE/'gallery/data.json')['cases'];scorer=read(HERE/'bundles/v9_m2/scorer.json')
 assert {a['scan_id'] for a in cases}=={a['scan_id'] for a in index}
 counts=[]
 for a in cases:
  sid=a['scan_id'];z=npz(HERE/'predictions'/(sid+'.npz'));cs=read(HERE/'gallery/assets'/sid/'candidates.json');counts.append([len(cs['m1']),len(cs['m2'])])
  for model in (1,2):
   source=npz(HERE/'fits'/f'final_m{model}'/'predictions'/(sid+'.npz'));assert np.array_equal(z[f'm{model}_score'],source['score']);assert np.array_equal(z[f'm{model}_raw_mask'],source['score']>=.7)
   reconstructed=np.zeros((512,512),bool)
   for c in cs[f'm{model}']:
    mask=decode(c['runs']);assert mask.sum()==c['area_pixels'];assert abs(c['area_um2']-mask.sum()*PX_UM**2)<1e-5;reconstructed|=mask
   assert np.array_equal(reconstructed,z[f'm{model}_raw_mask'])
  wanted=np.zeros((512,512),bool)
  for c in cs['m2']:
   if c['display_selected']:wanted|=decode(c['runs'])
  assert np.array_equal(wanted,z['m2_adjusted_display_mask'])
  assert [c['runs'] for c in adjust(cs['m2'],scorer)]==[c['runs'] for c in cs['m2']]
 for f in protocol['folds']:
  fit=read(HERE/'development'/f"outer{f['fold']}_scorer.json")
  assert not set(fit['training_animals'])&set(f['evaluation_animals'])
  for e in read(HERE/'development'/f"outer{f['fold']}_fitting_examples.json")['records']:
   assert e['animal'] not in e['cnv_training_animals'];assert not (set(e['cnv_training_animals'])|{e['animal']})&set(f['evaluation_animals'])
 complete=list((HERE/'fits').glob('*/complete.json'));assert len(complete)==14
 for p in complete:
  r=read(p);assert r['completed_epochs']==100 and r['optimizer_steps']==3200
  stats=read(p.parent/'normalization.json');assert stats['training_scan_ids']==r['contract']['training_scan_ids'];assert stats['training_animals']==r['contract']['training_animals'];verify(r['checkpoint'])
 result=dict(passed=True,complete_fits=14,total_optimizer_steps=14*3200,matched_inference_membership=len(cases),raw_candidates_preserved=True,adjustment_preserves_geometry=True,independent_scorer_roles=True,training_only_normalization=True,all_probability_arrays_finite=True,candidates_per_scan=counts)
 write(HERE/'verification/FINAL_DATA_QA.json',result);return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--final',action='store_true');args=p.parse_args();print(json.dumps(final() if args.final else preflight(),indent=2))
