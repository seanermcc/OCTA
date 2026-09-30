"""Build a read-only standalone viewer of the four flagged lead confirmations."""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
ROOT = BASE.parents[1]
sys.path.insert(0, str(ROOT/'code'))
from reviewer_compare.build import load_review, digest, safe
from octa_seg_v3.feedback import resolve
from octa_seg_v3 import lesions as L
data = json.loads((BASE/'data.js').read_text(encoding='utf-8').removeprefix('window.COMPARISON = ').strip().removesuffix(';'))
expected = {
    ('TS247_OD_2024-11-20_D35_s03_113903', 184),
    ('TS250_OD_2026-03-20_D24_s04_143137', 64),
    ('TS250_OD_2026-03-20_D24_s04_143137', 260),
    ('TS250_OD_2026-03-23_D27_s01_112447', 380),
}
cases = []
for c in data['cases']:
    if (c['scan_id'], c['bscan']) not in expected:
        continue
    old = c['reviewers']['lead']
    source = Path(old['source_path'])
    raw = source.read_bytes()
    j = json.loads(raw)
    assert j['reviewer_id'] == 'lead' and j['scan_id'] == c['scan_id'] and j['bscan'] == c['bscan']
    candidates = [Path('F:/octa/For_Segmentation')/folder/c['scan_id'] for folder in ('Reviewed_Samples','More_Samples')]
    provider_path = next(p for p in candidates if (p/'prepared.json').exists())
    prep = json.loads((provider_path/'prepared.json').read_text(encoding='utf-8-sig'))
    with np.load(provider_path/'measurements.npz', allow_pickle=False) as z:
        row=c['bscan']; baseline=z['raw_position_branch'][row]; shadow=z['shadow'][row]; vessel=z['vessel'][row]; offset=int(z['label_offset'])
    if (provider_path/'context.npz').exists():
        with np.load(provider_path/'context.npz', allow_pickle=False) as z: vessel=vessel|z['vessel'][row].astype(bool)
    provider_sha=digest(provider_path/'measurements.npz')
    assert provider_sha == json.loads(Path(old['source_path']).read_text(encoding='utf-8'))['source']['provider_sha256']
    assert offset==c['offset']
    r = load_review((source,j,hashlib.sha256(raw).hexdigest()),dict(sha=provider_sha,prep=prep),baseline,shadow,vessel,offset,j['source']['image_shape'])
    resolved=resolve(j['events'][:j['cursor']],baseline,offset,c['depth'])
    ls = L.snapshot(resolved['lesions'])
    assert ls['shape'] == [c['depth'], c['width']]
    cases.append(dict(id=c['id'], scan=c['scan_id'], bscan=c['bscan'], offset=c['offset'],
                      width=c['width'], depth=c['depth'], image=c['image_data'], positions=r['positions'],
                      approved=r['approved'], lesion=ls, notes=r['notes'], revision=r['revision'],
                      sha256=r['sha256'], source_path=r['source_path'], status=r['status']))
assert len(cases) == 4
template = (BASE/'beforelaser_viewer/viewer.html').read_text(encoding='utf-8')
template = template.replace('Shichu · four beforelaser cases', 'Lead · four reviews flagged for a missing CNV region')
template = template.replace('Saved CNV-positive annotations on TS247 OD acquisitions dated October 17, 2024. “Beforelaser” is the acquisition name; laser history and lesion identity remain to be checked.',
    'These four lead reviews were flagged for saved CNV edge and/or Hyper_Ref annotations without a CNV region. The viewer shows their latest saved state, including any subsequent corrections.')
template = template.replace('Shichu', 'lead')
template = template.replace('</style>', '@media(min-width:720px) and (max-width:950px){.panes{grid-template-columns:1fr 1fr}canvas{height:340px}}\n</style>')
template = template.replace('<button id="full">Full image</button>', '<button id="full">Full image</button><button id="focus">Focus annotations</button>')
template = template.replace('<div id="status">', '<p id="regionNotice" style="color:#ffd18b"></p><div id="status">')
template = template.replace('lead · confirmed annotations', 'lead · saved annotations')
template = template.replace('Confirmed by lead', '${q.status} · lead')
template = template.replace("$('meta').replaceChildren();", "$('regionNotice').textContent=region===0?'CNV region: empty in this save. No pink shading is expected; an empty region does not establish biological absence.':'A CNV region is now present in this save; the earlier missing-region flag may have been addressed.';$('meta').replaceChildren();")
template = template.replace('lesion annotations come from the matching confirmation snapshot', 'lesion annotations come from authoritative replay of the current saved journal')
template = template.replace("${q.scan.includes('_s11_')?'Acquisition s11':'Acquisition s12'}", "${q.scan.split('_')[0]} · ${q.scan.split('_')[3]} · ${q.scan.split('_')[4]}")
template = template.replace("$('prev').onclick=", """$('focus').onclick=()=>{const q=c(),xs=[],ys=[];q.lesion.cnv_edge.forEach((v,x)=>{if(v!==null){xs.push(x);ys.push(v-q.offset)}});for(const [lo,hi] of q.lesion.hyper_ref_runs){xs.push(lo%q.width,(hi-1)%q.width);ys.push(Math.floor(lo/q.width),Math.floor((hi-1)/q.width))}if(!xs.length){fit();return}const left=Math.max(0,Math.min(...xs)-25),right=Math.min(q.width,Math.max(...xs)+25),top=Math.max(0,Math.min(...ys)-35),bottom=Math.min(q.depth,Math.max(...ys)+35),r=panes[0].getBoundingClientRect();center={x:(left+right)/2,y:(top+bottom)/2};scale=Math.min((r.width-24)/((right-left)*aspect),(r.height-24)/(bottom-top));draw()};
$('prev').onclick=""")
template = template.replace("img.src=q.image}", "img.onerror=()=>{$('status').textContent='Image could not be loaded.'};img.src=q.image}")
payload = json.dumps(safe(dict(names=data['names'], cases=cases)), separators=(',', ':'), allow_nan=False).replace('</', '<\\/')
(HERE/'viewer.html').write_text(template, encoding='utf-8')
(HERE/'index.html').write_text(template.replace('/*DATA*/', payload), encoding='utf-8')
summary = []
for c in cases:
    assert hashlib.sha256(Path(c['source_path']).read_bytes()).hexdigest() == c['sha256']
    ls = c['lesion']
    summary.append(dict(case=c['id'],status=c['status'], region_columns=sum(hi-lo for lo,hi in ls['cnv_region']),
                        saved_edge_columns=sum(v is not None for v in ls['cnv_edge']),
                        hyper_ref_pixels=sum(hi-lo for lo,hi in ls['hyper_ref_runs']),
                        revision=c['revision'], source_path=c['source_path'], sha256=c['sha256']))
(HERE/'verification.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
(HERE/'OPEN_VIEWER.cmd').write_text('@echo off\nstart "" "%~dp0index.html"\n', encoding='utf-8')
print(json.dumps(summary, indent=2))
