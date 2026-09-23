"""Verification of the collection contract. All writes use synthetic GUI records."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import argparse
import copy
import json
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PySide6.QtTest import QTest
from .verify import fixture, ContractTests, RAW, BASE, e
from .common import OUT, ROOT, V3, read, write, fingerprint
from .feedback import resolve, position_targets, training_targets, state_digest, geometry, anchored_order
from .policy import render
from .gui import Window, configure_v3_app
from .label_gui import Journal, Qt, QtCore, QtWidgets
from .data import VolumeCache, discover, load_volume
from .saved import index as saved_index, describe
from .providers import learned_onh, validate_grid, completed_manifest, context_overlays


class NewContractTests(unittest.TestCase):
    def test_normal_drawing_preserves_join_and_neighbor_reliability(self):
        first = e('stroke', k=2, lo=60, hi=80, xs=[60,79], ys=[70,70], taper=30,
                  semantics=3, drawing_reliability='reliable')
        second = e('stroke', k=1, lo=60, hi=80, xs=[60,79], ys=[80,80], taper=30,
                   semantics=3, drawing_reliability='reliable')
        r = resolve([first, second], RAW, 0, 256)
        self.assertTrue(r['displaced'][2,60:80].all())
        self.assertTrue((r['reliability'][2,60:80] == 1).all())
        self.assertFalse((r['reliability'] == 0).any())
        output = render(BASE, r, 0, 256, np.zeros(512, bool))
        self.assertTrue((output['state'] == 1).all())
        targets = position_targets(r, np.zeros(512, bool), r['valid_geometry'])
        self.assertFalse(targets['reliable_manual'][2,60:80].any())
        self.assertFalse(targets['approved_position'].any())
        # Old events retain their exact reliability replay, despite the display fix.
        old = resolve([first, dict(second, semantics=2)], RAW, 0, 256)
        self.assertTrue((old['reliability'][2,60:80] == -1).all())

    def test_uncertainty_is_explicit_and_local_during_drawing(self):
        events = [e('unreliable', k=2, lo=60, hi=80, semantics=3),
                  e('stroke', k=1, lo=60, hi=80, xs=[60,79], ys=[80,80], taper=30,
                    semantics=3, drawing_reliability='unreliable')]
        r = resolve(events, RAW, 0, 256)
        state = render(BASE, r, 0, 256, np.zeros(512, bool))['state']
        self.assertTrue((state[1:3,60:80] == 3).all())
        self.assertEqual(state[1,59], 1)
        self.assertEqual(state[2,59], 1)
        events.append(e('stroke', k=1, lo=60, hi=80, xs=[60,79], ys=[81,81], taper=30,
                        semantics=3, drawing_reliability='reliable'))
        r = resolve(events, RAW, 0, 256)
        self.assertTrue((r['reliability'][1,60:80] == 1).all())
        self.assertTrue((r['reliability'][2,60:80] == 0).all())

    def test_vector_order_matches_original_column_algorithm(self):
        rng = np.random.default_rng(718)
        for active in range(8):
            z = rng.uniform(-50, 300, RAW.shape).astype(np.float32)
            z[rng.random(z.shape) < .1] = np.nan
            trace = rng.integers(-1, 2, z.shape)
            anatomy = rng.integers(-1, 2, z.shape)
            excluded = rng.random(512) < .1
            touched = rng.random(512) < .7
            expected = z.copy()
            for x in np.flatnonzero(touched & ~excluded):
                if not np.isfinite(expected[active,x]): continue
                for direction in (-1, 1):
                    anchor = expected[active,x]
                    for k in range(active+direction, 8 if direction > 0 else -1, direction):
                        if not np.isfinite(expected[k,x]) or trace[k,x] == 0 or anatomy[k,x] == 0: continue
                        limit = anchor + direction
                        if direction * (expected[k,x]-limit) >= 0: break
                        expected[k,x] = limit
                        anchor = expected[k,x]
            np.testing.assert_array_equal(anchored_order(z, active, touched, trace, anatomy, excluded), expected)

    def test_locality_stops_at_nonconflicting_neighbor(self):
        raw = RAW.copy(); raw[0,90] = 80  # unrelated old crossing
        event = e('stroke', k=6, lo=90, hi=91, xs=[90], ys=[160], taper=0, semantics=2)
        r = resolve([event], raw, 0, 256)
        np.testing.assert_array_equal(r['positions'][:6,90],raw[:6,90])

    def test_join_does_not_bridge_judged_gap(self):
        events = [e('not_traceable',k=6,lo=90,hi=95,semantics=2),
                  e('stroke',k=6,lo=100,hi=101,xs=[100],ys=[170],taper=30,semantics=2)]
        r=resolve(events,RAW,0,256)
        np.testing.assert_array_equal(r['positions'][6,:95],RAW[6,:95])

    def test_active_pr_crosses_many_inner_neighbors_locally(self):
        event = e('stroke', k=6, lo=80, hi=82, xs=[80, 81], ys=[40, 42], taper=0, semantics=2)
        r = resolve([event], RAW, 0, 256)
        np.testing.assert_array_equal(r['positions'][6, 80:82], [40, 42])
        self.assertTrue(r['displaced'][1:6, 80:82].all())
        self.assertFalse(r['drawn'][:6].any())
        np.testing.assert_array_equal(r['positions'][:, :80], RAW[:, :80])
        np.testing.assert_array_equal(r['positions'][:, 82:], RAW[:, 82:])
        self.assertFalse(r['unresolved'].any())

    def test_deeper_edit_and_missing_proposals(self):
        raw = RAW.copy(); raw[2, 70:72] = np.nan
        r = resolve([e('stroke', k=1, lo=70, hi=72, xs=[70,71], ys=[170,171], taper=0, semantics=2)], raw, 0, 256)
        self.assertTrue(np.isnan(r['positions'][2,70:72]).all())
        np.testing.assert_array_equal(r['positions'][1,70:72], [170,171])
        self.assertTrue(r['displaced'][3:7,70:72].all())
        self.assertTrue(r['unresolved'][2,70:72].all())
        r = resolve([e('stroke', k=2, lo=70, hi=72, xs=[70,71], ys=[80,81], taper=30, semantics=2)], raw, 0, 256)
        self.assertTrue(np.isfinite(r['positions'][2]).all())

    def test_image_limit_preserves_stroke_and_requires_exception(self):
        ev = e('stroke', k=6, lo=70, hi=71, xs=[70], ys=[0], taper=0, semantics=2)
        r = resolve([ev], RAW, 0, 256)
        self.assertEqual(r['positions'][6,70], 0)
        self.assertTrue(r['unresolved'][:6,70].all())
        r = resolve([ev, dict(e('not_traceable', lo=70, hi=71, semantics=2), boundaries=list(range(6)))], RAW, 0, 256)
        self.assertFalse(r['unresolved'].any())

    def test_legacy_ordering_is_unchanged(self):
        ev = e('stroke', k=6, lo=70, hi=71, xs=[70], ys=[40], taper=0)
        r = resolve([ev, e('case_metadata', values={'completed': True})], RAW, 0, 256)
        self.assertEqual(r['positions'][6,70], RAW[5,70]+1)
        self.assertFalse(r['approved'].any())
        self.assertEqual(r['review_status'], 'Draft')


def qt_checks(app, folder):
    errors = []
    hook = sys.excepthook
    def error_hook(typ, val, tb):
        import traceback
        traceback.print_exception(typ, val, tb)
        errors.append(str(val))
    sys.excepthook = error_hook
    volume = fixture(folder)
    window = Window('synthetic_lead', entries=[volume.entry], output=folder/'synthetic_lead', autoload=False,
        cache=VolumeCache([volume.entry], loader=lambda entry, image_budget: volume), queue_output=folder/'queues')
    window.resize(1550, 950); window.show(); app.processEvents()
    window.install_volume(volume, 0, 256, False); app.processEvents(); window.fit(); app.processEvents()
    ed = window.editor
    assert not ed.auto_pick.isChecked()
    assert not list((window.output/'journals').glob('*.json'))
    assert not window.queue_toolbar.isVisible()
    def click(button):
        QTest.mouseClick(button, Qt.MouseButton.LeftButton); app.processEvents()
        assert not errors, errors
    def drag(button, modifiers=Qt.KeyboardModifier.NoModifier, start=(100,50), stop=(110,50)):
        a = ed.canvas.mapFromScene(QtCore.QPointF(*start)); b = ed.canvas.mapFromScene(QtCore.QPointF(*stop))
        QTest.mousePress(ed.canvas.viewport(), button, modifiers, a)
        QTest.mouseMove(ed.canvas.viewport(), b)
        QTest.mouseRelease(ed.canvas.viewport(), button, modifiers, b)
        app.processEvents(); assert not errors, errors
        event = ed.journal.events[-1]
        return event['lo'], event['hi']
    # Tool selection is not boundary work, including switching modes and turning off.
    click(ed.mark_buttons['unreliable']); click(ed.mark_buttons['not_visible']); click(ed.mark_buttons['not_visible'])
    assert not list((window.output/'journals').glob('*.json'))
    assert not saved_index(window.reviewer, window.output)
    # Explicit selected PR remains selected even while drawing close to another boundary.
    ed.surface_list.setCurrentRow(6)
    lo, hi = drag(Qt.MouseButton.LeftButton, start=(100,45), stop=(111,45))
    assert ed.s == 6 and ed.resolved['drawn'][6,lo:hi].all()
    assert ed.resolved['displaced'][2:6,lo:hi].all()
    assert not (ed.resolved['reliability'] == 0).any()
    assert (ed.rendered['state'] == 1).all()
    # Journal already survives a restart even before the derived NPZ idle save.
    disk_record = read(ed.journal.path)
    disk_state = resolve(disk_record['events'][:disk_record['cursor']], RAW, 0, 256)
    assert state_digest(disk_state) == state_digest(ed.resolved)
    with patch.object(ed, '_save_clicked') as save:
        ed.canvas._drawing = True
        ed._save_when_idle()
        save.assert_not_called()
        ed.canvas._drawing = False
    assert np.max(np.abs(ed.resolved['positions'][6,lo:hi] - 45)) < 1
    after = state_digest(ed.resolved)
    QTest.keyClick(ed.canvas, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier); app.processEvents()
    np.testing.assert_array_equal(ed.resolved['positions'], RAW)
    QTest.keyClick(ed.canvas, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier); app.processEvents()
    assert state_digest(ed.resolved) == after
    assert len(window.navigator._review_lines) == 1
    assert window.navigator._review_lines[0].pen().style() == Qt.PenStyle.DashLine
    # Independent marking axes, precedence of explicit modifiers, and retained geometry.
    ed.surface_list.setCurrentRow(1)
    click(ed.mark_buttons['unreliable'])
    before = ed.resolved['positions'].copy()
    lo, hi = drag(Qt.MouseButton.RightButton, start=(200,55), stop=(213,55))
    assert ed.resolved['reliability'][1,lo:hi].tolist() == [0]*(hi-lo)
    np.testing.assert_array_equal(ed.resolved['positions'], before)
    click(ed.mark_buttons['not_visible'])
    drag(Qt.MouseButton.RightButton, start=(220,55), stop=(234,55))
    assert ed.resolved['trace'][1,225] == 0
    drag(Qt.MouseButton.RightButton, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier, start=(220,55), stop=(234,55))
    assert ed.resolved['trace'][1,225] == 0 and ed.resolved['reliability'][1,225] == 1
    drag(Qt.MouseButton.RightButton, Qt.KeyboardModifier.AltModifier, start=(240,55), stop=(253,55))
    assert ed.resolved['reliability'][1,245] == 0 and ed.resolved['trace'][1,245] != 0
    click(ed.mark_buttons['not_visible'])
    drag(Qt.MouseButton.RightButton, start=(260,60), stop=(273,60))
    assert ed.resolved['excluded'][265]
    drag(Qt.MouseButton.RightButton, Qt.KeyboardModifier.ControlModifier, start=(280,60), stop=(293,60))
    ed.span_lo.setValue(300); ed.span_hi.setValue(310); ed.action('absent')
    # Hidden content triggers one all-boundary inspection step; span never narrows approval.
    ed.only_active.setChecked(True)
    click(ed.confirm_button)
    assert ed.resolved['confirmation'] is None and not ed.only_active.isChecked()
    click(ed.confirm_button)
    assert ed.resolved['review_status'] == 'Confirmed', ed.status.text()
    assert ed.resolved['approved'][0,0] and ed.resolved['approved'][7,-1]
    assert ed.resolved['approved'][2:6,105].all()
    assert not ed.resolved['approved'][1,205] and not ed.resolved['approved'][1,225]
    assert not ed.resolved['approved'][:,265].any() and not ed.resolved['approved'][1,305]
    assert window.navigator._review_lines[0].pen().style() == Qt.PenStyle.SolidLine
    # Editing confirmed curves changes approval status, never unrelated reliability.
    before_display = ed.rendered['state'].copy()
    ed.surface_list.setCurrentRow(0)
    drag(Qt.MouseButton.LeftButton, start=(30,21), stop=(40,21))
    assert ed.resolved['review_status'] == 'Needs reconfirmation'
    assert not ed.resolved['approved'].any()
    np.testing.assert_array_equal(before_display, ed.rendered['state'])
    ed.undo_redo(-1)
    assert ed.resolved['review_status'] == 'Confirmed'
    ed.surface_list.setCurrentRow(1)
    r = ed.resolved
    targets = position_targets(r, volume.data['shadow'][256], r['valid_geometry'])
    assert targets['approved_position'][2:6,105].all()
    assert targets['approved_position'][6,98]  # join approved, never called drawn
    assert not r['drawn'][6,98]
    assert not training_targets(ed.journal.data, RAW, 0, 256, volume.data['shadow'][256])['eligible']
    # Reader's role/policy branch uses an in-memory identity, never writes fake real labels.
    test_record = copy.deepcopy(ed.journal.data)
    test_record.update(scan_id='TEST_READER_IN_MEMORY_ONLY', training_eligible=True)
    for event in test_record['events']:
        if event['action'] == 'confirm_bscan': event['scan_id'] = test_record['scan_id']
    target = training_targets(test_record, RAW, 0, 256, np.zeros(512, bool))
    assert target['approved_position'][0,0]
    shadow = np.zeros(512, bool); shadow[0] = True
    assert not training_targets(test_record, RAW, 0, 256, shadow)['approved_position'][:,0].any()
    assert not training_targets(test_record, RAW, 0, 256, shadow, role='assessment')['eligible']
    snapshot = state_digest(ed.resolved)
    ed.metadata(notes='Synthetic only', for_review=True, categories=['cnv'])
    assert ed.resolved['review_status'] == 'Confirmed'
    window.navigate(257); window.navigate(256)
    assert state_digest(ed.resolved) == snapshot and ed.resolved['review_status'] == 'Confirmed'
    window.map_tabs.setCurrentIndex(1); app.processEvents()
    assert len(window.navigator._review_lines) == 1
    window.map_tabs.setCurrentIndex(0)
    # Any state edit invalidates the whole-scan approval; undo restores exact validity.
    ed.action('clear_marks')
    assert ed.resolved['review_status'] == 'Needs reconfirmation' and not ed.resolved['approved'].any()
    QTest.keyClick(ed.canvas, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier); app.processEvents()
    assert ed.resolved['review_status'] == 'Confirmed'
    QTest.keyClick(ed.canvas, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier); app.processEvents()
    assert ed.resolved['review_status'] == 'Needs reconfirmation'
    click(ed.confirm_button)
    queue = window.export_queue()
    assert 'positions' not in json.dumps(read(queue))
    # Browser filters are real widgets, and opening one's own work keeps the same key/path.
    window.show_saved(); app.processEvents()
    browser = window.saved_browser
    assert len(browser.rows) == 1
    browser.search.setText('does_not_exist'); assert len(browser.rows) == 0
    browser.search.clear(); browser.category.setCurrentText('cnv'); assert len(browser.rows) == 1
    browser.hide()
    # Journal optimistic locking + interruption before atomic replace.
    identity = {k: ed.journal.data[k] for k in ('reviewer_id','scan_id','bscan','model_id')}
    stale = Journal(ed.journal.path, identity)
    ed.metadata(notes='Synthetic revised note')
    try: stale.change(direction=-1); raise AssertionError('stale writer accepted')
    except RuntimeError: pass
    disk = fingerprint(ed.journal.path)
    with patch('octa_seg_v3.label_gui.write', side_effect=OSError('simulated interrupted save')):
        try: ed.record_event('unreliable', 10, 12); raise AssertionError('interrupted write accepted')
        except OSError: pass
    assert fingerprint(ed.journal.path) == disk
    assert ed.resolved['review_status'] == 'Confirmed'
    # A long actual mouse gesture must not trigger disk saves or context loads
    # mid-drag, even when their periodic timers become due.
    ed.surface_list.setCurrentRow(0)
    a = ed.canvas.mapFromScene(QtCore.QPointF(350, 21))
    b = ed.canvas.mapFromScene(QtCore.QPointF(470, 21))
    motion_ms = []
    with patch.object(ed.journal, 'change', wraps=ed.journal.change) as changed:
        QTest.mousePress(ed.canvas.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, a)
        for x in range(351, 471):
            start = time.perf_counter()
            point = ed.canvas.mapFromScene(QtCore.QPointF(x, 21))
            QTest.mouseMove(ed.canvas.viewport(), point); app.processEvents()
            motion_ms.append((time.perf_counter() - start) * 1000)
        assert ed.canvas._drawing
        with patch('octa_seg_v3.providers.context_overlays') as context:
            window.refresh_overlays()
            context.assert_not_called()
        ed._save_when_idle()
        changed.assert_not_called()
        QTest.mouseRelease(ed.canvas.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, b)
        assert changed.call_count == 1
    assert ed.resolved['drawn'][0,351:470].all()
    ed.undo_redo(-1)
    assert ed.resolved['review_status'] == 'Confirmed'
    path = ed.journal.path
    window.grab().save(str(folder/'synthetic_controls.png'))
    window.close(); app.processEvents()
    # Reopen after process-equivalent window/cache teardown.
    resumed = Window('synthetic_lead', entries=[volume.entry], output=folder/'synthetic_lead', autoload=False,
        cache=VolumeCache([volume.entry], loader=lambda entry,image_budget: volume))
    resumed.show(); resumed.install_volume(volume,0,256,False); app.processEvents()
    assert resumed.editor.resolved['review_status'] == 'Confirmed' and len(resumed.navigator._review_lines) == 1
    resumed.close(); app.processEvents()
    colleague = Window('synthetic_colleague', queue_path=queue, entries=[volume.entry], output=folder/'synthetic_colleague', autoload=False,
        cache=VolumeCache([volume.entry], loader=lambda entry,image_budget: volume))
    colleague.show(); colleague.install_volume(volume,0,256,False); app.processEvents()
    assert not colleague.editor.resolved['drawn'].any() and not colleague.editor.resolved['approved'].any()
    colleague.close(); app.processEvents()
    # Read-only discussion cannot write even with timers, edits and direct API attempts.
    protected = fingerprint(path)
    discussion = Window('synthetic_lead', entries=[volume.entry], output=folder/'synthetic_lead', autoload=False, read_only=True,
        cache=VolumeCache([volume.entry], loader=lambda entry,image_budget: volume))
    discussion.show(); discussion.install_volume(volume,0,256,False); app.processEvents()
    discussion.editor.record_event('unreliable',0,20)
    discussion.editor.undo_redo(-1); discussion.save_all(); discussion.close(); app.processEvents()
    assert fingerprint(path) == protected
    assert not errors, errors
    sys.excepthook = hook
    return dict(actual_qt_mouse_keys_buttons=True, anchored_edit=True, modifiers_and_latched_tools=True,
        full_confirmation_and_masks=True, revision_invalidation_undo_redo=True, saved_browser_and_lines=True,
        independent_review=True, discussion_read_only=True, stale_and_interrupted_saves=True, restart=True,
        synthetic_training_excluded=True, no_background_writes_during_drag=True,
        mouse_move_median_ms=float(np.median(motion_ms)), mouse_move_max_ms=max(motion_ms), callback_errors=errors)


def real_checks(app, folder):
    entries = discover()
    ids = ['TS267_OD_2025-03-05_D14_s01_104048', 'TS165_OS_2025-04-29_WT_s02_121711', 'TS247_OD_2024-10-17_beforelaser_s01_103017']
    selected = [next(e for e in entries if e['scan_id'] == sid) for sid in ids]
    results=[]
    for entry in selected:
        volume = load_volume(entry, image_budget=0)
        window = Window('read_only_verification', entries=[entry], output=folder/'real_read_only', autoload=False,
            cache=VolumeCache([entry], loader=lambda entry,image_budget: volume), read_only=True)
        window.resize(1550,950); window.show(); app.processEvents()
        for bscan in ([180,256,320] if 'TS267' in entry['scan_id'] else [256]):
            window.install_volume(volume,0,bscan,False); window.fit(); app.processEvents()
            window.grab().save(str(folder/f'{entry["scan_id"]}_b{bscan:04d}.png'))
        onh = learned_onh(volume)
        results.append(dict(scan_id=entry['scan_id'], shape=list(volume.images.shape), source=volume.provenance,
            automatic_onh_adapter=bool(onh), onh_pixels=int(onh[0].sum()) if onh else None))
        window.close(); app.processEvents()
    assert not list((folder/'real_read_only').rglob('*.npz'))
    return results


def provider_checks(folder):
    from .providers import ANATOMY, validate_anatomy
    v=fixture(folder)
    directory=folder/'provider fixture with spaces'; directory.mkdir()
    spec=dict(scan_id=v.scan.scan_id,source_volume=str(v.scan.source_volume),shape=list(v.scan.native_shape),
        axis_order='B-scan,A-line',orientation='native-enface;vitreous-at-depth-zero',crop_offset=0,
        retina_band=[0,256],spacing_um=[1460/512,1460/512,1.12],file='masks.npz')
    mask=np.zeros(v.scan.native_shape,bool); mask[100:120,200:240]=True
    np.savez_compressed(directory/'masks.npz',onh=mask)
    spec['sha256']=fingerprint(directory/'masks.npz')
    manifest=dict(format='octa-review-provider-1',status='complete',version='synthetic-context-1',
        checkpoint_identity='synthetic-only',kind='context',scans=[spec],
        masks=[dict(name='onh',definition='optic nerve head enface footprint',array='onh')],state_availability='automatic mask only',provenance='synthetic test')
    path=directory/'review_provider.json'; write(path,manifest)
    assert completed_manifest(path) is None
    write(directory/'REVIEW_PROVIDER_COMPLETE.json',dict(manifest_sha256=fingerprint(path)))
    validate_grid(spec,v)
    with patch('octa_seg_v3.providers.manifests',return_value=[path]):
        context=context_overlays(v,folder/'no_proposals')
        np.testing.assert_array_equal(context[2],mask)
        before=v.data['raw_position_branch'].copy()
        np.savez_compressed(directory/'masks.npz',onh=~mask)  # interrupted publisher: seal no longer matches payload
        rejected=context_overlays(v,folder/'no_proposals')
        assert rejected[4]['errors'] and not rejected[2].any()
        np.testing.assert_array_equal(before,v.data['raw_position_branch'])
        spec['sha256']=fingerprint(directory/'masks.npz'); spec['shape']=[512,511]
        write(path,manifest); write(directory/'REVIEW_PROVIDER_COMPLETE.json',dict(manifest_sha256=fingerprint(path)))
        assert context_overlays(v,folder/'no_proposals')[4]['errors']
    malformed=copy.deepcopy(ANATOMY); malformed['boundaries'][6]['definition']='different PR definition'
    try: validate_anatomy(malformed); raise AssertionError('anatomy mismatch accepted')
    except ValueError: pass
    return dict(sealed_mask_loaded=True, incomplete_write_rejected=True, geometry_mismatch_rejected=True,
        boundary_definition_mismatch_rejected=True, inference_inputs_unchanged=True)


def legacy_checks(app, folder):
    import shutil
    source=next(p for p in (V3/'tests').rglob('SYNTHETIC_GUI_FIXTURE_b0256.json') if p.parent.name=='journals' and p.parent.parent.name=='reviewer_a')
    original=fingerprint(source)
    fake_v3=folder/'historical_home'
    legacy_path=fake_v3/'reviewers/reviewer_a/journals'/source.name
    legacy_path.parent.mkdir(parents=True); shutil.copy2(source,legacy_path)
    v=fixture(folder)
    with patch('octa_seg_v3.label_gui.V3',fake_v3), patch('octa_seg_v3.saved.V3',fake_v3):
        window=Window('reviewer_a',entries=[v.entry],output=folder/'adopted/reviewer_a',autoload=False,
            cache=VolumeCache([v.entry],loader=lambda entry,image_budget:v))
        window.show(); window.install_volume(v,0,256,False); app.processEvents()
        ed=window.editor
        assert ed.journal.legacy_path and saved_index('reviewer_a',window.output)[0]['status']=='Legacy'
        old=resolve(read(source)['events'][:read(source)['cursor']],RAW,0,256)
        np.testing.assert_array_equal(old['positions'],ed.resolved['positions'])
        assert not ed.resolved['confirmation']
        window.save_all()
        assert not list((window.output/'journals').glob('*.json'))
        QTest.mouseClick(ed.confirm_button,Qt.MouseButton.LeftButton); app.processEvents()
        if ed.resolved['confirmation'] is None:
            QTest.mouseClick(ed.confirm_button,Qt.MouseButton.LeftButton); app.processEvents()
        assert ed.resolved['review_status']=='Confirmed',ed.status.text()
        assert ed.journal.data['adopted_from']['sha256']==original
        assert fingerprint(source)==original and fingerprint(legacy_path)==original
        assert (ed.journal.path.parent/'history'/f'{ed.journal.path.stem}_legacy_original.json').exists()
        window.close(); app.processEvents()
    return dict(historical_positions_preserved=True, old_completed_not_confirmation=True,
        browser_before_adoption=True, explicit_gui_confirmation_adopts=True, original_bytes_unchanged=True)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--real', action='store_true')
    args=parser.parse_args()
    folder=OUT/'verification'/time.strftime('%Y%m%d_%H%M%S'); folder.mkdir(parents=True)
    QtCore.QSettings.setDefaultFormat(QtCore.QSettings.Format.IniFormat)
    QtCore.QSettings.setPath(QtCore.QSettings.Format.IniFormat,QtCore.QSettings.Scope.UserScope,str(folder/'preferences'))
    protected={str(p):fingerprint(p) for root in (V3/'reviewers', OUT/'reviewers', ROOT/'outputs/cnv_labels') for p in root.rglob('*') if p.is_file() and p.suffix in ('.json','.npz')}
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(ContractTests), unittest.defaultTestLoader.loadTestsFromTestCase(NewContractTests)])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful(): raise SystemExit(1)
    app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([]); configure_v3_app(app)
    output=dict(contract_tests=result.testsRun, qt=qt_checks(app,folder), providers=provider_checks(folder),
        legacy=legacy_checks(app,folder), screenshots_are='offscreen rendering; not proof of interactive desktop visibility')
    if args.real: output['real_read_only']=real_checks(app,folder)
    changed=[path for path,digest in protected.items() if fingerprint(path)!=digest]
    output.update(protected_files=len(protected), protected_changes=changed, directory=str(folder))
    assert not changed, changed
    write(folder/'results.json',output); write(OUT/'verification/latest.json',output)
    print(json.dumps(output,indent=2))

if __name__=='__main__': main()
