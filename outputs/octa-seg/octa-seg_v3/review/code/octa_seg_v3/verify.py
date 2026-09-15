"""Real Qt interaction checks mutate synthetic fixtures only; real cohort checks are read-only."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import argparse
import copy
from pathlib import Path
from types import SimpleNamespace
import time
import unittest
import uuid
import numpy as np
from .common import OUT, ROOT, V2, read, write, fingerprint
from .feedback import resolve, position_targets
from .policy import baseline, render
from .data import Volume, VolumeCache, discover
from .label_gui import Editor, Journal, Qt, QtCore, QtGui, QtWidgets
from .gui import Window, configure_v3_app
from octa_seg_v1.decisions import thickness
from eight_surface.config import SURFACE_NAMES
from PySide6.QtTest import QTest

CAL = [dict(supported=True, not_traceable_cutoff=.2, trace_cutoff=.6, reliability_cutoff=.6) for _ in range(8)]
RAW = np.broadcast_to((20 + np.arange(8) * 25)[:, None], (8, 512)).astype(np.float32).copy()
BASE = baseline(RAW, np.full((8, 2, 512), .9), CAL, np.zeros(512, bool), 0, 256)


def e(action, k=1, lo=60, hi=80, **extras):
    return dict(action=action, boundaries=[k], lo=lo, hi=hi, **extras)


class ContractTests(unittest.TestCase):
    def test_drawing_mode_judges_exact_stroke_and_preserves_old_events(self):
        original = e('stroke', lo=212, hi=214, xs=[212., 213.], ys=[46., 46.], taper=30.)
        old = resolve([original], RAW, 0, 256)
        self.assertTrue(np.all(old['reliability'] == -1))
        for mode, value in [('unreliable', 0), ('reliable', 1)]:
            r = resolve([dict(original, drawing_reliability=mode)], RAW, 0, 256)
            self.assertEqual(np.argwhere(r['reliability'] != -1).tolist(), [[1, 212], [1, 213]])
            self.assertTrue(np.all(r['reliability'][1, 212:214] == value))
            result = render(BASE, r, 0, 256, np.zeros(512, bool))
            self.assertTrue(np.all(result['state'][1, 212:214] == (3 if value == 0 else 1)))
            self.assertEqual(result['state'][1, 211], BASE['state'][1, 211])  # joining is not a reliability mark

    def test_modifier_axes_independent(self):
        events = [e('unreliable'), e('not_traceable'), e('traceable')]
        r = resolve(events, RAW, 0, 256)
        self.assertTrue(np.all(r['trace'][1, 60:80] == 1))
        self.assertTrue(np.all(r['reliability'][1, 60:80] == 0))
        r = resolve([e('not_traceable'), e('reliable')], RAW, 0, 256)
        self.assertTrue(np.all(render(BASE, r, 0, 256, np.zeros(512, bool))['state'][1, 60:80] == 2))

    def test_absence_is_distinct_and_cannot_be_restored_by_visibility(self):
        r = resolve([e('absent'), e('traceable'), e('reliable')], RAW, 0, 256)
        output = render(BASE, r, 0, 256, np.zeros(512, bool))
        self.assertTrue(np.all(r['anatomy'][1, 60:80] == 0))
        self.assertTrue(np.isnan(output['uncertain_estimates'][1, 60:80]).all())
        self.assertTrue(np.isfinite(output['reported_positions'][0, 60:80]).all())

    def test_stroke_join_and_ordering_are_not_manual_targets(self):
        r = resolve([e('stroke', lo=70, hi=71, xs=[70.], ys=[80.], taper=30.)], RAW, 0, 256)
        self.assertEqual(int(r['drawn'].sum()), 1)
        self.assertTrue(r['taper'][1, 69])
        self.assertTrue(r['displaced'][2, 70])
        self.assertFalse(r['drawn'][2, 70])
        self.assertTrue(np.all(r['reliability'] == -1))
        output = render(BASE, r, 0, 256, np.zeros(512, bool))
        self.assertEqual(output['state'][1, 69], BASE['state'][1, 69])

    def test_reviewed_is_not_drawn(self):
        r = resolve([e('reviewed', columns={'1': [65]}, positions={'1': [45.]})], RAW, 0, 256)
        self.assertTrue(r['reviewed'][1, 65])
        self.assertFalse(r['drawn'].any())
        self.assertFalse(r['approved'].any())

    def test_approval_revoked_by_changed_coordinates(self):
        events = [e('approve_position', columns={'1': [65]}, positions={'1': [45.]}),
                  e('stroke', lo=65, hi=66, xs=[65.], ys=[46.], taper=0.)]
        r = resolve(events, RAW, 0, 256)
        self.assertFalse(r['approved'].any())

    def test_ambiguous_stroke_separate_from_reliable_training(self):
        r = resolve([e('stroke', lo=65, hi=66, xs=[65.], ys=[46.], taper=0.), e('unreliable')], RAW, 0, 256)
        result = render(BASE, r, 0, 256, np.zeros(512, bool))
        target = position_targets(r, np.zeros(512, bool), result['valid_geometry'])
        self.assertTrue(target['ambiguous_manual'][1, 65])
        self.assertFalse(target['reliable_manual'].any())
        self.assertTrue(np.isnan(result['thickness_um'][0, 65]))
        self.assertEqual(result['uncertain_estimates'][1, 65], 46.)

    def test_shadow_and_exclusion_thickness_nan(self):
        shadow = np.zeros(512, bool)
        shadow[100] = True
        r = resolve([e('exclude_image')], RAW, 0, 256)
        result = render(BASE, r, 0, 256, shadow)
        self.assertTrue(np.isnan(result['thickness_um'][:, 60:80]).all())
        self.assertTrue(np.isnan(result['thickness_um'][:, 100]).all())
        self.assertAlmostEqual(float(result['thickness_um'][0, 90]), 28., places=4)

    def test_region_clear_restores_prior_local_mark(self):
        r = resolve([e('reliable'), e('unreliable_region'), e('clear_region')], RAW, 0, 256)
        self.assertTrue(np.all(r['reliability'][1, 60:80] == 1))
        self.assertTrue(np.all(r['reliability'][2, 60:80] == -1))

    def test_metadata_does_not_annotate_boundaries(self):
        r = resolve([e('case_metadata', values=dict(categories=['cnv'], for_review=True))], RAW, 0, 256)
        self.assertFalse(r['drawn'].any())
        self.assertTrue(np.all(r['trace'] == -1))
        self.assertTrue(np.all(r['reliability'] == -1))

    def test_no_trace_keeps_other_boundaries(self):
        r = resolve([e('not_traceable')], RAW, 0, 256)
        output = render(BASE, r, 0, 256, np.zeros(512, bool))
        self.assertTrue(np.isnan(output['reported_positions'][1, 60:80]).all())
        self.assertTrue(np.isfinite(output['reported_positions'][2, 60:80]).all())

    def test_positive_state_inside_exclusion_is_masked(self):
        events = [e('reviewed', columns={'1': [65]}, positions={'1': [45.]}), e('exclude_image'), e('not_traceable', k=2)]
        r = resolve(events, RAW, 0, 256)
        target = position_targets(r, np.zeros(512, bool), np.ones((8, 512), bool))
        self.assertEqual(target['trace'][1, 65], -1)
        self.assertEqual(target['reliability'][1, 65], -1)
        self.assertEqual(target['trace'][2, 65], 0)


def fixture(folder, sid='SYNTHETIC_GUI_FIXTURE'):
    image = np.broadcast_to(np.linspace(0, 30, 256)[:, None], (256, 512)).astype(np.float32)
    images = np.broadcast_to(image[None], (512, 256, 512))
    data = dict(raw_position_branch=np.broadcast_to(RAW[None], (512, 8, 512)),
                probabilities=np.full((512, 8, 2, 512), .9, np.float32),
                entropy=np.zeros((512, 8, 512), np.float32),
                vessel=np.zeros((512, 512), bool), shadow=np.zeros((512, 512), bool),
                label_offset=np.array(0), surface_names=np.array(SURFACE_NAMES))
    base = {key: np.broadcast_to(BASE[key][None], (512, 8, 512)) for key in ('state', 'reason', 'reported_positions', 'uncertain_estimates')}
    masks = tuple(np.zeros((512, 512), bool) for _ in range(4))
    source = folder / 'synthetic_source'
    scan = SimpleNamespace(scan_id=sid, source_volume=source, native_shape=(512, 512),
        retina_band=(0, 256), surface_names=tuple(SURFACE_NAMES), px_um=1.12,
        shadow=data['shadow'], structural_bscan=lambda row: images[row])
    return Volume(dict(scan_id=sid, directory=str(folder / sid)), images, data, {}, base,
        thickness(base['reported_positions'], data['shadow']), images.mean(axis=1), scan,
        masks + (dict(status='synthetic fixture — not human labels'), ''), 'synthetic-model-v1',
        dict(training_eligible=False), 0., 1024, 'synthetic')


def qt_checks(app, folder):
    errors = []
    import sys
    previous_hook = sys.excepthook
    sys.excepthook = lambda typ, value, tb: errors.append(str(value))
    v = fixture(folder)
    cache = VolumeCache([v.entry], loader=lambda entry, image_budget: v)
    w = Window('reviewer_a', entries=[v.entry], output=folder / 'reviewer_a', autoload=False,
               cache=cache, queue_output=folder / 'queues')
    w.show()
    app.processEvents()
    w.install_volume(v, 0, 256, False)
    w.fit()
    app.processEvents()
    ed = w.editor
    ed.auto_pick.setChecked(False)
    assert not list((w.output / 'surface_labels').glob('*.npz'))
    ed.surface_list.setCurrentRow(1)

    # One-column button marks must not change the rest of the display or labels.
    ed.span_lo.setValue(212)
    ed.span_hi.setValue(213)
    before = {key: value.copy() for key, value in ed.rendered.items()}
    opacity = ed.canvas._surface_items[1].opacity()
    action = next(a for a in ed.findChildren(QtGui.QAction)
                  if a.text() == 'Mark selected range unreliable (keep position)')
    action.trigger()
    app.processEvents()
    assert np.argwhere(ed.resolved['reliability'] == 0).tolist() == [[1, 212]]
    for key in ('reported_positions', 'uncertain_estimates', 'state'):
        outside = np.ones(before[key].shape, bool)
        outside[1, 212] = False
        assert np.array_equal(before[key][outside], ed.rendered[key][outside], equal_nan=True), key
    assert ed.canvas._surface_items[1].opacity() == opacity
    assert 'Buttons affect 1 A-line: 212' in ed.range_summary.text()
    assert '1 A-lines marked unreliable' in ed.range_summary.text()
    ed.undo_redo(-1)

    def drag(button, modifiers, start=(60, 45), stop=(80, 45)):
        a = ed.canvas.mapFromScene(QtCore.QPointF(*start))
        b = ed.canvas.mapFromScene(QtCore.QPointF(*stop))
        lo, hi = sorted([int(np.clip(round(ed.canvas.mapToScene(p).x()), 0, 511)) for p in (a, b)])
        QTest.mousePress(ed.canvas.viewport(), button, modifiers, a)
        QTest.mouseMove(ed.canvas.viewport(), b)
        QTest.mouseRelease(ed.canvas.viewport(), button, modifiers, b)
        app.processEvents()
        assert not errors, errors
        return lo, hi + 1

    # A single click is a real correction, not a strip-mode action.
    point = ed.canvas.mapFromScene(QtCore.QPointF(100, 50))
    expected_col = int(round(ed.canvas.mapToScene(point).x()))
    QTest.mouseClick(ed.canvas.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)
    app.processEvents()
    assert ed.resolved['drawn'][1, expected_col]
    assert ed.resolved['drawn'].sum() == 1
    assert ed.resolved['taper'].any()
    assert ed.resolved['reliability'][1, expected_col] == 1
    ed.undo_redo(-1)
    assert not ed.resolved['drawn'].any()
    ed.undo_redo(1)
    assert ed.resolved['drawn'][1, expected_col]
    before_mode = ed.resolved['reliability'].copy()
    QTest.mouseClick(ed.unreliable_draw, Qt.MouseButton.LeftButton)
    assert ed.unreliable_draw.isChecked()
    assert np.array_equal(ed.resolved['reliability'], before_mode)  # toggle alone never annotates
    QTest.mouseClick(ed.canvas.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)
    assert ed.resolved['reliability'][1, expected_col] == 0
    assert ed.rendered['state'][1, expected_col] == 3
    assert np.sum(ed.resolved['reliability'] == 0) == 1
    QTest.mouseClick(ed.unreliable_draw, Qt.MouseButton.LeftButton)
    QTest.mouseClick(ed.canvas.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)
    assert ed.resolved['reliability'][1, expected_col] == 1
    assert ed.rendered['state'][1, expected_col] == 1
    lo, hi = drag(Qt.MouseButton.RightButton, Qt.KeyboardModifier.AltModifier)
    assert np.all(ed.resolved['reliability'][1, lo:hi] == 0)
    assert np.all(ed.resolved['reliability'][0, lo:hi] == -1)
    drag(Qt.MouseButton.RightButton, Qt.KeyboardModifier.ShiftModifier)
    assert np.isnan(ed.rendered['uncertain_estimates'][1, lo:hi]).all()
    drag(Qt.MouseButton.RightButton, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
    assert np.all(ed.resolved['trace'][1, lo:hi] == 1)
    assert np.all(ed.resolved['reliability'][1, lo:hi] == 0)
    drag(Qt.MouseButton.RightButton, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)
    assert np.all(ed.resolved['reliability'][1, lo:hi] == 1)
    drag(Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier, (200, 80), (215, 100))
    assert ed.resolved['excluded'][205]
    drag(Qt.MouseButton.RightButton, Qt.KeyboardModifier.ControlModifier, (200, 80), (215, 100))
    assert not ed.resolved['excluded'][205]
    reviewed_lo, reviewed_hi = drag(Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier, (260, 45), (280, 45))
    assert np.all(ed.resolved['reviewed'][1, reviewed_lo:reviewed_hi])
    assert not ed.resolved['drawn'][1, reviewed_lo:reviewed_hi].any()
    ed.span_lo.setValue(300)
    ed.span_hi.setValue(320)
    ed.action('absent')
    assert np.all(ed.resolved['anatomy'][1, 300:320] == 0)
    assert np.isnan(ed.rendered['reported_positions'][1, 300:320]).all()
    assert np.isfinite(ed.rendered['reported_positions'][0, 300:320]).all()
    w.category_checks['cnv'].setChecked(True)
    w.ambiguous.setChecked(True)
    w.for_review.setChecked(True)
    w.completed.setChecked(True)
    app.processEvents()
    record = read(ed.journal.path)
    assert record['reviewer_id'] == 'reviewer_a'
    expected = copy.deepcopy(ed.resolved)
    w.navigate(257)
    assert not ed.resolved['drawn'].any()
    w.navigate(256)
    for key in ('drawn', 'taper', 'trace', 'reliability', 'anatomy', 'positions'):
        assert np.array_equal(ed.resolved[key], expected[key], equal_nan=True), key
    assert w.for_review.isChecked() and w.ambiguous.isChecked()
    assert w.category_checks['cnv'].isChecked()
    QTest.keyClick(ed.canvas, Qt.Key.Key_Right)
    app.processEvents()
    assert w.row == 257
    QTest.keyClick(ed.canvas, Qt.Key.Key_Left)
    app.processEvents()
    assert w.row == 256
    QTest.keyClick(ed.canvas, Qt.Key.Key_3)
    assert ed.s == 2
    QTest.keyClick(ed.canvas, Qt.Key.Key_BracketLeft)
    assert ed.s == 1
    label = next((w.output / 'surface_labels').glob('*b0256.npz'))
    with np.load(label, allow_pickle=False) as z:
        assert str(z['labeller'][0]) == 'reviewer_a'
        assert z['local_drawn'].sum() == 1
    w.map_tabs.setCurrentIndex(1)
    w.map_choice.setCurrentIndex(w.map_choice.findData('RNFL'))
    w.cursor_column(305)
    assert 'no reportable' in w.point_value.text()
    w.cursor_column(30)
    assert '28.00' in w.point_value.text()
    ed.blind_check.setChecked(True)
    assert w.map_tabs.currentIndex() == 0 and not w.map_tabs.isTabEnabled(1)
    assert not ed.displayed(1)[30]
    assert ed.displayed(1)[expected_col]
    ed.blind_check.setChecked(False)
    w.notes.setPlainText('Synthetic test note only')
    w.navigate(257)
    assert w.notes.toPlainText() == ''
    w.navigate(256)
    assert w.notes.toPlainText() == 'Synthetic test note only'
    queue_path = w.export_queue()
    manifest = read(queue_path)
    assert len(manifest['examples']) == 1
    assert not any(key in manifest['examples'][0] for key in ('positions', 'notes', 'categories', 'especially_ambiguous'))
    stale = Journal(ed.journal.path, {key: record[key] for key in ('reviewer_id', 'scan_id', 'bscan', 'model_id')})
    ed.action('unreliable')
    try:
        stale.change(direction=-1)
        raise AssertionError('Stale journal was allowed to overwrite')
    except RuntimeError:
        pass
    w.grab().save(str(folder / 'synthetic_controls.png'))
    w.close()
    app.processEvents()
    # Same case, independent reviewer: no labels/decisions are inherited.
    v2 = fixture(folder)
    colleague = Window('reviewer_b', queue_path=queue_path, entries=[v2.entry],
        output=folder / 'reviewer_b', autoload=False, cache=VolumeCache([v2.entry], loader=lambda entry, image_budget: v2))
    colleague.show()
    app.processEvents()
    colleague.install_volume(v2, 0, 256, False)
    assert not colleague.editor.resolved['drawn'].any()
    assert np.all(colleague.editor.resolved['anatomy'] == -1)
    assert colleague.notes.toPlainText() == ''
    assert colleague.editor.blind_check.isChecked()
    colleague.close()
    app.processEvents()
    assert not errors, errors
    sys.excepthook = previous_hook
    return dict(single_click=True, exact_intervals=[lo, hi], original_modifier_gestures=True,
        undo_redo=True, reopen=True, anatomical_absence_distinct=True, no_browsing_labels=True,
        explicit_labeller=True, independent_reviewers=True, annotation_free_export=True,
        hidden_overlay_mode=True, map_point_units_and_nan=True, notes_do_not_leak_between_cases=True,
        conflicts_rejected=True, qt_callback_errors=errors)


def real_checks(app, folder):
    entries = discover()
    protected = {}
    for relative in ('outputs/eight_surface/labels', 'outputs/cnv_review_v1/surface_labels',
                     'outputs/octa-seg/octa-seg_v1/reviewer', 'outputs/octa-seg/octa-seg_v2/reviewer'):
        for path in (ROOT / relative).rglob('*'):
            if path.is_file() and path.suffix in ('.npz', '.json'):
                protected[str(path)] = fingerprint(path)
    selected = [entries[0], next(x for x in entries if x['scan_id'].startswith('TS247_')), next(x for x in entries if x['scan_id'].startswith('TS336_'))]
    window = Window('read_only_verification', entries=selected, output=folder / 'read_only', autoload=False)
    window.show()
    app.processEvents()
    before = time.perf_counter()
    window.load_scan(0, 256)
    deadline = time.monotonic() + 120
    tick = time.monotonic()
    while window.volume is None and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.05)  # release the GIL so the real background reader can run
        if time.monotonic() - tick >= 10:
            print('Real-volume cache progress', window.cache.status(), 'timer active', window.poll.isActive(), flush=True)
            tick = time.monotonic()
    assert window.volume is not None, f'Real volume load timeout: {window.cache.status()}'
    cold = time.perf_counter() - before
    window.fit()
    app.processEvents()
    window.grab().save(str(folder / 'real_enface.png'))
    window.map_tabs.setCurrentIndex(1)
    app.processEvents()
    window.grab().save(str(folder / 'real_thickness.png'))
    while len(window.cache.status()['ready']) < 3 and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.05)
    state = window.cache.status()
    assert len(state['ready']) == 3, state
    before = time.perf_counter()
    window.load_scan(1, 256)
    app.processEvents()
    warm = time.perf_counter() - before
    assert window.volume.scan.scan_id == selected[1]['scan_id']
    window.fit()
    app.processEvents()
    window.grab().save(str(folder / 'real_cnv.png'))
    assert state['bytes'] <= state['budget']
    window.close()
    app.processEvents()
    assert not list((folder / 'read_only/surface_labels').glob('*.npz'))
    for path, expected in protected.items():
        assert fingerprint(path) == expected, f'Protected annotation changed: {path}'
    return dict(discovered_volumes=len(entries), cold_open_seconds=cold, cached_open_seconds=warm,
                cached_volumes=len(state['ready']), cache_bytes=state['bytes'], cache_budget=state['budget'],
                protected_annotation_files_unchanged=len(protected), real_volume_mutations=False,
                selected=[x['scan_id'] for x in selected])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--real', action='store_true')
    args = parser.parse_args()
    folder = OUT / 'tests' / ('run_' + uuid.uuid4().hex)
    write(folder / 'SYNTHETIC_FIXTURES.json', dict(training_eligible=False, purpose='software checks only'))
    tests = unittest.defaultTestLoader.loadTestsFromTestCase(ContractTests)
    result = unittest.TextTestRunner(verbosity=2).run(tests)
    if not result.wasSuccessful():
        raise SystemExit(1)
    app = QtWidgets.QApplication([])
    app.setQuitOnLastWindowClosed(False)
    configure_v3_app(app)
    report = dict(contracts=result.testsRun, qt=qt_checks(app, folder), folder=str(folder))
    print('Qt interaction checks passed', flush=True)
    if args.real:
        report['real'] = real_checks(app, folder)
    write(folder / 'verification.json', report)
    write(OUT / 'tests/latest_verification.json', report)
    print(json_report(report), flush=True)


def json_report(value):
    import json
    return json.dumps(value, indent=2)


if __name__ == '__main__':
    main()
