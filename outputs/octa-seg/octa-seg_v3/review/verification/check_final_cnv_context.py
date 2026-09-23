"""Read-only cohort and Qt integration checks; no human annotation writes."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[3]
sys.dont_write_bytecode = True
sys.path[:0] = [str(HERE/'code'), str(HERE.parent.parent/'octa-seg_v2/code'), str(ROOT/'code')]
import copy
import json
import hashlib
from collections import Counter
from types import SimpleNamespace
from unittest.mock import patch
import unittest
import numpy as np
from octa_seg_v3 import cnv_context as C
from octa_seg_v3.common import read, fingerprint
from octa_seg_v3.data import local_path, discover, load_volume, VolumeCache
from octa_seg_v3.gui import Window, Navigator, configure_v3_app
from octa_seg_v3.label_gui import QtWidgets, QtCore, QtGui
from octa_seg_v3.verify import fixture
from octa_seg_v3.providers import saved_cnv, context_overlays


def volume_for(source):
    return SimpleNamespace(scan=SimpleNamespace(scan_id=source['scan_id'],
        source_volume=local_path(source['source']), native_shape=tuple(source['native_shape'])))


def run():
    out = HERE/'verification/final_cnv_context'
    out.mkdir(parents=True, exist_ok=True)
    doc, records = C.index(C.FINAL/'dataset/manifest.json', 'records')
    _, sources = C.index(C.GALLERY, 'cases')
    counts = Counter()
    for sid, record in records.items():
        mask, meta = C.load_final_cnv(volume_for(sources[sid]))
        assert mask.shape == (512, 512) and mask.dtype == np.bool_
        counts[record['status']] += 1
        if record['status'] == 'confirmed_positive':
            assert mask.any()
            if not (C.FINAL/'review/regions'/f'{sid}.json').exists():
                with np.load(local_path(record['targets']['path'])) as z:
                    np.testing.assert_array_equal(mask, z['target'])
        elif record['status'] in ('confirmed_negative', 'excluded_poor_image'):
            assert not mask.any()
    print('Native cohort masks:', dict(counts), flush=True)

    sid = next(s for s, r in records.items() if r['status'] == 'confirmed_positive')
    volume = volume_for(sources[sid])
    live_path = C.FINAL/'review/regions'/f'{sid}.json'
    real_exists = Path.exists
    simulated = dict(schema='cnv-final-correction-v9.1', synthetic=False, scan_id=sid,
        source_identity=records[sid]['source_identity'], native_shape=[512,512],
        axis_order='B-scan,A-line', revision=9,
        state=dict(regions=[dict(state='draft', runs=[[255, 10, 25]]),
                            dict(state='kept', runs=[[256, 30, 50]]),
                            dict(state='unsure', runs=[[256, 35, 40]])],
                   absence=False, confirmation=None, defer_reason=''),
        masks=dict(positive=[[256,30,35],[256,40,50]], ignored=[[256,35,40]]))
    def mocked_read(path):
        return copy.deepcopy(simulated) if Path(path) == live_path else read(path)
    with patch.object(Path, 'exists', lambda p: True if p == live_path else real_exists(p)), patch.object(C, 'read', mocked_read), patch.object(C, 'fingerprint', lambda p: 'in-memory-test' if Path(p) == live_path else fingerprint(p)):
        mask, meta = saved_cnv(volume)
        assert mask.sum() == 30 and mask[255,10:25].all() and not mask[256,35:40].any()
        assert 'draft' in meta['status']
        assert live_path in C.signature_paths(sid)
        simulated['state'] = dict(regions=[], absence=True, confirmation=None, defer_reason='')
        simulated['masks'] = dict(positive=[], ignored=[])
        state = simulated['state']
        digest = hashlib.sha256(json.dumps({k:state[k] for k in ('regions','absence')},sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        state['confirmation'] = dict(whole_field_checked=True, annotation_sha256=digest)
        mask, meta = saved_cnv(volume)
        assert not mask.any() and 'confirmed' in meta['status'] and 'no CNV' in meta['status']
        simulated['axis_order'] = 'A-line,B-scan'
        try: saved_cnv(volume)
        except ValueError: pass
        else: raise AssertionError('Axis mismatch accepted')
    bad = volume_for(sources[sid]); bad.scan.native_shape = (511,512)
    try: C.load_final_cnv(bad)
    except ValueError: pass
    else: raise AssertionError('Grid mismatch accepted')
    print('Live draft/absence precedence, ignored pixels, and source/grid rejection passed', flush=True)

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    configure_v3_app(app)
    v = fixture(out)
    mask = np.zeros((512,512), bool)
    mask[250:261,100:140] = True
    mask[256,170:172] = True
    v.overlays = (mask,) + v.overlays[1:]
    cache = VolumeCache([v.entry], max_bytes=1024**3, loader=lambda entry, image_budget: v)
    w = Window('cnv_context_verify', entries=[v.entry], output=out/'synthetic_view',
               autoload=False, cache=cache, read_only=True)
    with patch('octa_seg_v3.providers.context_overlays', return_value=v.overlays):
        w.install_volume(v, 0, 256, cached=True)
    w.resize(1650,950); w.show(); app.processEvents(); w.fit(); app.processEvents()
    image = w.navigator._overlay.pixmap().toImage()
    color = QtGui.QColor(C.PINK)
    assert image.pixelColor(110,255).alpha() == 30
    assert image.pixelColor(100,255).alpha() == 240
    assert image.pixelColor(100,255).red() == color.red()
    assert image.pixelColor(90,255).alpha() == 0
    def check_row(row):
        w.navigate(row); app.processEvents()
        fill = next(i for i in w.editor._extras if i.data(0) == 'cnv_context_fill')
        for x in range(512):
            for y in (1, 128, 255):
                assert fill.path().contains(QtCore.QPointF(x,y)) == bool(mask[row,x]), (row,x,y)
    for row in (249,250,256,260,261,256): check_row(row)
    w.grab().save(str(out/'synthetic_alignment.png'))
    assert not list((out/'synthetic_view').rglob('*__b*.json'))
    w.close(); app.processEvents()
    print('Qt outline/fill and exact full-depth row projection passed', flush=True)

    # Real source/geometry and visual verification in read-only mode.
    entries = {e['scan_id']:e for e in discover()}
    real_sid = next(s for s, r in records.items() if r['status']=='confirmed_positive' and s in entries)
    real = load_volume(entries[real_sid], image_budget=0)
    overlay = C.load_final_cnv(real)[0]
    row = int(np.argmax(overlay.sum(axis=1)))
    cache = VolumeCache([real.entry], max_bytes=1024**3, loader=lambda entry, image_budget: real)
    w = Window('cnv_context_verify', entries=[real.entry], output=out/'real_read_only',
               autoload=False, cache=cache, read_only=True)
    w.install_volume(real,0,row,cached=True)
    assert not real.overlays[4]['errors'], real.overlays[4]
    np.testing.assert_array_equal(real.overlays[0], overlay)
    np.testing.assert_array_equal(w.editor._lesion, overlay[row])
    assert not w.editor.journal.data['events']
    w.resize(1700,1000); w.show(); app.processEvents(); w.fit(); app.processEvents()
    w.grab().save(str(out/'real_cnv_overlay.png'))
    w.close(); app.processEvents()
    from octa_seg_v3.verify_lesions import LesionTests
    result = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(LesionTests))
    assert result.wasSuccessful()
    summary = dict(cohort_counts=dict(counts), cohort_native_masks_checked=len(records),
        live_precedence_and_absence=True, ignored_pixels_excluded=True, grid_rejection=True,
        qt_native_row_projection=True, real_scan=real_sid, real_bscan=row,
        lesion_regressions=result.testsRun, human_annotations_written=0)
    (out/'results.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))


if __name__ == '__main__': run()
