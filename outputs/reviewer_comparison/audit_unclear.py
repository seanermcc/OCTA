"""Read-only audit of unclear marks in the comparison snapshot."""
import json
import hashlib
from pathlib import Path
import numpy as np

out=Path(__file__).parent
data=json.loads((out/'data.js').read_text(encoding='utf-8').removeprefix('window.COMPARISON = ').rstrip().removesuffix(';'))
totals={who:dict(points=0,unreliable=0,not_traceable=0,absent=0,unclear_union=0,unclear_scored=0,unclear_shichu_approved=0) for who in ['lead','shichu']}
cnv_totals=dict(points=0,unclear=0,unclear_scored=0,scans_with_region=0)
for c in data['cases']:
    if len(c['reviewers'])!=2:continue
    for who in totals:
        r=c['reviewers'][who]
        u=np.asarray(r['reliability'])==0
        t=np.asarray(r['trace'])==0
        a=np.asarray(r['anatomy'])==0
        denied=u|t
        z=totals[who]
        for key,value in [('points',u.size),('unreliable',u.sum()),('not_traceable',t.sum()),('absent',a.sum()),('unclear_union',denied.sum()),('unclear_scored',(denied&np.asarray(r['approved'])).sum())]:z[key]+=int(value)
        if who=='lead':z['unclear_shichu_approved']+=int((denied&np.asarray(c['reviewers']['shichu']['approved'])).sum())
        if who=='lead':
            print(c['id'],'lead unclear',int(denied.sum()),'of',u.size,'per boundary',dict(zip(data['names'],denied.sum(axis=1).tolist())))
            content=Path(r['source_path']).read_bytes()
            assert hashlib.sha256(content).hexdigest()==r['sha256'], 'Journal changed since snapshot'
            j=json.loads(content); ev=j['events'][:j['cursor']]
            confirmation=next((e for e in reversed(ev) if e['action']=='confirm_bscan'),{})
            region=np.zeros(c['width'],bool)
            for lo,hi in confirmation.get('lesion_snapshot',{}).get('cnv_region',[]):region[lo:hi]=True
            cnv_totals['points']+=int(region.sum())*8
            cnv_totals['scans_with_region']+=int(region.any())
            cnv_totals['unclear']+=int((denied&region[None]).sum())
            cnv_totals['unclear_scored']+=int((denied&region[None]&np.asarray(r['approved'])).sum())
print(json.dumps(totals,indent=2))
print('Inside lead CNV region',json.dumps(cnv_totals))
path=Path(next(c['reviewers']['lead']['source_path'] for c in data['cases'] if c['id'].endswith('s03_142449_b0045')))
j=json.loads(path.read_text());events=j['events'][:j['cursor']]
confirmation=next((e for e in reversed(events) if e['action']=='confirm_bscan'),{})
print('lesion snapshot keys',list(confirmation.get('lesion_snapshot',{})))
print('cnv_region',str(confirmation.get('lesion_snapshot',{}).get('cnv_region'))[:1000])
