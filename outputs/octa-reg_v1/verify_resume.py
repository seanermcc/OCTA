"""Exercise resume and changed-cache invalidation on isolated copies, never upstream."""
from pathlib import Path
import sys
import shutil
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'code'))
from octa_reg_v1 import CONFIG
from octa_reg_v1.io import read,write,save,sha,DEFAULT_INVENTORY,DEFAULT_EXPORT
from octa_reg_v1.pipeline import run

out=Path(__file__).resolve().parent/'verification'/'resume_fixture'
source=out/'source';(source/'inputs').mkdir(parents=True,exist_ok=True)
rows=sorted([r for r in read(DEFAULT_INVENTORY)['scans'] if r['animal']=='TS165' and r['eye']=='OD'],key=lambda r:r['scan_id'])[:2]
write(source/'inventory.json',{'scans':rows})
for r in rows:
    sid=r['scan_id']
    for suffix in ('.json','.npz'):shutil.copyfile(DEFAULT_INVENTORY.parent/'inputs'/(sid+suffix),source/'inputs'/(sid+suffix))
target=out/'run'
run(target,source/'inventory.json',DEFAULT_EXPORT,CONFIG)
pair_id=rows[0]['scan_id']+'__'+rows[1]['scan_id']
first=read(target/'pairs'/(pair_id+'.json'))
run(target,source/'inventory.json',DEFAULT_EXPORT,CONFIG)
assert read(target/'status.json')['pairs_resumed']==1
second=read(target/'pairs'/(pair_id+'.json'));assert first==second
cache=source/'inputs'/(rows[0]['scan_id']+'.npz')
with np.load(cache,allow_pickle=False) as z:optical=z['optical'].copy()
optical[0,0,0]+=1
save(cache,optical=optical)
side=read(cache.with_suffix('.json'));side['optical_cache']['sha256']=sha(cache);write(cache.with_suffix('.json'),side)
run(target,source/'inventory.json',DEFAULT_EXPORT,CONFIG)
third=read(target/'pairs'/(pair_id+'.json'))
assert read(target/'status.json')['pairs_resumed']==0
assert third['signature']!=second['signature']
write(out.parent/'resume_invalidation.json',dict(passed=True,unchanged_pair_reused=True,unchanged_artifact_identical=True,
    changed_optical_hash_invalidated=True,fixture='isolated copies of two TS165_OD caches and sidecars',upstream_modified=False,
    original_signature=first['signature'],changed_signature=third['signature']))
print('PASS: identical pair resumed; changed optical hash invalidated it; upstream unchanged')
