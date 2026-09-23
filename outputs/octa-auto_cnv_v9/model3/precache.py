"""Prepare inference-only inputs while GPU fits consume already-frozen training caches."""
from common import *
from run_pipeline import prepare
from media import run as media
training={r['scan_id'] for r in read(HERE/'data/supervision.json')['records']}
cases=read(HERE/'data/selection.json')['acquisitions']
for i,a in enumerate(cases):
 if a['scan_id'] not in training:prepare(a)
 write(HERE/'precache_progress.json',dict(completed=i+1,total=len(cases),scan_id=a['scan_id']))
 if (i+1)%20==0:print(json.dumps(dict(prepared=i+1,total=len(cases))),flush=True)
media()
write(HERE/'PRECACHE_COMPLETE.json',dict(acquisitions=len(cases)))
