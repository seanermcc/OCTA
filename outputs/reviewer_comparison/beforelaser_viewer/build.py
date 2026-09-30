"""Create a standalone, read-only four-case viewer from verified saved reviews."""
import hashlib,json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
data=json.loads((BASE/'data.js').read_text(encoding='utf-8').removeprefix('window.COMPARISON = ').strip().removesuffix(';'))
cases=[]
expected={('TS247_OD_2024-10-17_beforelaser_s11_121207',234),('TS247_OD_2024-10-17_beforelaser_s11_121207',411),('TS247_OD_2024-10-17_beforelaser_s11_121207',422),('TS247_OD_2024-10-17_beforelaser_s12_121821',330)}
for c in data['cases']:
    if (c['scan_id'],c['bscan']) not in expected:continue
    r=c['reviewers']['shichu']
    raw=Path(r['source_path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==r['sha256'],'Journal changed; refresh comparison first'
    j=json.loads(raw);assert r['status']=='Confirmed'
    confirmation=next(e for e in reversed(j['events'][:j['cursor']]) if e['action']=='confirm_bscan')
    ls=confirmation['lesion_snapshot']
    assert ls['shape']==[c['depth'],c['width']]
    cases.append(dict(id=c['id'],scan=c['scan_id'],bscan=c['bscan'],offset=c['offset'],width=c['width'],depth=c['depth'],
                      image=c['image_data'],positions=r['positions'],approved=r['approved'],lesion=ls,
                      notes=r['notes'],revision=r['revision'],sha256=r['sha256'],source_path=r['source_path']))
assert len(cases)==4
payload=json.dumps(dict(names=data['names'],cases=cases),separators=(',',':'),allow_nan=False).replace('</','<\\/')
template=(HERE/'viewer.html').read_text(encoding='utf-8')
(HERE/'index.html').write_text(template.replace('/*DATA*/',payload),encoding='utf-8')
print('Verified four current Shichu journal hashes; wrote',HERE/'index.html')
