"""Synthetic migration, independent edit, save/reopen and display-only toggle checks."""
import copy
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import time
import unittest
import numpy as np
from PySide6.QtTest import QTest
from . import lesions as L
from .feedback import resolve, state_digest, training_targets
from .verify import RAW, fixture, ContractTests
from .verify_review import NewContractTests
from .verify_lesions import LesionTests, confirmed, event
from .label_gui import Journal, Qt, QtCore, QtWidgets
from .gui import Window, configure_v3_app
from .common import OUT, write, fingerprint
from .controls import confirm
from .data import VolumeCache


def legacy_record():
    record = confirmed([event('cnv_region', 100, 180), event('hyper_ref', 120, 121, xs=[120], ys=[100], diameter=9)])
    for ev in record['events']:
        ev['lesion_definition'] = L.LEGACY_VERSION
        if ev['action'] == 'confirm_bscan':
            state = resolve(record['events'][:-1], RAW, 0, 256)['lesions']
            ev.update(lesion_definitions=L.LEGACY_DEFINITIONS, lesion_snapshot=L.snapshot(state, L.LEGACY_VERSION),
                      lesion_digest=L.digest(state, L.LEGACY_VERSION))
    return record


class DistinctionTests(unittest.TestCase):
    def test_legacy_confirmation_and_explicit_migration_preserve_geometry(self):
        record = legacy_record()
        original = resolve(record['events'], RAW, 0, 256)
        for who, kind in L.LEGACY_MAPPING.items():
            migration = dict(action=L.MIGRATION_ACTION, reviewer_id=who, destination=kind,
                             from_definition=L.LEGACY_VERSION, lesion_definition=L.DEFINITION_VERSION,
                             legacy_region_runs=[[100, 180]])
            result = resolve(record['events'] + [migration], RAW, 0, 256)
            self.assertEqual(state_digest(result), state_digest(original))
            np.testing.assert_array_equal(result['approved'], original['approved'])
            self.assertEqual(result['confirmation'], original['confirmation'])
            np.testing.assert_array_equal(result['lesions'][kind], original['lesions']['cnv_region'])
            self.assertFalse(result['lesions']['cnv_region'].any())
            self.assertFalse(result['lesions']['cnv_full' if kind == 'cnv_core' else 'cnv_core'].any())
            self.assertIsNone(result['lesion_confirmation'])
            updated = dict(record, events=record['events'] + [migration], cursor=record['cursor'] + 1)
            targets = training_targets(updated, RAW, 0, 256, np.zeros(512, bool))
            self.assertFalse(targets['cnv_core_known'].any())
            self.assertFalse(targets['cnv_full_known'].any())
            # New strokes and confirmations replay without rewriting any historical event.
            new_events = updated['events'] + [event('cnv_full', 90, 190)]
            new_record = confirmed(new_events)
            self.assertIsNotNone(resolve(new_record['events'], RAW, 0, 256)['lesion_confirmation'])

    def test_overlapping_categories_erase_independently(self):
        events = [event('cnv_core', 100, 180), event('cnv_full', 80, 200), event('cnv_core', 120, 140, erase=True)]
        state = resolve(events, RAW, 0, 256)['lesions']
        self.assertFalse(state['cnv_core'][120:140].any())
        self.assertTrue(state['cnv_full'][80:200].all())
        record = confirmed(events)
        targets = training_targets(record, RAW, 0, 256, np.zeros(512, bool))
        self.assertTrue(targets['cnv_core_known'].all())
        self.assertTrue(targets['cnv_full_known'].all())
        self.assertFalse(targets['cnv_region_known'].any())

    def test_invalid_migration_and_false_absence_rejected(self):
        record = legacy_record()
        migration = dict(action=L.MIGRATION_ACTION, reviewer_id='lead', destination='cnv_full',
                         from_definition=L.LEGACY_VERSION, lesion_definition=L.DEFINITION_VERSION,
                         legacy_region_runs=[[100, 180]])
        with self.assertRaises(ValueError):
            resolve(record['events'] + [migration], RAW, 0, 256)
        targets = training_targets(record, RAW, 0, 256, np.zeros(512, bool))
        self.assertFalse(targets['cnv_full_known'].any())
        self.assertFalse(targets['cnv_core_known'].any())


