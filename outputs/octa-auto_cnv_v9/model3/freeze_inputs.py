"""Export the user-selected confirmation inventory without changing human records."""
from common import *
import importlib.util, shutil
from collections import Counter
from legacy import export_target

PARENT=HERE.parent
INVENTORY=ROOT/'outputs/cnv_confirmation_inventory_20260921/inventory.json'

def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path)
 mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def run():
 if (HERE/'data/supervision.json').exists():
  doc=read(HERE/'data/supervision.json')
  for r in doc['records']:verify(r['label']);verify(r['target_file'])
  return doc
 inventory=read(INVENTORY)
 chosen=[r for r in inventory['selected_acquisitions'] if r['confirmed'] and r['kind'] in ('positive','negative')]
 assert Counter(r['kind'] for r in chosen)==dict(positive=73,negative=28)
 assert len({r['acquisition_key'] for r in chosen})==101
 acquisitions=read(V7/'queue/inventory.json')['scans']
 assert len(acquisitions)==324 and len({a['source_identity'] for a in acquisitions})==324
 byid={a['scan_id']:a for a in acquisitions}
 v7=module('original_v7_review',V7/'review_store.py')
 v9=module('original_v9_review',PARENT/'review_store.py')
 web=object.__new__(v9.ReviewStore);web.gallery=PARENT/'gallery';web.data=read(web.gallery/'data.json');web.cases={a['scan_id']:a for a in web.data['cases']}
 records=[];preserve=[fingerprint(INVENTORY)];audit=[]
 for row in chosen:
  sid=row['scan_id'];a=byid[sid];fp=fingerprint(row['path']);assert fp['sha256']==row['sha256'],sid+' changed since inventory'
  d=read(row['path']);assert d['scan_id']==sid and not d.get('synthetic',False)
  assert d['axis_order']=='B-scan,A-line' if row['version']!=9 else True
  if row['source_identity']:assert row['source_identity']==a['source_identity']
  details={}
  if row['version'] in (7,8):
   assert d['native_shape']==[512,512]
   p,b,ig,drafts,overlap=v7.targets(d['state'],(512,512),require_complete=True)
   assert v7.completion_kind(d['state'],(512,512))==row['kind'] and not drafts
   assert d['masks']==dict(positive=encode(p),reviewed_background=encode(b),ignored=encode(ig))
   assert d['state']['confirmation']['ignored_conflict_pixels']==overlap
   regions=[r for r in d['state']['regions'] if r['state']=='kept' and (decode(r['runs'])&~ig).any()]
   instances=[decode(r['runs'])&~ig for r in regions];ids=[r['id'] for r in regions]
   z=dict(target=p,known=p|b,ignored=ig,instances=np.stack(instances) if instances else np.zeros((0,512,512),bool))
  elif row['version']==5:
   z,details=export_target(d,a)
   assert details['complete'],(sid,details)
   z['ignored']=~z['known'];ids=row['region_ids']
  elif row['version']==9:
   contract,token=web.contract(sid);assert token==d['token'] and contract['models']==d['prediction_contract']['models']
   interpreted=v9.interpret_approval(d);model=interpreted['preferred_shared_target_model'];assert model==row['preferred_model']
   for status in contract['predictions']:
    for key in ('prediction','checkpoint'):verify(status[key]);preserve.append(status[key])
   cp=web.gallery/'assets'/sid/'candidates.json';cs=read(cp)['m2' if model=='m2_adjusted' else 'm1']
   if model=='m2_adjusted':cs=[c for c in cs if c['display_selected']]
   instances=[decode(c['runs']) for c in cs];ids=[c['id'] for c in cs]
   stack=np.stack(instances) if instances else np.zeros((0,512,512),bool);p=stack.any(0)
   assert hashlib.sha256(p.tobytes()).hexdigest()==contract['models'][model]['mask_sha256']
   z=dict(target=p,known=np.ones((512,512),bool),ignored=np.zeros((512,512),bool),instances=stack)
   preserve.append(fingerprint(cp));details=dict(approved_model=model)
  else:raise ValueError('Unsupported source version')
  assert int(z['target'].sum())==row['positive_pixels'],(sid,'positive pixel mismatch',details)
  assert int(z['ignored'].sum())==row['ignored_pixels'],(sid,'ignored pixel mismatch',details)
  assert len(z['instances'])==row['regions']==len(ids)
  assert np.array_equal(z['instances'].any(0),z['target']) and not (z['target']&~z['known']).any()
  assert bool(z['target'].any())==(row['kind']=='positive')
  assert row['kind']!='negative' or z['known'].all()
  target=HERE/'data/targets'/(sid+'.npz');save(target,**z,scan_id=np.array(sid),axis_order=np.array('B-scan,A-line'))
  shutil.copyfile(row['path'],dest(HERE/'data/source_snapshots'/(fp['sha256']+'.json')))
  records.append(dict(scan_id=sid,animal=a['animal'],acquisition=a,kind=row['kind'],label=fp,target_file=fingerprint(target),source_version=row['version'],revision=row['revision'],regions=[dict(id=i,pixels=int(m.sum())) for i,m in zip(ids,z['instances'])],positive_pixels=int(z['target'].sum()),ignored_pixels=int(z['ignored'].sum()),inventory_record=row,export_details=details))
  preserve.append(fp)
 assert sum(len(r['regions']) for r in records)==156
 protocol=read(PARENT/'data/protocol.json')
 protocol.update(release='v9 Model 3',parent_model='v9 Model 2',training_authority='User: use exactly 73 confirmed positive and 28 confirmed no-CNV scans from supplied inventory',fit_count=dict(final=1,animal_excluded_scorer=3),initialization='fresh, matching Model 2 recipe',evaluation='Three animal-excluded fits supply scorer targets only; final all-label fit is not independent evaluation. No held-out accuracy claimed.',inventory=fingerprint(INVENTORY))
 for f in protocol['folds']:f.pop('inner',None)
 doc=dict(records=records,animals=sorted({r['animal'] for r in records}),eligible_counts=dict(Counter(r['kind'] for r in records)),kept_regions=156,inventory=fingerprint(INVENTORY),policy='Use exactly requested 101 selected records; uncertain-only and pending excluded; retain ignored pixels; never union alternative sources.')
 for i,a in enumerate(acquisitions,1):a['queue_position']=i;a['visit_group']=a['session_date']
 write(HERE/'data/protocol.json',protocol);write(HERE/'data/selection.json',dict(acquisitions=acquisitions,scope='all 324 processed acquisitions, including training fields; predictions are proposals'))
 write(HERE/'data/preservation_before.json',dict(files=list({p['path']:p for p in preserve}.values())))
 shutil.copyfile(INVENTORY,dest(HERE/'data/inventory_snapshot.json'))
 write(HERE/'data/supervision.json',doc)
 print(json.dumps(dict(acquisitions=len(records),counts=doc['eligible_counts'],regions=156,inference_acquisitions=len(acquisitions))),flush=True)
 return doc

if __name__=='__main__':run()
