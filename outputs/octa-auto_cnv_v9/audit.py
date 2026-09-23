"""Freeze only latest confirmed CNV heads, novelty inventory, roles and policies."""
from common import *
from collections import Counter,defaultdict
import random, shutil, re
from context import load_context, CHANNELS

def validate_target(d,a):
 if d['schema']!='cnv-model1-correction-v8.1' or d['synthetic']:raise ValueError('Wrong correction schema')
 if d['scan_id']!=a['scan_id'] or d['source_identity']!=a['source_identity']:raise ValueError('Annotation identity mismatch')
 if d['native_shape']!=[512,512] or d['axis_order']!='B-scan,A-line':raise ValueError('Annotation grid mismatch')
 s=d['state'];c=s.get('confirmation');valid=bool(c and c.get('whole_field_checked') and c.get('annotation_sha256')==digest({k:s[k] for k in ('regions','absence')}))
 p=np.zeros((512,512),bool);ig=p.copy();instances=[];ids=[];draft=False
 for r in s['regions']:
  if r['id'] in ids:raise ValueError('Duplicate region ID')
  ids.append(r['id']);m=decode(r['runs']);state=r['state']
  if state not in ('kept','removed','unsure','excluded','draft'):raise ValueError('Region state')
  if state=='removed':continue
  draft |= state=='draft' or not m.any()
  if state=='kept':p|=m;instances.append(m)
  elif state in ('unsure','excluded'):ig|=m
 conflict=int((p&ig).sum());p &= ~ig
 if valid:
  if draft or s.get('defer_reason') or not (0<c['completion_revision']<=d['revision']):raise ValueError('Invalid confirmed revision')
  if not ((s['absence'] and not p.any() and not ig.any()) or (not s['absence'] and p.any())):raise ValueError('Invalid confirmed absence/positive')
  if c.get('ignored_conflict_pixels')!=conflict:raise ValueError('Conflict acknowledgement differs')
 k=~ig if valid else np.zeros_like(p)
 for key,m in [('positive',p),('reviewed_background',k&~p),('ignored',ig)]:
  if not np.array_equal(decode(d['masks'][key]),m):raise ValueError('Stored mask mismatch')
 kind=('positive' if p.any() else 'negative') if valid else ('deferred' if s.get('defer_reason') else 'draft')
 if d['kind']!=kind:raise ValueError('Stored completion state mismatch')
 return dict(target=p,known=k,ignored=ig,instances=np.stack(instances)&~ig if instances else np.zeros((0,512,512),bool)),kind

def historical_inventory():
 """Scan live and historical annotation namespaces, including vessel-only records."""
 records=[]; skipped=[]
 prune={'cache','checkpoints','predictions','proposals','figures','images','inputs','volumes','verification','__pycache__','.git','node_modules','code_snapshot','implementation_snapshot','sources','targets','segmented','neural','raw_neural','position','states'}
 for directory,dirs,files in os.walk(ROOT/'outputs'):
  p=Path(directory)
  dirs[:]=[x for x in dirs if x not in prune and not (p/x).is_relative_to(HERE)]
  for name in files:
   f=p/name
   candidate=name.endswith('_cnv.npz') or name.endswith('_regions.json') or (p.name=='regions' and name.endswith('.json')) or ('history' in p.parts and name.endswith('.json') and 'regions' in p.parts)
   if not candidate:continue
   try:
    if f.suffix=='.npz':
     z=npz(f)
     if 'cnv_mask' not in z:continue
     sid=str(np.asarray(z.get('scan_id','')).reshape(-1)[0]);reviews=z.get('reviewed_targets')
     reviewed=bool(np.asarray(reviews if reviews is not None else z.get('reviewed',False)).reshape(-1)[0])
     has=bool(z['cnv_mask'].any()) or reviewed
     info=dict(reason='CNV mask or explicit CNV review' if has else 'vessel/ONH-only record; not a CNV novelty exclusion',cnv_reviewed=reviewed,cnv_pixels=int(z['cnv_mask'].sum()))
    else:
     d=read(f)
     if 'scan_id' not in d or d.get('synthetic'):continue
     sid=d['scan_id'];has=True;info=dict(reason='prior CNV annotation/review record, including drafts and historical revisions')
    records.append(dict(scan_id=sid,excludes_novelty=has,source=fingerprint(f),**info))
   except Exception as e:skipped.append(dict(path=str(f),error=str(e)))
 if skipped:write(HERE/'data/novelty_errors.json',skipped);raise ValueError('Cannot establish novelty for unreadable annotation inventory')
 # Existing training/normalization use must be excluded even if its label moved.
 old=read(V8/'data/manifest.json')
 for r in old['records']:records.append(dict(scan_id=r['scan_id'],excludes_novelty=True,reason='v8 training exposure',source=fingerprint(V8/'data/manifest.json')))
 return records

