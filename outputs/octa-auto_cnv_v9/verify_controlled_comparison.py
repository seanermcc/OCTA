"""Cross-model parity and missing-pool audits independent of metric calculations."""
from common import *
from collections import Counter
reports=[]
for stem in ('outer0','outer1','outer2','final'):
 folders=[HERE/'fits'/f'{stem}_m{model}' for model in (1,2)]
 a,b=[read(f/'normalization.json') for f in folders]
 assert a==b,stem+': unequal baseline normalization'
 da,db=[read(f/'complete.json') for f in folders]
 assert da['sampling_counts']==db['sampling_counts'],stem+': unequal sampling'
 for d in (da,db):
  c=d['sampling_counts'];assert sum(v for k,v in c.items() if k.startswith('animal:'))==12800
  assert c['requested:positive']==6400 and c['requested:background']==3200 and c['requested:hard']==3200
 reports.append(dict(fit=stem,baseline_normalization_equal=True,sampling_equal=True,patches_per_model=12800,actual=dict((k,v) for k,v in da['sampling_counts'].items() if k.startswith(('actual:','fallback:'))),animal_patches={k:v for k,v in da['sampling_counts'].items() if k.startswith('animal:')}))
write(HERE/'verification/CONTROLLED_COMPARISON_QA.json',dict(passed=True,records=reports))
print('Identical normalization and 12800 sampled patches per paired fit verified')
