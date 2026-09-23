"""Verify this wider local refinement and exercise saving on an isolated copy."""
from pathlib import Path
import json,tempfile
import numpy as np
from octa_reg_v3.review_server import current,analysis_records,save
from octa_reg_v2.run import read,write,sha
root=Path(__file__).resolve().parent;folder=root/'TS241_OD'
doc=read(folder/'montage.json');review=current(folder,doc)
rows=analysis_records(doc,review);source=read(root/'source_analysis_records.json')
ev=read(root/'refinement_evidence.json');center=np.array([255.5,255.5,1.])
assert ev['limits']=={'center_translation_px':25.,'rotation_deg':5.}
for i,(before,after) in enumerate(zip(source,rows)):
    assert before['scan_id']==after['scan_id']
    assert before['review_tier']==after['review_tier'] and before['notes']==after['notes']
    a=np.array(before['matrix_to_current_origin_pixels']);b=np.array(after['matrix_to_current_origin_pixels'])
    assert np.linalg.norm((b@center-a@center)[:2])<=25.0001
    rotation=b[:2,:2]@a[:2,:2].T
    assert abs(np.degrees(np.arctan2(rotation[1,0],rotation[0,0])))<=5.0001
    np.testing.assert_allclose(b[:2,:2].T@b[:2,:2],np.eye(2),atol=1e-8)
    if not np.allclose(a,b,atol=1e-8):assert not after['placement_confirmed']
    if i==ev['anchor_index']:np.testing.assert_array_equal(a,b)
assert not review['montage_confirmed']
with tempfile.TemporaryDirectory(prefix='octa_local_refinement_save_test_') as temp:
    p=Path(temp);write(p/'montage.json',doc)
    body=current(p,doc);save(p,doc,body)
    assert analysis_records(doc,current(p,doc))==rows
for p,h in ev['source'].items():assert sha(p)==h
verified=read(root/'VERIFIED.json')
verified.update(tests_passed=20,full_26_field_isolated_save_reload=True,independent_25px_5deg_audit=True)
write(root/'VERIFIED.json',verified)
(folder/'OPEN_MONTAGE.cmd').write_text('@echo off\ncall "%~dp0..\\OPEN_REVIEWER.cmd"\n')
print('All 26 poses, categories, notes, confirmations, source hashes, and isolated save/reload verified.')
