"""Export full-cohort Model 2/3 comparisons and exact confirmed-reference overlays."""
from common import *
from candidates import extract,adjust
from media import run as media, png, rgba
import shutil

def run():
 assert (HERE/'COMPUTE_COMPLETE.json').exists()
 m=read(HERE/'data/supervision.json');truth={r['scan_id']:r for r in m['records']}
 cases=read(HERE/'data/selection.json')['acquisitions']
 media()
 md={r['scan_id']:r for r in read(HERE/'gallery/media_manifest.json')['records']}
 scorers={2:read(HERE.parent/'bundles/v9_m2/scorer.json'),3:read(HERE/'bundles/v9_m3/scorer.json')}
 index=[]
 for a in cases:
  sid=a['scan_id'];context=npz(HERE/'cache'/sid/'context.npz')['channels'];csall={};arrays={};status=[]
  for model,fit in [(2,'parent_m2'),(3,'final_m3')]:
   pred=HERE/'fits'/fit/'predictions'/(sid+'.npz');doc=read(pred.with_suffix('.json'));verify(doc['prediction']);z=npz(pred)
   labels,cs=extract(z['score'],context);cs=adjust(cs,scorers[model]);csall[f'm{model}']=cs
   mask=np.isin(labels,[c['id'] for c in cs if c['display_selected']])
   arrays.update({f'm{model}_score':z['score'],f'm{model}_labels':labels,f'm{model}_raw_mask':z['raw_mask'],f'm{model}_adjusted_mask':mask})
   status.append(dict(model=f'v9_m{model}',prediction=doc['prediction'],checkpoint=doc['checkpoint'],status='complete'))
  r=truth.get(sid);manual=[]
  if r:
   z=npz(r['target_file']['path'])
   manual=[dict(id=rr['id'],runs=encode(mask),area_pixels=int(mask.sum()),area_um2=int(mask.sum())*PX_UM**2) for rr,mask in zip(r['regions'],z['instances'])]
   manual_status=dict(confirmed=True,kind=r['kind'],source_version=r['source_version'],source=r['label'],training_target=r['target_file'],regions=len(manual),ignored_pixels=r['ignored_pixels'])
  else:manual_status=dict(confirmed=False,kind='unconfirmed',regions=0)
  write(HERE/'gallery/assets'/sid/'candidates.json',dict(scan_id=sid,**csall,manual=manual,manual_status=manual_status))
  save(HERE/'predictions'/(sid+'.npz'),scan_id=np.array(sid),axis_order=np.array('B-scan,A-line'),**arrays)
  c=read(HERE/'cache'/sid/'context.json')
  row=dict(a);row.update(status=status,canonical_crop_offset=md[sid]['canonical_crop_offset'],context_source=c['source'],context_notes=c.get('notes',''),manual_status=manual_status,training_scan=bool(r),quality_note=a.get('scan_notes',''),disagreement_pixels=int((arrays['m2_adjusted_mask']^arrays['m3_adjusted_mask']).sum()))
  for model in (2,3):
   cs=csall[f'm{model}'];row.update({f'm{model}_raw_count':len(cs),f'm{model}_count':sum(c['display_selected'] for c in cs),f'm{model}_hidden_count':sum(not c['display_selected'] for c in cs),f'm{model}_pixels':int(arrays[f'm{model}_adjusted_mask'].sum())})
  index.append(row)
 write(HERE/'gallery/data.json',dict(cases=index,selection_sha256=sha(HERE/'data/selection.json'),raw_pixel_threshold=.7,adjusted_candidate_threshold=.5,training=dict(acquisitions=101,positive=73,negative=28,regions=156),models=['v9_m2','v9_m3']))
 bundle=HERE/'bundles/v9_m3';fit=HERE/'fits/final_m3'
 for name in ('final.pt','normalization.json','config.json'):shutil.copyfile(fit/name,dest(bundle/name))
 for name in ('common.py','models.py','v6_model.py','legacy.py','prepare.py','context.py','candidates.py','training.py','freeze_inputs.py','run_pipeline.py','fit_candidate_scorer.py'):shutil.copyfile(HERE/name,dest(bundle/'source'/name))
 write(bundle/'bundle.json',dict(model='v9_m3',checkpoint=fingerprint(bundle/'final.pt'),normalization=fingerprint(bundle/'normalization.json'),scorer=fingerprint(bundle/'scorer.json'),training_manifest=fingerprint(HERE/'data/supervision.json'),protocol=fingerprint(HERE/'data/protocol.json'),contract=read(fit/'complete.json')['contract']))
 before=read(HERE/'data/preservation_before.json')['files']
 for fp in before:verify(fp)
 write(HERE/'reports/preservation_after.json',dict(unchanged=True,files_checked=len(before)))
 write(HERE/'DELIVERY_COMPLETE.json',dict(models=['v9_m2','v9_m3'],acquisitions=len(index),training_acquisitions=101,positive=73,negative=28,regions=156,source_annotations_unchanged=True,independent_accuracy_claim=False))
 progress('Verifying Model 3 full-cohort release',acquisitions=len(index))
 from verify_delivery import run as verify_delivery
 verify_delivery()
 progress('Model 3 and full-cohort comparison verified',acquisitions=len(index))

if __name__=='__main__':run()
