"""Lesion replay and offscreen GUI checks; disk annotations are synthetic and ineligible."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import copy
import json
import sys
import time
import unittest
import uuid
from unittest.mock import patch
import numpy as np
from PySide6.QtTest import QTest
from . import lesions as L
from .feedback import CONTRACT, REVIEW_POLICY, STATE_KEYS, resolve, state_digest, training_targets, review_warnings
from .policy import render
from .verify import fixture, RAW, BASE
from .gui import Window, configure_v3_app
from .label_gui import Qt, QtCore, QtWidgets
from .data import VolumeCache
from .controls import confirm, json_array
from .common import OUT, V3, ROOT, read, write, fingerprint


def event(action, lo=100, hi=180, **values):
    return dict(id=uuid.uuid4().hex, action=action, lo=lo, hi=hi, boundaries=[], semantics=3,
                lesion_definition=L.DEFINITION_VERSION, **values)


def confirmed(events, include_lesions=True, policy=None, baseline=RAW):
    r = resolve(events, baseline, 0, 256)
    snapshot = {key: json_array(r[key]) for key in STATE_KEYS}
    approved = r['valid_geometry'] & (r['trace'] != 0) & (r['reliability'] != 0) & (r['anatomy'] != 0) & ~r['excluded'][None]
    snapshot['approved'] = approved.tolist()
    identity = dict(reviewer_id='unit', scan_id='UNIT_MEMORY_ONLY', bscan=256, model_id='unit', source={}, boundary_names=list(range(8)))
    confirmation = dict(action='confirm_bscan', semantics=3, contract=CONTRACT, state_digest=state_digest(r),
                        scope=[8, 512], geometry_revision=r['geometry_revision'], snapshot=snapshot, **identity)
    if policy is not None:
        confirmation.update(review_policy=policy, acknowledged_warnings=review_warnings(r['unresolved'], r['lesions']))
    if include_lesions:
        confirmation.update(lesion_contract=L.CONTRACT, lesion_definition=L.DEFINITION_VERSION,
                            lesion_definitions=L.DEFINITIONS, lesion_digest=L.digest(r['lesions']),
                            lesion_snapshot=L.snapshot(r['lesions']))
    all_events = events + [confirmation]
    return dict(**identity, events=all_events, cursor=len(all_events), training_eligible=True)


class LesionTests(unittest.TestCase):
    def test_shadow_override_is_column_wide_local_and_preserves_manual_exceptions(self):
        shadow = np.zeros(512, bool); shadow[100:160] = True
        ev = [dict(event('not_traceable', 125, 130), boundaries=[3]),
              dict(event('unreliable', 125, 130), boundaries=[4]),
              dict(event('stroke', 120, 140, xs=[120,139], ys=[70,70], taper=15, drawing_reliability='reliable'), boundaries=[2])]
        record = confirmed(ev, policy=REVIEW_POLICY)
        r = resolve(record['events'], RAW, 0, 256)
        out = render(BASE, r, 0, 256, shadow)
        self.assertFalse(out['context_uncertain'][:, 120:140].any())
        self.assertTrue(out['context_uncertain'][1:, 100:120].all())
        self.assertTrue(out['context_uncertain'][1:, 140:160].all())  # Taper never overrides.
        self.assertTrue((out['state'][3,125:130] == 2).all())
        self.assertTrue((out['state'][4,125:130] == 3).all())
        self.assertTrue((out['state'][1,120:140] == 1).all())  # Not just the selected boundary.
        self.assertTrue(shadow[100:160].all())
        self.assertEqual(int(r['shadow_override_sources'].sum()), 20)
        inc = training_targets(record, RAW, 0, 256, shadow)
        exc = training_targets(record, RAW, 0, 256, shadow, include_shadow_overrides=False)
        self.assertTrue(inc['approved_position'][1,120:140].all())
        self.assertFalse(exc['approved_position'][:,120:140].any())
        self.assertTrue((exc['trace'][:,120:140] == -1).all())
        self.assertTrue((exc['reliability'][:,120:140] == -1).all())
        for key in ('approved_position', 'reliable_manual', 'trace', 'reliability', 'anatomy', 'cnv_region_known', 'hyper_ref_known'):
            np.testing.assert_array_equal(inc[key][...,160:], exc[key][...,160:])
        self.assertTrue(inc['shadow_override_columns'][120:140].all())
        self.assertFalse(exc['cnv_region_known'][120:140].any())
        self.assertFalse(exc['hyper_ref_known'][:,120:140].any())

    def test_shadow_override_requires_a_surviving_normal_stroke(self):
        normal = dict(event('stroke', 120, 140, xs=[120,139], ys=[70,70], taper=0, drawing_reliability='reliable'), boundaries=[2])
        for events in ([dict(normal, drawing_reliability='unreliable')],
                       [dict(normal, drawing_reliability=None)],
                       [event('cnv_region')], [event('hyper_ref', xs=[120], ys=[100], diameter=9)],
                       [dict(event('reliable'), boundaries=[2])],
                       [normal, dict(event('erase_boundary',120,140), boundaries=[2])],
                       [normal, dict(event('reset_boundary',120,140), boundaries=[2])],
                       [normal, dict(event('not_traceable',120,140), boundaries=[2])],
                       [normal, dict(event('unreliable',120,140), boundaries=[2])]):
            self.assertFalse(resolve(events, RAW, 0, 256)['shadow_override_sources'].any())
        r = resolve([normal], RAW, 0, 256)
        self.assertTrue(r['shadow_override_sources'][2,120:140].all())
        self.assertFalse(resolve([], RAW, 0, 256)['shadow_override_sources'].any())

    def test_cnv_edge_can_override_shadow_and_multiple_sources_survive_one_erasure(self):
        edge = event('cnv_edge',120,140,xs=[120,139],ys=[170,170])
        normal = dict(event('stroke',120,140,xs=[120,139],ys=[70,70],taper=0,drawing_reliability='reliable'),boundaries=[2])
        events = [edge,normal,dict(event('erase_boundary',120,140),boundaries=[2])]
        r = resolve(events, RAW, 0, 256)
        self.assertTrue(r['shadow_override_sources'][-1,120:140].all())
        r = resolve(events+[dict(edge,erase=True)], RAW, 0, 256)
        self.assertFalse(r['shadow_override_sources'].any())

    def test_context_guard_overrides_confirmation_but_preserves_ilm_and_no_trace(self):
        events = [dict(event('reliable', 100, 160), boundaries=list(range(8))),
                  dict(event('not_traceable', 110, 115), boundaries=[2])]
        record = confirmed(events, policy=REVIEW_POLICY)
        r = resolve(record['events'], RAW, 0, 256)
        vessel = np.zeros(512, bool); vessel[100:120] = True
        shadow = np.zeros(512, bool); shadow[140:160] = True
        output = render(BASE, r, 0, 256, shadow, vessel)
        self.assertTrue((output['state'][1:, 100:110] == 3).all())
        self.assertTrue((output['state'][1:, 140:160] == 3).all())
        self.assertTrue((output['state'][0, 100:160] == 1).all())
        self.assertTrue((output['state'][2, 110:115] == 2).all())
        self.assertTrue(np.isnan(output['uncertain_estimates'][2, 110:115]).all())
        self.assertTrue(np.isnan(output['thickness_um'][:, vessel | shadow]).all())
        self.assertTrue((r['reliability'][:, 100:160] == 1).all())  # Replay is unchanged.
        t = training_targets(record, RAW, 0, 256, shadow, vessel=vessel)
        self.assertFalse(t['approved_position'][1:, vessel | shadow].any())
        self.assertTrue(t['approved_position'][0, 100:120].all())
        self.assertFalse(t['approved_position'][:, shadow].any())  # Original shadow safety retained for ILM.
        self.assertFalse((t['reliability'][1:, vessel | shadow] == 1).any())
        self.assertTrue(t['approved_position'][:, 200].all())

    def test_manual_reliable_stroke_and_cnv_edge_cannot_override_vessel_guard(self):
        vessel = np.zeros(512, bool); vessel[120:140] = True
        ev = [dict(event('stroke', 120, 140, xs=[120,139], ys=[70,70], taper=0, drawing_reliability='reliable'), boundaries=[2]),
              event('cnv_edge', 120, 140, xs=[120,139], ys=[170,170])]
        record = confirmed(ev, policy=REVIEW_POLICY)
        t = training_targets(record, RAW, 0, 256, np.zeros(512, bool), vessel=vessel)
        self.assertFalse(t['reliable_manual'][2, vessel].any())
        self.assertFalse(t['cnv_edge_valid'][vessel].any())
        self.assertFalse(t['cnv_edge_known'][vessel].any())
        self.assertTrue((t['cnv_edge_state'][vessel] == 1).all())  # Human annotation retained separately.

    def test_retinal_erase_is_local_preserves_judgments_and_can_be_redrawn(self):
        marks = [dict(event('unreliable', 110, 115), boundaries=[2])]
        erased = marks + [dict(event('erase_boundary', 100, 120), boundaries=[2])]
        r = resolve(erased, RAW, 0, 256)
        self.assertTrue(np.isnan(r['positions'][2, 100:120]).all())
        np.testing.assert_array_equal(r['positions'][[0, 1, 3, 4, 5, 6, 7]], RAW[[0, 1, 3, 4, 5, 6, 7]])
        self.assertTrue((r['trace'] == -1).all())
        self.assertTrue((r['anatomy'] == -1).all())
        self.assertTrue((r['reliability'][2, 110:115] == 0).all())
        stroke = dict(event('stroke', 102, 108, xs=[102, 107], ys=[70, 70], taper=0, drawing_reliability='reliable'), boundaries=[2])
        redrawn = resolve(erased + [stroke], RAW, 0, 256)
        self.assertTrue(np.isfinite(redrawn['positions'][2, 102:108]).all())
        self.assertTrue(np.isnan(redrawn['positions'][2, 108:120]).all())
        np.testing.assert_array_equal(resolve(marks, RAW, 0, 256)['positions'], RAW)

    def test_confirmed_edge_is_independent_of_region(self):
        record = confirmed([event('cnv_edge', 100, 110, xs=[100, 109], ys=[100, 100])], policy=REVIEW_POLICY)
        t = training_targets(record, RAW, 0, 256, np.zeros(512, bool))
        self.assertEqual(record['events'][-1]['acknowledged_warnings'], {})
        self.assertTrue(t['cnv_edge_valid'][100:110].all())
        self.assertFalse(t['cnv_region'].any())
        self.assertFalse(t['cnv_edge_known'][:100].any())

    def test_acknowledged_invalid_geometry_stays_out_of_positional_targets(self):
        raw = RAW.copy()
        raw[0, 10] = np.nan
        raw[0, 20] = -5
        raw[1, 30] = raw[2, 30] + 5
        record = confirmed([], policy=REVIEW_POLICY, baseline=raw)
        t = training_targets(record, raw, 0, 256, np.zeros(512, bool))
        self.assertTrue(t['eligible'])
        self.assertEqual(t['review_status'], 'Confirmed')
        self.assertTrue(t['approved_position'][:, 40].all())
        self.assertFalse(t['approved_position'][0, [10, 20]].any())
        self.assertFalse(t['approved_position'][1:3, 30].any())
        for field, value in [('acknowledged_warnings', {}), ('review_policy', None), ('review_policy', 'unknown')]:
            wrong = copy.deepcopy(record)
            wrong['events'][-1][field] = value
            with self.assertRaises(ValueError):
                resolve(wrong['events'], raw, 0, 256)
        changed = record['events'] + [event('cnv_region')]
        self.assertIsNone(resolve(changed, raw, 0, 256)['confirmation'])
        self.assertIsNotNone(resolve(changed[:-1], raw, 0, 256)['confirmation'])

    def test_outside_paint_override_preserves_positives_without_new_background(self):
        record = confirmed([event('hyper_ref', 100, 110, xs=[100, 109], ys=[100, 100], diameter=3)], policy=REVIEW_POLICY)
        t = training_targets(record, RAW, 0, 256, np.zeros(512, bool))
        self.assertIn('hyper_ref_outside_region', record['events'][-1]['acknowledged_warnings'])
        np.testing.assert_array_equal(t['hyper_ref_known'], t['hyper_ref'])
        self.assertFalse(t['cnv_region'].any())

    def test_edge_traceability_and_reliability_restore_independently(self):
        events = [event('cnv_edge', 120, 141, xs=[120, 140], ys=[100, 100]),
                  event('cnv_edge_mark', 120, 141, mark='not_traceable'),
                  event('cnv_edge_mark', 120, 141, mark='unreliable')]
        r = resolve(events, RAW, 0, 256)['lesions']
        self.assertTrue((r['cnv_edge_state'][120:141] == 3).all())
        restored = resolve(events+[event('cnv_edge_mark', 120, 141, mark='traceable')], RAW, 0, 256)['lesions']
        self.assertTrue((restored['cnv_edge_state'][120:141] == 2).all())
        reliable = resolve(events+[event('cnv_edge_mark', 120, 141, mark='reliable')], RAW, 0, 256)['lesions']
        self.assertTrue((reliable['cnv_edge_state'][120:141] == 3).all())
        self.assertFalse(reliable['cnv_edge_unreliable'][120:141].any())

    def test_region_is_separate_and_edge_does_not_move_layers_or_bridge_gaps(self):
        ev = [event('cnv_region'), event('cnv_edge', 120, 141, xs=[120, 140], ys=[35, 40]),
              event('cnv_edge', 155, 166, xs=[155, 165], ys=[220, 221])]
        r = resolve(ev, RAW, 0, 256)
        np.testing.assert_array_equal(r['positions'], RAW)
        self.assertFalse(r['excluded'].any())
        self.assertTrue(np.isnan(r['lesions']['cnv_edge'][141:155]).all())
        self.assertEqual(r['lesions']['cnv_edge'][165], 221)
        erased = resolve(ev+[event('cnv_edge', 125, 130, erase=True)], RAW, 0, 256)
        self.assertTrue(np.isnan(erased['lesions']['cnv_edge'][125:130]).all())

    def test_round_continuous_brush_and_canonical_crop_offset(self):
        s = L.empty(100, 70)
        ev = event('hyper_ref', 10, 51, xs=[10, 50], ys=[320, 320], diameter=6)
        L.apply(s, ev, 300)
        self.assertTrue(s['hyper_ref'][20, 10:51].all())
        self.assertTrue(s['hyper_ref'][17, 30])
        self.assertFalse(s['hyper_ref'][16, 30])
        self.assertFalse(s['hyper_ref'][16, 10])
        L.apply(s, dict(ev, erase=True), 300)
        self.assertFalse(s['hyper_ref'].any())

    def test_empty_confirmed_hyper_ref_is_negative_in_region_only(self):
        record = confirmed([event('cnv_region')])
        t = training_targets(record, RAW, 0, 256, np.zeros(512, bool))
        self.assertTrue(t['lesion_eligible'])
        self.assertTrue(t['hyper_ref_known'][:, 100:180].all())
        self.assertFalse(t['hyper_ref_known'][:, :100].any())
        self.assertFalse(t['hyper_ref'].any())
        self.assertTrue(t['cnv_edge_known'][100:180].all())
        self.assertFalse(t['cnv_edge_valid'].any())

    def test_old_confirmations_drafts_roles_and_synthetic_are_not_lesion_negatives(self):
        for record in (confirmed([], False), confirmed([event('cnv_region')])):
            if record['events'][-1].get('lesion_contract'):
                record['cursor'] -= 1
            t = training_targets(record, RAW, 0, 256, np.zeros(512, bool))
            self.assertFalse(t['lesion_eligible'])
            self.assertFalse(t['cnv_region_known'].any())
            self.assertFalse(t['hyper_ref_known'].any())
        record = confirmed([event('cnv_region')])
        for role in ('assessment', 'practice'):
            self.assertFalse(training_targets(record, RAW, 0, 256, np.zeros(512, bool), role)['lesion_eligible'])
        record['training_eligible'] = False
        self.assertFalse(training_targets(record, RAW, 0, 256, np.zeros(512, bool))['lesion_eligible'])

    def test_exclusions_shadows_and_uncertain_edge_mask_targets(self):
        ev = [event('cnv_region'), event('cnv_edge', 120, 150, xs=[120, 149], ys=[140, 140]),
              event('cnv_edge_mark', 125, 130, mark='unreliable'), event('exclude_image', 135, 140)]
        shadow = np.zeros(512, bool); shadow[145:150] = True
        record = confirmed(ev)
        t = training_targets(record, RAW, 0, 256, shadow, include_shadow_overrides=False)
        self.assertTrue(t['cnv_edge_valid'][120:125].all())
        for lo, hi in ((125, 130), (135, 140), (145, 150)):
            self.assertFalse(t['cnv_edge_valid'][lo:hi].any())
        self.assertFalse(t['hyper_ref_known'][:, 135:140].any())
        self.assertFalse(t['hyper_ref_known'][:, 145:150].any())
        included = training_targets(record, RAW, 0, 256, shadow)
        self.assertTrue(included['cnv_edge_valid'][145:150].all())
        self.assertTrue(included['shadow_override_columns'][145:150].all())
        self.assertFalse(included['cnv_edge_valid'][135:140].any())

    def test_revision_snapshot_and_definition_checks(self):
        record = confirmed([event('cnv_region')])
        for key, value in [('lesion_digest', 'bad'), ('lesion_definition', 'unknown')]:
            wrong = copy.deepcopy(record)
            wrong['events'][-1][key] = value
            with self.assertRaises(ValueError):
                resolve(wrong['events'], RAW, 0, 256)
        changed = record['events'] + [event('cnv_region', 100, 105, erase=True)]
        self.assertIsNone(resolve(changed, RAW, 0, 256)['lesion_confirmation'])
        self.assertIsNotNone(resolve(changed[:-1], RAW, 0, 256)['lesion_confirmation'])
        with self.assertRaises(ValueError):
            confirmed_outside = confirmed([event('cnv_edge', 100, 110, xs=[100, 109], ys=[100, 100])])
            resolve(confirmed_outside['events'], RAW, 0, 256)


def gui_checks(app, folder):
    errors = []
    old_hook = sys.excepthook
    def hook(typ, value, tb):
        import traceback
        traceback.print_exception(typ, value, tb)
        errors.append(str(value))
    sys.excepthook = hook
    v = fixture(folder, 'SYNTHETIC_LESION_TOOLS')
    v.data['raw_position_branch'] = v.data['raw_position_branch'].copy()
    v.data['raw_position_branch'][258, 0, 10:21] = np.nan
    v.data['raw_position_branch'][258, 1, 35] = -5
    v.data['raw_position_branch'][258, 2, 50:61] = RAW[3, 50:61] + 2
    v.data['vessel'][259, 120:126] = True
    v.data['shadow'][259, 140:146] = True
    v.data['shadow'][259, 190:210] = True
    w = Window('synthetic_lesion', entries=[v.entry], output=folder/'synthetic_lesion', autoload=False,
               cache=VolumeCache([v.entry], loader=lambda entry, image_budget: v))
    w.resize(1550, 950); w.show(); w.install_volume(v, 0, 256, False); app.processEvents(); w.fit()
    ed, c = w.editor, w.editor.canvas
    tool = ed.lesion_tools
    def click(widget):
        QTest.mouseClick(widget, Qt.MouseButton.LeftButton); app.processEvents()
        assert not errors, errors
    def answer_confirmation(answer, screenshot=None):
        seen = []
        def answer_popup():
            popup = app.activeModalWidget()
            try:
                assert isinstance(popup, QtWidgets.QMessageBox)
                assert popup.text() == 'Are you sure segmentation is fully complete?'
                assert popup.defaultButton() == popup.button(QtWidgets.QMessageBox.StandardButton.No)
                if screenshot:
                    popup.grab().save(str(folder/screenshot))
                seen.append(popup.informativeText())
                QTest.mouseClick(popup.button(answer), Qt.MouseButton.LeftButton)
            except Exception as exc:
                errors.append(str(exc))
                if popup is not None:
                    popup.reject()
        QtCore.QTimer.singleShot(50, answer_popup)
        result = confirm(ed)
        assert seen and not errors, errors
        return result
    def drag(start, stop, ctrl=False, button=Qt.MouseButton.LeftButton):
        mods = Qt.KeyboardModifier.ControlModifier if ctrl else Qt.KeyboardModifier.NoModifier
        a, b = [c.mapFromScene(QtCore.QPointF(*p)) for p in (start, stop)]
        QTest.mousePress(c.viewport(), button, mods, a)
        QTest.mouseMove(c.viewport(), b)
        QTest.mouseRelease(c.viewport(), button, mods, b)
        app.processEvents()
        assert not errors, errors
    click(ed.drawing_info); assert ed.drawing_mode_hint.isVisible()
    click(ed.drawing_info); assert not ed.drawing_mode_hint.isVisible()
    click(ed.confirm_info); assert ed.confirm_key.isVisible()
    click(ed.confirm_info); assert not ed.confirm_key.isVisible()
    click(ed.cnv_info); assert ed.cnv_hint.isVisible()
    assert 'horizontal extent' in ed.cnv_hint.text() and 'lower depth boundary' in ed.cnv_hint.text()
    click(ed.cnv_info); assert not ed.cnv_hint.isVisible()
    assert ed.body.layout().indexOf(ed.surface_list) < ed.body.layout().indexOf(ed.all_boundaries) < ed.body.layout().indexOf(ed.tools_box)
    click(ed.all_boundaries)
    assert ed.all_boundaries.text().endswith('OFF')
    assert all(not item.isVisible() for item in c._surface_items)
    assert all(item.path().isEmpty() for item in c._ruler_items.values())
    assert not ed.journal.path.exists()
    click(ed.all_boundaries)
    assert ed.all_boundaries.text().endswith('ON')
    assert all(item.isVisible() for item in c._surface_items)
    ed.surface_list.item(0).setCheckState(Qt.CheckState.Unchecked)
    assert ed.all_boundaries.text().endswith('SOME')
    click(ed.all_boundaries)
    assert all(item.isVisible() for item in c._surface_items)
    click(tool.buttons['cnv_region'])
    assert not ed.journal.path.exists()
    drag((100, 30), (180, 220))
    assert ed.resolved['lesions']['cnv_region'][101:180].all()
    assert not ed.resolved['excluded'].any()
    assert tool.erase.text() == 'Erase' and tool.erase.isEnabled()
    click(tool.erase)
    drag((110, 20), (115, 40))
    assert not ed.resolved['lesions']['cnv_region'][111:115].any()
    ed.undo_redo(-1)
    click(tool.erase)
    tool.select(None)
    ed.record_event('unreliable', 120, 140, [0])
    ed.record_event('not_traceable', 145, 160, [1])
    trace, reliability = ed.resolved['trace'].copy(), ed.resolved['reliability'].copy()
    for marking in ('unreliable', 'not_visible'):
        tool.select(None)
        click(ed.mark_buttons[marking])
        ed.unreliable_draw.setChecked(True)
        cursor = ed.journal.data['cursor']
        click(tool.buttons['cnv_region'])
        assert ed.journal.data['cursor'] == cursor  # A tool selection is never a judgment.
        assert ed.mark_mode is None and not ed.unreliable_draw.isChecked()
        assert not any(button.isChecked() for button in ed.mark_buttons.values())
        drag((100, 30), (180, 220), button=Qt.MouseButton.RightButton)
        assert ed.journal.events[-1]['action'] == 'cnv_region'
        np.testing.assert_array_equal(ed.resolved['trace'], trace)
        np.testing.assert_array_equal(ed.resolved['reliability'], reliability)
        assert not ed.resolved['excluded'].any()
    drag((101, 20), (105, 40), ctrl=True)
    assert not ed.resolved['lesions']['cnv_region'][102:105].any()
    ed.undo_redo(-1)
    click(tool.buttons['cnv_edge'])
    drag((120, 170), (160, 175))
    np.testing.assert_array_equal(ed.resolved['positions'], RAW)
    assert np.isfinite(ed.resolved['lesions']['cnv_edge'][121:160]).all()
    assert np.isnan(ed.resolved['lesions']['cnv_edge'][:119]).all()
    click(tool.erase)
    drag((130, 170), (135, 175))
    assert np.isnan(ed.resolved['lesions']['cnv_edge'][131:135]).all()
    ed.undo_redo(-1)
    click(tool.erase)
    click(tool.buttons['hyper_ref'])
    tool.dial.setValue(9)
    drag((130, 140), (148, 138))
    painted = ed.resolved['lesions']['hyper_ref'].copy()
    assert painted[140, 135]
    assert not ed.resolved['excluded'].any()
    click(tool.erase)
    drag((130, 140), (135, 139))
    assert ed.resolved['lesions']['hyper_ref'].sum() < painted.sum()
    QTest.keyClick(c, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier); app.processEvents()
    np.testing.assert_array_equal(ed.resolved['lesions']['hyper_ref'], painted)
    QTest.keyClick(c, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier); app.processEvents()
    assert ed.resolved['lesions']['hyper_ref'].sum() < painted.sum()
    QTest.keyClick(c, Qt.Key.Key_E); app.processEvents()
    assert not tool.erase.isChecked()
    drag((230, 140), (235, 140))
    cursor = ed.journal.data['cursor']
    assert not answer_confirmation(QtWidgets.QMessageBox.StandardButton.No)
    assert 'outside CNV region' in ed.status.text() and '#ff3030' in ed.status.styleSheet()
    assert ed.journal.data['cursor'] == cursor
    assert answer_confirmation(QtWidgets.QMessageBox.StandardButton.Yes)
    assert 'hyper_ref_outside_region' in ed.resolved['confirmation']['acknowledged_warnings']
    ed.undo_redo(-1)  # Undo override confirmation, then the outside paint.
    ed.undo_redo(-1)
    tool.select('cnv_edge')
    drag((220, 170), (240, 175))
    assert confirm(ed)  # Outside edge alone does not ask for a popup.
    assert not ed.resolved['confirmation']['acknowledged_warnings']
    tool.show.setChecked(False)
    assert not confirm(ed) and tool.show.isChecked()
    assert confirm(ed)
    assert ed.resolved['lesion_confirmation'] is not None
    cursor = ed.journal.data['cursor']
    click(ed.all_boundaries)
    assert not any(item.isVisible() for item in [tool.region_item, tool.mask_item, *tool.edge_items])
    assert ed.resolved['lesion_confirmation'] is not None and ed.journal.data['cursor'] == cursor
    assert not confirm(ed)  # First confirmation click reveals the curves without approving again.
    assert ed.all_boundaries.text().endswith('ON') and ed.journal.data['cursor'] == cursor
    assert all(item.isVisible() for item in [tool.region_item, tool.mask_item, *tool.edge_items])
    tool.show.setChecked(False)
    assert ed.all_boundaries.text().endswith('SOME')
    click(ed.all_boundaries)
    assert tool.show.isChecked() and ed.all_boundaries.text().endswith('ON')
    before = L.digest(ed.resolved['lesions'])
    path = ed.journal.path
    w.save_all()
    disk = read(path)
    assert not disk['training_eligible']
    assert L.digest(resolve(disk['events'][:disk['cursor']], RAW, 0, 256)['lesions']) == before
    w.map_tabs.setCurrentIndex(1); app.processEvents()
    assert w.coverage_info.isVisible() and not w.coverage_hint.isVisible()
    w.grab().save(str(folder/'lesion_tools_collapsed.png'))
    click(w.coverage_info); assert w.coverage_hint.isVisible()
    click(ed.drawing_info); click(ed.confirm_info); click(ed.cnv_info)
    w.grab().save(str(folder/'lesion_tools_expanded.png'))
    click(w.coverage_info); click(ed.drawing_info); click(ed.confirm_info); click(ed.cnv_info)
    w.install_volume(v, 0, 257, False); app.processEvents()
    assert not ed.resolved['lesions']['hyper_ref'].any()
    w.install_volume(v, 0, 256, False); app.processEvents()
    assert L.digest(ed.resolved['lesions']) == before
    assert ed.resolved['lesion_confirmation'] is not None
    tool.select('hyper_ref')
    drag((160, 130), (164, 130))
    assert ed.resolved['lesion_confirmation'] is None
    ed.undo_redo(-1)
    assert ed.resolved['lesion_confirmation'] is not None
    QTest.keyClick(c, Qt.Key.Key_2); app.processEvents()
    assert tool.mode is None
    assert w.navigator._review_lines[0].pen().color().name() == '#41e36f'
    assert w.navigator._cursor.pen().color().name() == '#ff9600'
    QTest.keyClick(c, Qt.Key.Key_E); app.processEvents()
    assert tool.erase.isChecked()
    original = ed.resolved['positions'].copy()
    drag((200, 80), (210, 80))
    assert ed.journal.events[-1]['action'] == 'erase_boundary'
    assert np.isnan(ed.resolved['positions'][1, 201:210]).all()
    assert ed.resolved['confirmation'] is None
    assert w.navigator._review_lines[0].pen().color().name() == '#ffea00'
    np.testing.assert_array_equal(ed.resolved['positions'][[0, 2, 3, 4, 5, 6, 7]], original[[0, 2, 3, 4, 5, 6, 7]])
    w.save_all()
    w.install_volume(v, 0, 257, False); app.processEvents()
    w.install_volume(v, 0, 256, False); app.processEvents()
    assert np.isnan(ed.resolved['positions'][1, 201:210]).all()
    ed.undo_redo(-1)
    np.testing.assert_array_equal(ed.resolved['positions'], original)
    assert ed.resolved['confirmation'] is not None
    tool.erase.setChecked(False)
    w.save_all()
    w.install_volume(v, 0, 258, False); app.processEvents(); w.fit()
    assert not answer_confirmation(QtWidgets.QMessageBox.StandardButton.No, 'confirmation_warning_popup.png')
    assert not ed.journal.path.exists()  # Cancel is display-only.
    bars = [item for item in ed._extras if item.data(0) == 'unresolved_boundary']
    assert {item.data(1) for item in bars} == {0, 1, 2, 3}
    assert all(item.pen().color().name() == '#ff3030' and not item.path().isEmpty() for item in bars)
    assert '#ff3030' in ed.status.styleSheet()
    w.grab().save(str(folder/'unresolved_red_bars.png'))
    assert answer_confirmation(QtWidgets.QMessageBox.StandardButton.Yes)
    assert ed.resolved['review_status'] == 'Confirmed'
    assert not ed.resolved['approved'][ed.resolved['unresolved']].any()
    invalid_path = ed.journal.path
    w.save_all()
    w.install_volume(v, 0, 257, False); app.processEvents()
    assert '#ff3030' not in ed.status.styleSheet()
    w.install_volume(v, 0, 258, False); app.processEvents()
    assert ed.resolved['confirmation']['acknowledged_warnings']
    disk = read(invalid_path)
    assert resolve(disk['events'][:disk['cursor']], v.data['raw_position_branch'][258], 0, 256)['confirmation']
    ed.undo_redo(-1); assert ed.resolved['confirmation'] is None
    ed.undo_redo(1); assert ed.resolved['confirmation'] is not None
    w.install_volume(v, 0, 259, False); app.processEvents(); w.fit()
    orange = next(item for item in ed._extras if item.data(0) == 'automatic_shadow_tint')
    assert not orange.path().isEmpty() and orange.brush().color().name() == '#ffad55'
    tool.select('cnv_edge')
    drag((110, 175), (130, 175))
    ed.record_event('reliable', 100, 180, list(range(8)))
    ed.record_event('not_traceable', 122, 125, [2])
    assert confirm(ed)
    assert (ed.rendered['state'][1:, 140:146] == 3).all()
    assert (ed.rendered['state'][1:, 120:122] == 3).all()
    assert (ed.rendered['state'][0, 100:180] == 1).all()
    assert (ed.rendered['state'][2, 122:125] == 2).all()
    tool.select(None)
    ed.surface_list.setCurrentRow(1)
    ed.unreliable_draw.setChecked(False)
    drag((139, float(RAW[1,140])), (147, float(RAW[1,140])))
    assert ed.rendered['shadow_override_columns'][140:146].all()
    assert not ed.rendered['context_uncertain'][:,140:146].any()
    assert (ed.rendered['state'][:,140:146] == 1).all()
    assert np.isfinite(ed.rendered['thickness_um'][:,140:146]).all()
    assert w._shadow_overrides[259,140:146].all()
    ed.undo_redo(-1)
    assert ed.rendered['effective_shadow_mask'][140:146].all()
    ed.undo_redo(1)
    assert not ed.rendered['effective_shadow_mask'][140:146].any()
    assert confirm(ed)
    overlays = list(v.overlays)
    overlays[1] = overlays[1].copy(); overlays[1][259, 160:166] = True
    protected = fingerprint(ed.journal.path)
    with patch('octa_seg_v3.providers.context_overlays', return_value=tuple(overlays)):
        w.refresh_overlays()
    assert fingerprint(ed.journal.path) == protected
    assert (ed.rendered['state'][1:, 160:166] == 3).all()
    assert not tool.edge_items[1].path().isEmpty()
    assert np.isnan(ed.rendered['thickness_um'][:, 160:166]).all()
    tool.select(None)
    assert ed.confirm_button.height() >= 44
    w.grab().save(str(folder/'confirmed_vessel_shadow_uncertainty.png'))
    w.save_all()
    w.install_volume(v, 0, 257, False); app.processEvents()
    w.install_volume(v, 0, 259, False); app.processEvents()
    assert ed.resolved['confirmation'] is not None
    assert (ed.rendered['state'][1:, 140:146] == 1).all()
    assert ed.rendered['effective_shadow_mask'][190:210].all()
    assert (ed.rendered['state'][2, 122:125] == 2).all()
    w.install_volume(v, 0, 256, False); app.processEvents()
    ed.read_only = True
    file_hash = fingerprint(path)
    tool.select('hyper_ref')
    drag((130, 140), (150, 140))
    assert fingerprint(path) == file_hash
    w.close(); app.processEvents()
    sys.excepthook = old_hook
    assert not errors, errors
    return dict(callback_errors=errors, gestures=True, saved_reopened=True, undo_redo=True,
                confirmation=True, confirmation_override_cancel_save_reopen=True, bright_red_unresolved_bars=True,
                independent_cnv_edge_confirmation=True, information_toggles=True, all_boundaries_toggle=True,
                cnv_region_tool_priority_preserves_judgments=True, universal_erase_save_reopen_undo=True,
                navigator_green_confirmed_orange_current=True, persistent_vessel_shadow_guard=True,
                column_wide_shadow_override_orange_tint=True, read_only=True)


def main():
    folder = OUT/'verification'/('lesions_' + time.strftime('%Y%m%d_%H%M%S'))
    folder.mkdir(parents=True)
    protected = {str(p): fingerprint(p) for root in (V3/'reviewers', OUT/'reviewers', ROOT/'outputs/cnv_labels')
                 for p in root.rglob('*') if p.is_file() and p.suffix in ('.json', '.npz')}
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(LesionTests))
    if not result.wasSuccessful():
        raise SystemExit(1)
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([]); configure_v3_app(app)
    report = dict(contract_tests=result.testsRun, qt=gui_checks(app, folder), directory=str(folder),
                  screenshots_are='offscreen rendering; not proof of interactive desktop visibility')
    report['protected_changes'] = [p for p, sha in protected.items() if fingerprint(p) != sha]
    report['protected_files'] = len(protected)
    assert not report['protected_changes'], report['protected_changes']
    write(folder/'results.json', report)
    write(OUT/'verification/latest_lesions.json', report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
