"""Read-only inventory of current journals; no label writers are called."""
from pathlib import Path
import collections
import hashlib
import json
import sys

ROOT = Path('D:/Projects/octa')
PROJECT = Path('F:/octa/Full/_Project')
sys.path.insert(0, str(PROJECT/'outputs/octa-seg/octa-seg_v3/review/code'))
from octa_seg_v3.saved import describe

roots = [Path('F:/octa/For_Segmentation/Reviews/reviewers/lead'),
         Path('F:/octa/reviewers/lead'), Path('E:/reviewers/lead'),
         ROOT/'outputs/octa-seg/octa-seg_v3/review/reviewers/lead',
         ROOT/'outputs/octa-seg/octa-seg_v3/reviewers/lead',
         ROOT/'outputs/portable_seg_20260923/outputs/octa-seg/octa-seg_v3/review/reviewers/lead']
report = []
for root in roots:
    rows = [describe(p) for p in sorted((root/'journals').glob('*.json'))]
    report.append(dict(root=str(root), exists=root.exists(), journals=len(rows),
        statuses=dict(collections.Counter(r['status'] for r in rows if r['work'])),
        confirmed_volumes=len({r['scan_id'] for r in rows if r['status']=='Confirmed'}),
        empty_or_tags_only=sum(not r['work'] for r in rows),
        cases=[{k:r[k] for k in ('scan_id','bscan','status','work','meta','path')} for r in rows]))
manifest = json.loads((PROJECT/'PORTABLE_CACHE.json').read_text())
live = report[0]['cases']
current = {(r['scan_id'],r['bscan']):r for r in live}
additional = {}
for group in report[1:]:
    for r in group['cases']:
        key = (r['scan_id'],r['bscan'])
        if r['work'] and key not in current:
            additional.setdefault(str(key), []).append(r)
result = dict(stores=report, additional_cases=additional,
    unavailable_confirmed=[r for r in live if r['status']=='Confirmed' and r['scan_id'] not in manifest['scans']])
(Path(__file__).parent/'inventory.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
hashes = {str(p):hashlib.sha256(p.read_bytes()).hexdigest()
          for root in (Path('F:/octa/For_Segmentation/Reviews/reviewers'),Path('F:/octa/reviewers'))
          for pattern in ('*/journals/*.json', '*/surface_labels/*.npz', '*/surface_context/*.npz')
          for p in root.glob(pattern) if p.is_file()}
target = Path(__file__).parent/'human_files_before.json'
if not target.exists(): target.write_text(json.dumps(hashes, indent=2))
print(json.dumps(dict(stores=[{k:v for k,v in g.items() if k!='cases'} for g in report],
                     additional_cases=len(additional), unavailable_confirmed=len(result['unavailable_confirmed'])), indent=2))
