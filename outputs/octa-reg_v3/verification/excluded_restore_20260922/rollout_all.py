"""Update published reviewer controls only; preserve all saved review/data files."""
from pathlib import Path
import hashlib,json
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
targets=[]
for version,root in [('v2',ROOT/'outputs/octa-reg_v2/all_samples'),('v3',ROOT/'outputs/octa-reg_v3')]:
    source=ROOT/f'code/octa_reg_{version}/cohort_viewer.js'
    assert b'function restoreExcluded(' in source.read_bytes()
    for target in sorted(root.rglob('cohort_viewer.js')):
        if any(part in ('verification','development','reviewer_test') for part in target.relative_to(root).parts):continue
        if (target.parent/'montage.json').is_file():targets.append((version,source,target))
protected={str(p):digest(p) for _,_,target in targets for name in ('human_review.json','montage.json','data.js') if (p:=target.parent/name).is_file()}
result=[]
for version,source,target in targets:
    before=digest(target);payload=source.read_bytes();after=hashlib.sha256(payload).hexdigest()
    if before!=after:
        backup=OUT/'viewer_backups'/target.relative_to(ROOT/'outputs')
        backup.parent.mkdir(parents=True,exist_ok=True)
        if not backup.exists():backup.write_bytes(target.read_bytes())
        target.write_bytes(payload)
    assert digest(target)==after
    result.append(dict(version=version,path=str(target),changed=before!=after,sha256=after))
assert all(digest(Path(p))==h for p,h in protected.items()),'A data file changed during deployment; inspect before reporting.'
report=dict(at=datetime.now(timezone.utc).isoformat(),reviewers=len(result),updated=sum(r['changed'] for r in result),targets=result,unchanged_data_files=protected)
(OUT/'all_montages_rollout.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:report[k] for k in ('reviewers','updated')}))
print('All scripts match their tested source. Saved reviews, placements and data unchanged:',len(protected))
