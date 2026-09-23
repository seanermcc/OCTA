"""Evaluate completed development fits independently of final GPU training."""
from common import *
from deliver import development

for fp in read(HERE/'data/scoring_implementation.json')['files']:verify(fp)
protocol=read(HERE/'data/protocol.json')
for f in protocol['folds']:
 for name in [f"outer{f['fold']}_m1",f"outer{f['fold']}_m2"]+[f"outer{f['fold']}_inner{j}_m2" for j in (0,1)]:
  d=read(HERE/'fits'/name/'complete.json');assert d['completed_epochs']==100;verify(d['checkpoint'])
results,scorer=development(read(HERE/'data/supervision.json'),protocol)
print(json.dumps({k:v['overall'] for k,v in results.items()},indent=2))
print(json.dumps({k:scorer[k] for k in ('fitted','training_examples','ignored_examples','class_counts','supported_area_pixels')},indent=2))
