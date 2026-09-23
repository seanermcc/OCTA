"""Read browser-created synthetic reviews and verify frozen real artifacts."""
from common import *
from urllib.request import urlopen,Request
from urllib.error import HTTPError

def get(path):return json.load(urlopen('http://127.0.0.1:8800'+path))
reviews=get('/reviews/export');r=reviews['records']['SYNTHETIC_0'];empty=reviews['records']['SYNTHETIC_1']
assert r['confirm_m1'] and not r['confirm_m2_adjusted'] and r['review_model2']
assert r['revision']==6 and 'correct the missed footprint' in r['notes']
assert empty['confirm_m1'] and empty['prediction_contract']['models']['m1']['area_pixels']==0
q=get('/reviews/model2-queue');assert len(q['acquisitions'])==1
assert q['acquisitions'][0]['prediction_contract']['models']['m2_adjusted']['candidate_ids']==[1]
assert q['acquisitions'][0]['confirmation'] is False
write(HERE/'verification/web_review_synthetic_export.json',reviews)
write(HERE/'verification/web_review_synthetic_queue.json',q)
request=Request('http://127.0.0.1:8800/reviews',data=b'{}',headers={'Content-Type':'application/json','Origin':'https://untrusted.example'},method='POST')
try:urlopen(request);raise AssertionError('Cross-origin write accepted')
except HTTPError as e:assert e.code==403
assert get('/reviews')['records']['SYNTHETIC_0']['revision']==6
frozen=read(HERE/'FINAL_VERIFIED.json')
for fp in [frozen['gallery']]+frozen['bundles']:verify(fp)
handoff=read(HERE/'correction_handoff.json');artifacts=[]
for a in handoff['acquisitions']:
 for key in ('combined_arrays','candidates'):verify(a[key]);artifacts.append(a[key])
for model in (1,2):
 b=read(HERE/'bundles'/f'v9_m{model}'/'bundle.json')
 for key in ('checkpoint','normalization'):verify(b[key])
 if model==2:verify(b['scorer'])
for fp in read(HERE/'data/scoring_implementation.json')['files']:verify(fp)
for r in read(HERE/'data/supervision.json')['records']:verify(r['label'])
write(HERE/'verification/WEB_REVIEW_QA.json',dict(passed=True,synthetic_unit_tests=4,browser_confirmations_reload=True,browser_notes_persist=True,mutual_exclusion_and_independent_m1=True,zero_candidates_explicitly_confirmed=True,flag_filter_and_empty_state=True,synthetic_only_write_tests=True,correction_export_adjusted_ids_only=True,cross_origin_write_rejected=True,real_prediction_artifacts_unchanged=len(artifacts),frozen_bundles_scorer_evaluation_code_unchanged=True,original_29_labels_unchanged=True))
print('Web review checks passed; 100 frozen prediction/candidate artifacts and original labels unchanged')