def freeze():
 mp=HERE/'data/supervision.json'
 if mp.exists():
  m=read(mp)
  for r in m['records']:verify(r['label']);verify(r['target_file'])
  return m
 qpath=V8/'manual_review/queue/queue.json';q=read(qpath)['acquisitions']
 ex=read(EXPORT/'manifest.json');exby={r['scan_id']:r for r in ex['records']}
 if sha(EXPORT/'manifest.json')!=read(EXPORT/'VERIFIED.json')['manifest_sha256']:raise ValueError('Export manifest changed')
 records=[];omissions=[];counts=Counter();fps=[fingerprint(qpath),fingerprint(EXPORT/'manifest.json'),fingerprint(EXPORT/'VERIFIED.json'),fingerprint(EXPORT/'load_masks.py')]
 for a in q:
  p=V8/'manual_review/review/regions'/(a['scan_id']+'.json')
  if not p.exists():omissions.append(dict(scan_id=a['scan_id'],reason='unsaved'));continue
  fp=fingerprint(p);fps.append(fp);d=read(p);z,kind=validate_target(d,a);counts[kind]+=1
  if kind not in ('positive','negative'):omissions.append(dict(scan_id=a['scan_id'],reason=kind,detail=d['state'].get('defer_reason')));continue
  if exby.get(a['scan_id'],{}).get('excluded_from_analysis'):omissions.append(dict(scan_id=a['scan_id'],reason='vessel export acquisition exclusion'));continue
  context,prov=load_context(a)
  out=HERE/'data/targets'/(a['scan_id']+'.npz');save(out,**z,scan_id=np.array(a['scan_id']),axis_order=np.array('B-scan,A-line'),label_sha256=np.array(fp['sha256']))
  # Exact source copies are an immutable audit snapshot, never GUI label heads.
  src=dest(HERE/'data/source_snapshots'/(fp['sha256']+'.json'));shutil.copyfile(p,src)
  rr=[dict(id=r['id'],origin=r['origin'],pixels=int((decode(r['runs'])&~z['ignored']).sum())) for r in d['state']['regions'] if r['state']=='kept']
  records.append(dict(scan_id=a['scan_id'],animal=a['animal'],acquisition=a,kind=kind,label=fp,target_file=fingerprint(out),revision=d['revision'],annotation_signature=d['state']['confirmation']['annotation_sha256'],regions=rr,context=prov,positive_pixels=int(z['target'].sum()),background_pixels=int((z['known']&~z['target']).sum()),ignored_pixels=int((~z['known']).sum())))
  verify(fp)
 if len({r['acquisition']['source_identity'] for r in records})!=len(records):raise ValueError('Duplicate supervision acquisition')
 animals=sorted({r['animal'] for r in records});random.Random(267).shuffle(animals)
 groups=[sorted(animals[i::3]) for i in range(3)]
 # Nested three outer folds, two inner folds. Only m2 inner fits needed for scorer examples.
 roles=[]
 for i,ev in enumerate(groups):
  tr=sorted(set(animals)-set(ev));inner=[tr[::2],tr[1::2]]
  roles.append(dict(fold=i,train_animals=tr,evaluation_animals=ev,inner=[dict(train_animals=inner[1-j],candidate_animals=inner[j]) for j in range(2)]))
 policy=dict(seed=267,selection_seed=20260920,epochs=100,steps_per_epoch=32,effective_batch=4,microbatch=1,lr=.001,weight_decay=.0001,raw_threshold=.7,adjusted_threshold=.5,matching=dict(detection_iou=.1,scorer_positive_iou=.25,min_assessed_fraction=.95,negative='zero positive overlap and no ignored-boundary contact',ambiguous='split/merge, low overlap, or insufficient assessment -> no scorer label'),scorer=dict(features=['mean_probability','max_probability','log_area','vessel_overlap','vessel_proximity','onh_overlap','onh_proximity','vessel_available','onh_available','vessel_reviewed','onh_reviewed','manual_source'],l2=10.,threshold=.5,status='uncalibrated regularized candidate ranking; no probability calibration claim'),folds=roles,fit_count=dict(m1=4,m2=10),context_channels=CHANNELS,area_um_per_pixel=PX_UM,selection='final epoch; all thresholds and regularization frozen before results; no tuning',size_strata='tertiles of observed human region areas from applicable training animals only',limitations=['CNV segmenters animal-separated; frozen upstream layer/vessel models may have seen those animals','Manual vessel/ONH context is human assisted and may contain label-informed edits','Connected-component matches are computational correspondences, not verified biological identities'])
 write(HERE/'data/protocol.json',policy)
 history=historical_inventory();write(HERE/'data/historical_annotations.json',dict(records=history))
 hist_ids={r['scan_id'] for r in history if r['excludes_novelty']};hist_ids|={a['scan_id'] for a in q}
 inv=read(V7/'queue/inventory.json')['scans'];hist_keys={a.get('source_identity') for a in inv if a['scan_id'] in hist_ids};hist_keys.discard(None)
 eligible=[];audit=[];seen=set()
 for a in sorted(inv,key=lambda a:a['scan_id']):
  sid=a['scan_id'];reason=[];day=a.get('eligibility_day');ctx=exby.get(sid)
  if sid in hist_ids or a.get('source_identity') in hist_keys:reason.append('prior CNV supervision/review or full v8 correction queue')
  if a['animal']=='TS165' or day is None or float(day)<=7:reason.append('WT, prelaser, unknown day, or not post-day-7')
  if not ctx:reason.append('required final_output_v1 missing')
  elif ctx['excluded_from_analysis']:reason.append('known quality exclusion: '+ctx['exclusion_reason'])
  if not a.get('source_identity') or a.get('source_identity') in seen:reason.append('missing/duplicate source identity')
  if not Path(a['source']).is_file() or not (V6/'inputs'/(sid+'.json')).exists():reason.append('processed source/provider missing')
  if not reason:
   meta=read(V6/'inputs'/(sid+'.json'))
   if not meta.get('images') or not Path(meta['images']['path']).is_file():reason.append('validated native B-scan provider unavailable')
  if not reason:eligible.append(a);seen.add(a['source_identity'])
  audit.append(dict(scan_id=sid,eligible=not reason,reasons=reason,animal=a['animal'],day=day,day_basis=a.get('eligibility_day_basis'),source_identity=a.get('source_identity')))
 # Seeded round robin across animals, then visits, then repeats; metadata only.
 rng=random.Random(policy['selection_seed']);pools={}
 for animal in sorted({a['animal'] for a in eligible}):
  byvisit=defaultdict(list)
  for a in eligible:
   if a['animal']==animal:byvisit[a['session_date']].append(a)
  visits=sorted(byvisit);rng.shuffle(visits)
  for v in visits:rng.shuffle(byvisit[v])
  pool=[]
  while any(byvisit.values()):
   for v in visits:
    if byvisit[v]:pool.append(byvisit[v].pop())
  pools[animal]=pool
 reserve=[]
 while any(pools.values()):
  for animal in sorted(pools):
   if pools[animal]:reserve.append(pools[animal].pop(0))
 chosen=reserve[:50]
 for i,a in enumerate(chosen):a.update(queue_position=i+1,context_source=exby[a['scan_id']]['selection'],prior_vessel_review=exby[a['scan_id']]['vessel_reviewed'],prior_automatic_cnv_inference=True,prior_cnv_supervision=False,visit_group=f"{a['animal']}_{a['eye']}_{a['session_date']}")
 write(HERE/'data/selection.json',dict(seed=policy['selection_seed'],acquisitions=chosen,reserve=reserve[50:],shortfall=max(0,50-len(chosen)),policy='metadata only, post-day-7, animal/visit round robin, no model outputs inspected',replacements=[]))
 write(HERE/'data/eligibility.json',dict(records=audit,historical_inventory_sha256=sha(HERE/'data/historical_annotations.json')))
 for r in history:fps.append(r['source'])
 for f in list(V8.glob('*.py'))+[V8/'model1/config.json',V7/'queue/inventory.json',ROOT/'outputs/scan_index.csv']:fps.append(fingerprint(f))
 write(HERE/'data/preservation_before.json',dict(files=list({r['path']:r for r in fps}.values())))
 m=dict(records=records,omissions=omissions,source_counts=dict(counts),eligible_counts=dict(Counter(r['kind'] for r in records)),kept_regions=sum(len(r['regions']) for r in records),animals=sorted(animals),queue_sha256=sha(qpath),context_manifest_sha256=sha(EXPORT/'manifest.json'),protocol_sha256=sha(HERE/'data/protocol.json'),selection_sha256=sha(HERE/'data/selection.json'))
 write(mp,m);progress('Supervision and selection frozen',confirmed=len(records),regions=m['kept_regions'],selected=len(chosen),omissions=omissions);return m

if __name__=='__main__':
 with RunLock():freeze()
