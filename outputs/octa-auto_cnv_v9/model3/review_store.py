"""Version-bound, disk-backed human decisions for Model 2 / Model 3."""
from common import *
import threading
from datetime import datetime,timezone

class ReviewConflict(ValueError):pass

class ReviewStore:
 def __init__(self,gallery,directory):
  self.gallery=Path(gallery);self.directory=dest(directory);self.data=read(self.gallery/'data.json');self.cases={a['scan_id']:a for a in self.data['cases']};self.lock=threading.RLock()
 def contract(self,sid):
  if sid not in self.cases:raise ValueError('Unknown acquisition')
  a=self.cases[sid];path=self.gallery/'assets'/sid/'candidates.json';cs=read(path);models={}
  for model in ('m2','m3'):
   rows=[c for c in cs[model] if c['display_selected']];mask=np.zeros((512,512),bool)
   for c in rows:mask|=decode(c['runs'])
   models[model]=dict(candidate_ids=[c['id'] for c in rows],mask_sha256=hashlib.sha256(mask.tobytes()).hexdigest(),area_pixels=int(mask.sum()))
  contract=dict(scan_id=sid,source_identity=a['source_identity'],selection_sha256=self.data['selection_sha256'],candidate_file=fingerprint(path),models=models,predictions=a['status'],raw_pixel_threshold=.7,adjusted_candidate_threshold=.5,axis_order='B-scan,A-line',native_shape=[512,512])
  token=digest(dict(scan_id=sid,source_identity=a['source_identity'],candidates_sha256=contract['candidate_file']['sha256'],selection=contract['selection_sha256'],models=models,predictions=[(p['model'],p['prediction']['sha256'],p['checkpoint']['sha256']) for p in a['status']]))
  return contract,token
 def _head(self,sid,token):
  path=self.directory/'decisions'/(sid+'.json')
  if not path.exists():return dict(scan_id=sid,revision=0,token=token,confirm_m2=False,confirm_m3=False,no_cnv_present=False,review_model3=False,notes='')
  r=read(path)
  if r['token']!=token:raise ReviewConflict('Prediction version changed; reconcile saved review')
  return r
 def all(self):
  with self.lock:
   return dict(schema='cnv-v9-model3-review-v1',records={sid:self._head(sid,self.contract(sid)[1]) for sid in self.cases},scope='whole-field human confirmation; unchecked means unconfirmed')
 def queue(self):
  return dict(schema='cnv-v9-model3-correction-flags-v1',acquisitions=[r for r in self.all()['records'].values() if r['review_model3']],creates_no_annotations=True)
 def save(self,sid,payload):
  fields={'expected_revision','token','confirm_m2','confirm_m3','no_cnv_present','review_model3','notes'}
  if not isinstance(payload,dict) or set(payload)!=fields:raise ValueError('Invalid review fields')
  for k in ('confirm_m2','confirm_m3','no_cnv_present','review_model3'):
   if type(payload[k]) is not bool:raise ValueError('Checkboxes must be boolean')
  if type(payload['expected_revision']) is not int or payload['expected_revision']<0:raise ValueError('Invalid revision')
  if not isinstance(payload['notes'],str) or len(payload['notes'])>4000:raise ValueError('Invalid notes')
  if payload['confirm_m3'] and payload['review_model3']:raise ValueError('Model 3 confirmation conflicts with correction request')
  with self.lock:
   contract,token=self.contract(sid)
   if payload['token']!=token:raise ReviewConflict('Prediction changed; reload')
   old=self._head(sid,token)
   if old['revision']!=payload['expected_revision']:raise ReviewConflict('Review changed in another tab; reload')
   if payload['no_cnv_present'] and (payload['confirm_m2'] or payload['confirm_m3']):raise ValueError('Use no CNVs present as a separate whole-field verdict; clear model confirmations first')
   for status in contract['predictions']:
    verify(status['prediction']);verify(status['checkpoint'])
   state={k:payload[k] for k in fields-{'expected_revision','token'}}
   if old['revision'] and all(old[k]==v for k,v in state.items()):return old
   record=dict(schema='cnv-v9-model3-decision-v1',scan_id=sid,revision=old['revision']+1,token=token,**state,updated_at=datetime.now(timezone.utc).isoformat(),prediction_contract=contract,human_action='explicit browser checkbox/notes save',confirmation_scope='whole field; adjusted candidates only; no_cnv_present explicitly asserts entire assessable field has no CNVs',unchecked_meaning='unconfirmed, never negative',previous_revision_sha256=sha(self.directory/'decisions'/(sid+'.json')) if old['revision'] else None)
   history=self.directory/'history'/sid/f"{record['revision']:06d}.json"
   if history.exists():raise ReviewConflict('Interrupted revision exists; reconcile history before saving')
   write(history,record);write(self.directory/'decisions'/(sid+'.json'),record)
   return record
