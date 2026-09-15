"""Repair only a verified identical-content mmap-close timestamp discrepancy."""
from batch import *
audit_path=OUT/'verification/mmap_timestamp_repairs.json'
repairs=read(audit_path) if audit_path.exists() else []
for p in (OUT/'volumes').glob('*/prepared.json'):
    d=read(p);old=d['images_fingerprint'];current=fingerprint(old['path'])
    if old==current:continue
    assert old['sha256']==current['sha256'] and old['bytes']==current['bytes'] and old['path']==current['path']
    repairs.append(dict(old=old,current=current,reason='Windows finalized mmap file timestamp on closing; full contents identical'))
    d['images_fingerprint']=current;write(p,d)
write(audit_path,repairs)
print('Verified identical-content timestamp repairs:',len(repairs))
