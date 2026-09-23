"""Build a source-verified display snapshot; never modify source human records."""
from pathlib import Path
import collections
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
MODEL = HERE.parent / 'model3'
_paths = sys.path[:]
sys.path.insert(0, str(MODEL))
from common import decode, encode, digest
from review_store import ReviewStore
sys.path[:] = _paths
import numpy as np
from PIL import Image
from scipy.ndimage import binary_erosion

def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def choose(training, decision):
    """Training references are independent of subsequent model-only judgments."""
    if decision.get('no_cnv_present'):
        return 'excluded', 'confirmed_no_cnv'
    if training:
        return ('manual', 'training_reference') if training['kind'] == 'positive' else ('excluded', 'training_no_cnv')
    if decision.get('confirm_m3'):
        return 'm3', 'both_confirmed_prefer_m3' if decision.get('confirm_m2') else 'confirmed_m3'
    if decision.get('confirm_m2'):
        return 'm2', 'confirmed_m2_review_m3' if decision.get('review_model3') else 'confirmed_m2'
    return 'excluded', 'correction_review' if decision.get('review_model3') else 'unconfirmed'

def build():
    inputs = {}
    def checked(p, expected=None):
        p = Path(p); h = sha(p)
        if expected and h != expected:
            raise ValueError('Source hash mismatch: ' + str(p))
        inputs[str(p)] = h
        return h
    def verify(fp):
        if fp['path'] not in inputs:
            checked(fp['path'], fp['sha256'])
        elif inputs[fp['path']] != fp['sha256']:
            raise ValueError('Conflicting source fingerprints')
    gallery = MODEL / 'gallery'
    checked(gallery/'data.json'); checked(MODEL/'data/supervision.json')
    data = read(gallery/'data.json')
    training = {r['scan_id']: r for r in read(MODEL/'data/supervision.json')['records']}
    store = object.__new__(ReviewStore)
    store.gallery = gallery; store.data = data; store.cases = {a['scan_id']: a for a in data['cases']}
    cases, excluded = [], []
    for a in sorted(data['cases'], key=lambda a:(a['animal'],a['eye'],a['session_date'],a['scan_id'])):
        sid = a['scan_id']; t = training.get(sid)
        dp = MODEL/'manual_review/decisions'/(sid+'.json')
        d = read(dp) if dp.exists() else {}
        if d:
            checked(dp)
            contract, token = store.contract(sid)
            assert d['token'] == token and contract['models'] == d['prediction_contract']['models'], sid
            assert not (d['confirm_m3'] and d['review_model3']), sid
            for pred in contract['predictions']:
                verify(pred['prediction']); verify(pred['checkpoint'])
        source, reason = choose(t, d)
        meta = {k:a.get(k,'') for k in ('scan_id','animal','eye','session_date','scan_no','day_label','days_post_laser','day_basis','source_identity')}
        meta.update(source=source, selection_reason=reason, original_decision={k:d.get(k) for k in ('revision','confirm_m2','confirm_m3','no_cnv_present','review_model3','notes')})
        if source == 'excluded':
            excluded.append(meta); continue
        cp = gallery/'assets'/sid/'candidates.json'; checked(cp)
        if source == 'manual':
            verify(t['target_file'])
            with np.load(t['target_file']['path'],allow_pickle=False) as z:
                mask = z['target'].astype(bool); ignored = z['ignored'].astype(bool)
                assert str(z['scan_id']) == sid and str(z['axis_order']) == 'B-scan,A-line'
                assert np.array_equal(z['instances'].any(0), mask)
                regions = len(z['instances'])
            assert t['acquisition']['source_identity'] == a['source_identity']
            assert mask.sum() == t['positive_pixels'] and not (mask & ignored).any()
            meta.update(source_label='Manual / training', source_version=t['source_version'], reference_provenance=t['target_file'], original_label=t['label'], ignored_pixels=int(ignored.sum()))
        else:
            selected = [c for c in read(cp)[source] if c['display_selected']]
            mask = np.zeros((512,512),bool)
            for c in selected: mask |= decode(c['runs'])
            assert hashlib.sha256(mask.tobytes()).hexdigest() == d['prediction_contract']['models'][source]['mask_sha256']
            assert int(mask.sum()) == d['prediction_contract']['models'][source]['area_pixels']
            regions = len(selected)
            meta.update(source_label='Model '+source[-1], reference_provenance={'path':str(cp),'sha256':inputs[str(cp)]}, original_label={'path':str(dp),'sha256':inputs[str(dp)]}, ignored_pixels=0)
        if not mask.any():
            meta.update(selection_reason='confirmed_empty_model'); excluded.append(meta); continue
        assert mask.shape == (512,512)
        assets = HERE/'gallery/assets'/sid; assets.mkdir(parents=True,exist_ok=True)
        original = gallery/'assets'/sid/'structural.png'
        media = read(gallery/'assets'/sid/'media.json')
        fp = next(f for f in media['outputs'] if Path(f['path']).name=='structural.png')
        checked(original,fp['sha256'])
        assert Image.open(original).size == (512,512)
        shutil.copyfile(original,assets/'structural.png')
        edge = mask & ~binary_erosion(mask, iterations=2)
        for name, alpha in [('outline',0),('fill',62)]:
            rgba = np.zeros((512,512,4),np.uint8)
            rgba[mask] = (255,211,65,alpha); rgba[edge] = (255,211,65,255)
            Image.fromarray(rgba).save(assets/(name+'.png'))
        meta.update(regions=regions, pixels=int(mask.sum()), mask_sha256=hashlib.sha256(mask.tobytes()).hexdigest(), runs=encode(mask), final_status='final_good', assessment_status='unassessed')
        meta['token'] = digest({k:meta[k] for k in ('scan_id','source_identity','source','mask_sha256','reference_provenance','original_label')})
        cases.append(meta)
    assert len({r['source_identity'] for r in cases}) == len(cases)
    # Refuse a mixed snapshot if reviews were edited while building.
    for p,h in inputs.items():
        assert sha(p) == h, 'Source changed during build: '+p
    summary = dict(inventory=len(data['cases']), displayed=len(cases), by_source=dict(collections.Counter(r['source'] for r in cases)), excluded=dict(collections.Counter(r['selection_reason'] for r in excluded)), model2_good_despite_model3_review=sum(r['selection_reason']=='confirmed_m2_review_m3' for r in cases), both_confirmed_using_model3=sum(r['selection_reason']=='both_confirmed_prefer_m3' for r in cases))
    doc = dict(schema='cnv-final-assessment-v1',created_at=datetime.now(timezone.utc).isoformat(), summary=summary, cases=cases, excluded=excluded, source_hashes=inputs, policy='Frozen manual training references; otherwise confirmed Model 3 preferred to confirmed Model 2. Model 2 confirmation plus Model 3 review is final/good. Standalone model correction flags excluded. No-CNV samples excluded. New assessment flags do not alter original approvals or training labels.')
    (HERE/'gallery/data.json').write_text(json.dumps(doc,indent=2),encoding='utf8')
    (HERE/'BUILD_REPORT.json').write_text(json.dumps({k:v for k,v in doc.items() if k!='cases'},indent=2),encoding='utf8')
    print(json.dumps(summary,indent=2))

if __name__ == '__main__': build()
