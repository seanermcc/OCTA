"""Check every rendered footprint, selection accounting and source preservation."""
from build import HERE, read, sha, decode
import json
import numpy as np
from PIL import Image
from datetime import datetime, timezone

d=read(HERE/'gallery/data.json')
all_rows=d['cases']+d.get('secondary_cases',[])+d['excluded']
assert len({r['scan_id'] for r in all_rows})==324
assert len({r['source_identity'] for r in all_rows})==324
assert len({r['entry_id'] for r in all_rows})==len(all_rows)
for r in d['cases']:
    mask=decode(r['runs'])
    assert int(mask.sum())==r['pixels']>0
    assert __import__('hashlib').sha256(mask.tobytes()).hexdigest()==r['mask_sha256']
    folder=HERE/'gallery/assets'/r.get('asset_id',r['scan_id'])
    fill=np.array(Image.open(folder/'fill.png'))
    outline=np.array(Image.open(folder/'outline.png'))
    assert fill.shape==outline.shape==(512,512,4)
    assert np.array_equal(fill[:,:,3]>0,mask)
    assert not ((outline[:,:,3]>0)&~mask).any()
    assert (outline[:,:,3]>0).any()
    assert Image.open(folder/'structural.png').size==(512,512)
    assert not r['original_decision']['no_cnv_present']
    if r['source']=='m2': assert r['original_decision']['confirm_m2'] and not r['original_decision']['confirm_m3']
    if r['source']=='m3': assert r['original_decision']['confirm_m3']
    if r['source']=='m3_corrected':
        correction=read(r['original_label']['path'])
        assert correction['kind']=='positive'
        assert np.array_equal(decode(correction['masks']['positive']),mask)
for r in d.get('secondary_cases',[]):
    assert r['source'] in ('no_cnv','deferred') and not r['runs']
    assert Image.open(HERE/'gallery/assets'/r['asset_id']/'structural.png').size==(512,512)
for p,h in d['source_hashes'].items(): assert sha(p)==h, 'Changed source: '+p
result=dict(verified_at=datetime.now(timezone.utc).isoformat(),passed=True,inventory=324,displayed=len(d['cases']),rendered_assets_checked=len(d['cases'])*3+len(d.get('secondary_cases',[])),source_files_unchanged=len(d['source_hashes']),summary=d['summary'],checks=['All 324 source identities accounted; training/correction overlap explicitly separate','All displayed CNV masks nonempty','Every fill raster equals the selected native mask','Outlines stay inside their selected native mask','All Structural OCT images and overlays share the 512 x 512 grid','All corrected masks equal saved confirmed correction targets','All snapshotted source files remain unchanged'],assessment_scope='Interface and provenance verification; no new biological quality judgments.')
(HERE/'VERIFIED.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print(json.dumps(result,indent=2))