def qt_checks(folder):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    configure_v3_app(app)
    errors = []
    import sys
    old_hook = sys.excepthook
    def hook(kind, error, tb):
        errors.append(str(error))
        sys.__excepthook__(kind, error, tb)
    sys.excepthook = hook
    v = fixture(folder, 'SYNTHETIC_CNV_DISTINCTIONS')
    masks = list(v.overlays)
    masks[0] = masks[0].copy(); masks[0][256, 60:220] = True
    v.overlays = tuple(masks)
    from unittest.mock import patch
    context = patch('octa_seg_v3.providers.context_overlays', return_value=tuple(masks))
    context.start()
    w = Window('synthetic_distinctions', entries=[v.entry], output=folder/'synthetic_distinctions', autoload=False,
               cache=VolumeCache([v.entry], loader=lambda entry, image_budget: v))
    w.resize(1700, 1050); w.show(); w.install_volume(v, 0, 256, False)
    app.processEvents(); w.fit()
    ed, c, tool = w.editor, w.editor.canvas, w.editor.lesion_tools
    def click(widget):
        QTest.mouseClick(widget, Qt.MouseButton.LeftButton); app.processEvents()
        assert not errors, errors
    def drag(a, b):
        a, b = [c.mapFromScene(QtCore.QPointF(*p)) for p in (a, b)]
        QTest.mousePress(c.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, a)
        QTest.mouseMove(c.viewport(), b)
        QTest.mouseRelease(c.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, b)
        app.processEvents(); assert not errors, errors
    click(ed.cnv_info)
    assert ed.cnv_hint.isVisible()
    assert L.CORE_DEFINITION in ed.cnv_hint.text() and L.FULL_DEFINITION in ed.cnv_hint.text()
    assert tool.buttons['cnv_core'].geometry().center().y() == tool.buttons['cnv_full'].geometry().center().y()
    assert abs(tool.buttons['cnv_core'].geometry().center().y() - ed.cnv_info.geometry().center().y()) < 3
    w.grab().save(str(folder/'cnv_definitions.png'))
    click(ed.cnv_info)
    click(tool.buttons['cnv_core']); drag((100, 50), (180, 150))
    click(tool.buttons['cnv_full']); drag((80, 50), (200, 150))
    assert ed.resolved['lesions']['cnv_core'][102:178].all()
    assert ed.resolved['lesions']['cnv_full'][82:198].all()
    full = ed.resolved['lesions']['cnv_full'].copy()
    click(tool.buttons['cnv_core']); click(tool.erase); drag((120, 50), (140, 150)); click(tool.erase)
    assert not ed.resolved['lesions']['cnv_core'][122:138].any()
    np.testing.assert_array_equal(full, ed.resolved['lesions']['cnv_full'])
    ed.undo_redo(-1); assert ed.resolved['lesions']['cnv_core'][122:138].all()
    ed.undo_redo(1); assert not ed.resolved['lesions']['cnv_core'][122:138].any()
    before = fingerprint(ed.journal.path)
    assert any(i.data(0) == 'cnv_context_outline' for i in ed._extras)
    w.map_tabs.setCurrentIndex(0); w.update_map(); app.processEvents()
    pixmap_on = w.navigator._overlay.pixmap().toImage().copy()
    click(ed.show_auto_cnv)
    assert not any(i.data(0) == 'cnv_context_outline' for i in ed._extras)
    assert pixmap_on != w.navigator._overlay.pixmap().toImage(), (w.map_tabs.currentIndex(), int(v.overlays[0].sum()), pixmap_on.pixelColor(100, 256).getRgb(), w.navigator._overlay.pixmap().toImage().pixelColor(100, 256).getRgb())
    assert all(i.isVisible() for i in tool.region_items.values())
    assert fingerprint(ed.journal.path) == before
    np.testing.assert_array_equal(v.overlays[0], masks[0])
    click(ed.show_auto_cnv)
    assert any(i.data(0) == 'cnv_context_outline' for i in ed._extras)
    assert pixmap_on == w.navigator._overlay.pixmap().toImage()
    assert fingerprint(ed.journal.path) == before
    tool.select(None)
    assert confirm(ed)
    expected = copy.deepcopy(ed.resolved['lesions'])
    w.save_all()
    w.grab().save(str(folder/'cnv_independent_overlays.png'))
    w.install_volume(v, 0, 257, False); w.install_volume(v, 0, 256, False); app.processEvents()
    for key in L.REGION_KEYS:
        np.testing.assert_array_equal(expected[key], ed.resolved['lesions'][key])
    assert ed.resolved['lesion_confirmation'] is not None
    w.close(); app.processEvents(); sys.excepthook = old_hook
    context.stop()
    assert not errors, errors
    return dict(callback_errors=errors, distinct_drag_erase_undo_redo=True, save_reopen=True,
                info_text_exact_and_same_row=True, auto_toggle_bscan_and_enface=True,
                visibility_does_not_change_journal_or_auto_masks=True)


def main():
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c)
                               for c in (DistinctionTests, LesionTests, ContractTests, NewContractTests))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    folder = OUT/'verification'/('cnv_distinctions_' + time.strftime('%Y%m%d_%H%M%S'))
    folder.mkdir(parents=True)
    report = dict(unit_tests=result.testsRun, qt=qt_checks(folder), native_macos_execution_tested=False)
    write(folder/'results.json', report)
    print(folder)
    print(report)


if __name__ == '__main__':
    main()
