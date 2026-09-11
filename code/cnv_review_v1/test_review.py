"""Behavioral checks with synthetic data; human study labels are never written."""
import json
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PySide6.QtTest import QTest

from eight_surface.cnv_data import CnvScan
from eight_surface.config import CASCADE_VERSION, SURFACE_NAMES
from eight_surface import labels as L, provenance as P
from cnv_review_v1.data import (AutoSource, RegionStore, SurfaceIndex, default_config,
                                decode_mask, encode_mask, fingerprint, load_enface)
from cnv_review_v1.gui import MainWindow, QtWidgets, QtCore, Qt


def fake_scan(root):
    nrow, width, depth = 12, 40, 100
    surfaces = np.broadcast_to(np.linspace(12, 86, 8, dtype=np.float32)[None, :, None], (nrow, 8, width)).copy()
    return CnvScan("TS999_TEST", root / "base.npz", root / "source_processedVolumes.mat",
                   np.full((nrow, width, depth), 10, np.float32),
                   np.arange(nrow * width).reshape(nrow, width).astype(np.float32),
                   np.ones((nrow, width), np.float32), surfaces, np.ones_like(surfaces),
                   np.zeros((nrow, width), bool), tuple(SURFACE_NAMES), 1.12, (10, 110), False)


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = default_config()
        self.config["output"] = str(self.root / "new")
        self.config["manual_sources"] = [str(self.root / "original")]
        self.scan = fake_scan(self.root)
        self.window = MainWindow(self.config, [self.scan.segmentation_path], autoload=False)
        self.blank = np.zeros(self.scan.native_shape, bool)
        self.vessels = self.blank.copy()
        self.vessels[:, 5:9] = True
        self.region = self.blank.copy()
        self.region[3:7, 12:26] = True
        self.meta = dict(name="test auto", path=str(self.scan.segmentation_path))
        self.index = SurfaceIndex([self.root / "new/surface_labels", self.root / "original"])
        self.index.refresh(self.scan)
        self.store = RegionStore(self.root / "new/regions", self.scan, self.region)
        self.window.pending_index = 0
        self.window._loaded((self.scan, self.scan.surfaces.copy(), self.scan.confidence, self.meta,
                             (self.region, self.vessels, self.blank, self.blank, dict(status="test vessels", path=""), ""), self.index, self.store))
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.autosave.stop()
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.temp.cleanup()

    def test_opening_browsing_and_closing_never_makes_labels(self):
        self.window.navigate(0, 5)
        self.window.navigate(11, 20)
        self.window.save_all()
        self.assertFalse(list(self.root.rglob("*.npz")))
        self.assertFalse(list((self.root / "new/regions").glob("*.json")))

    def test_region_categories_notes_and_round_trip(self):
        self.window.category.setCurrentText("Other")
        self.assertFalse(self.store.regions[0].complete)
        self.window.notes.setPlainText("Border artifact; layering preserved in adjacent slices.")
        self.assertTrue(self.store.regions[0].complete)
        self.assertTrue(self.window.save_all())
        reopened = RegionStore(self.root / "new/regions", self.scan, self.blank)
        self.assertEqual(reopened.regions[0].notes, self.store.regions[0].notes)
        self.assertEqual(reopened.regions[0].category, "Other")
        self.assertTrue(np.array_equal(reopened.regions[0].mask, self.region))
        self.window.category.setCurrentText("Normal")
        self.window.save_all()
        self.assertTrue(list((self.root / "new/regions/history").glob("*.json")))

    def test_polygon_new_redraw_remove_undo_redo_keep_identity(self):
        self.window._outline_drawn([(1, 1), (5, 1), (5, 4), (1, 4)], "cnv_outline_add")
        self.assertEqual(len(self.store.regions), 2)
        uid = self.store.regions[1].id
        self.window.category.setCurrentText("Full Lesion")
        self.window.outline_mode(True)
        self.window._outline_drawn([(2, 2), (6, 2), (6, 5), (2, 5)], "cnv_outline_add")
        self.assertEqual(self.store.regions[1].id, uid)
        self.window.remove_region()
        self.assertEqual(len(self.store.regions), 1)
        self.window.undo_region()
        self.assertEqual(self.store.regions[1].id, uid)
        self.window.redo_region()
        self.assertEqual(len(self.store.regions), 1)

    def test_native_row_click_and_slider_link_editor_and_vessel_footprint(self):
        self.window.bscan_choice.setValue(8)
        self.assertEqual(int(self.window.editor.pack.bscan_index[0]), 8)
        self.assertEqual(self.window.bscan_slider.value(), 8)
        self.assertTrue(np.array_equal(self.window.editor._vessels, self.vessels[8]))
        canvas = self.window.structural
        canvas.fit()
        point = canvas.mapFromScene(QtCore.QPointF(20, 3))
        QTest.mouseClick(canvas.viewport(), Qt.MouseButton.LeftButton, pos=point)
        self.assertEqual(self.window.row, 3)
        self.assertEqual(int(self.window.editor.pack.bscan_index[0]), 3)

    def test_gui_edit_save_reopen_preserves_uncertainty_and_original_auto(self):
        self.window.navigate(4, 15)
        editor = self.window.editor
        editor.s = 1
        editor.taper_spin.setValue(0)
        editor.canvas.localMarked.emit(12, 20, "unreliable")
        editor.canvas.strokeFinished.emit([12, 16, 20], [25, 25, 25])
        state = editor.pack.states[0]
        self.assertTrue(state.local["local_drawn"][1, 12:21].all())
        self.assertTrue((state.local["local_reliability"][1, 12:21] == P.MARK_NO).all())
        editor.commit_current()
        path = L.label_path(self.root / "new/surface_labels", self.scan.scan_id, 4)
        before = fingerprint(path)
        original_auto = L.load_label(path)["auto_surfaces"].copy()
        self.window.navigate(5, 15)
        self.window.surfaces += 2
        self.window.navigate(4, 15)
        self.assertTrue(np.array_equal(editor.pack.states[0].auto, original_auto))
        self.assertEqual(fingerprint(path), before)
        self.assertTrue((editor.pack.states[0].local["local_reliability"][1, 12:21] == P.MARK_NO).all())
        self.window.navigate(5, 15)
        self.assertTrue(np.array_equal(editor.pack.states[0].current, self.window.surfaces[5]))
        self.assertEqual(self.index.footprint(4, 40).sum(), 9)
        self.assertFalse(list((self.root / "original").glob("*.npz")))

    def test_rejected_review_remains_selectable_without_rewriting(self):
        self.window.navigate(2, 10)
        self.window.editor.set_verdict("rejected")
        self.window.save_all()
        path = L.label_path(self.root / "new/surface_labels", self.scan.scan_id, 2)
        before = fingerprint(path)
        self.window.navigate(3, 10)
        self.window.navigate(2, 10)
        self.assertEqual(self.window.editor.pack.states[0].verdict, "rejected")
        self.window.save_all()
        self.assertEqual(fingerprint(path), before)

    def test_unedited_review_uses_new_auto_without_transferring_old_acceptance(self):
        self.window.navigate(2, 10)
        editor = self.window.editor
        editor.canvas.localMarked.emit(2, 5, "reviewed")
        editor.canvas.localMarked.emit(12, 15, "unreliable")
        editor.set_verdict("accepted")
        self.window.save_all()
        path = L.label_path(self.root / "new/surface_labels", self.scan.scan_id, 2)
        before = fingerprint(path)
        self.window.navigate(3, 10)
        self.window.surfaces += 2
        self.window.navigate(2, 10)
        state = editor.pack.states[0]
        self.assertTrue(np.array_equal(state.current, self.window.surfaces[2]))
        self.assertIsNone(state.verdict)
        self.assertFalse(state.local["local_reviewed"].any())
        self.assertTrue((state.local["local_reliability"][0, 2:6] == P.MARK_UNKNOWN).all())
        self.assertTrue((state.local["local_reliability"][0, 12:16] == P.MARK_NO).all())
        self.window.save_all()
        self.assertEqual(fingerprint(path), before)

    def test_restoring_unreliable_checkboxes_is_not_a_human_edit(self):
        self.window.navigate(0, 10)
        editor = self.window.editor
        editor.canvas.strokeFinished.emit([2, 5, 8], [11, 11, 11])
        editor.surface_list.item(2).setCheckState(Qt.CheckState.Unchecked)
        editor.surface_list.item(7).setCheckState(Qt.CheckState.Unchecked)
        editor.set_verdict("rejected")
        self.window.save_all()
        path = L.label_path(self.root / "new/surface_labels", self.scan.scan_id, 0)
        before = fingerprint(path)
        record = L.load_label(path)
        self.window.navigate(4, 10)
        self.window.navigate(0, 10)
        state = editor.pack.states[0]
        self.assertTrue(np.array_equal(state.reliable, record["surface_reliable"]))
        self.assertEqual(editor.signature(), editor._saved_signature)
        self.window.save_all()
        self.assertEqual(fingerprint(path), before)

    def test_original_annotation_is_read_only_even_when_resumed_and_edited(self):
        self.window.navigate(4, 10)
        self.window.editor.canvas.strokeFinished.emit([2, 5, 8], [10, 10, 10])
        self.window.save_all()
        created = L.label_path(self.root / "new/surface_labels", self.scan.scan_id, 4)
        original = L.label_path(self.root / "original", self.scan.scan_id, 4)
        original.parent.mkdir()
        created.replace(original)  # synthetic fixture produced via GUI, not a fabricated study annotation
        self.index.refresh(self.scan)
        self.window.navigate(5, 10)
        self.window.navigate(4, 10)
        before = fingerprint(original)
        self.window.editor.canvas.strokeFinished.emit([10, 12, 14], [11, 11, 11])
        self.window.save_all()
        self.assertEqual(fingerprint(original), before)
        self.assertTrue(created.exists())
        self.assertEqual(self.index.records[4][0], created)

    def test_other_without_explanation_survives_as_draft(self):
        self.window.category.setCurrentText("Other")
        self.window.save_all()
        data = json.loads(self.store.path.read_text())
        self.assertFalse(data["regions"][0]["classification_complete"])
        self.assertEqual(data["regions"][0]["category"], "Other")

    def test_region_concurrent_change_detected(self):
        self.window.category.setCurrentText("Normal")
        self.window.save_all()
        self.store.path.write_text(self.store.path.read_text() + "\n")
        self.window.category.setCurrentText("Full Lesion")
        with self.assertRaisesRegex(RuntimeError, "another window"):
            self.store.save({}, [], {})
        # Restore expected hash for clean teardown; it is a synthetic review.
        self.store.disk_hash = fingerprint(self.store.path)

    def test_mask_round_trip_and_invalid_coordinates(self):
        self.assertTrue(np.array_equal(self.region, decode_mask(encode_mask(self.region), self.region.shape)))
        with self.assertRaises(ValueError):
            decode_mask([[0, -1, 4]], (12, 40))


class SourceTests(unittest.TestCase):
    def test_auto_priority_shape_identity_and_crop_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            scan = fake_scan(root)
            old, new = root / "old", root / "new"
            old.mkdir(); new.mkdir()
            fields = dict(scan_id=np.array([scan.scan_id]), surface_names=np.array(SURFACE_NAMES),
                          cascade_version=np.array([CASCADE_VERSION]), source=np.array([str(scan.source_volume)]),
                          retina_band=np.array(scan.retina_band), bscan_index=np.arange(12))
            np.savez(old / f"{scan.scan_id}.npz", surfaces=scan.surfaces, **fields)
            path = new / f"{scan.scan_id}_pack.npz"
            np.savez(path, surfaces=scan.surfaces + 1, **fields)
            provider = AutoSource([dict(name="new", directory=str(new)), dict(name="fallback", directory=str(old))])
            surfaces, _, meta = provider.load(scan)
            self.assertTrue(np.array_equal(surfaces, scan.surfaces + 1))
            self.assertEqual(meta["name"], "new")
            fields["retina_band"] = [11, 111]
            np.savez(path, surfaces=scan.surfaces, **fields)
            with self.assertRaisesRegex(ValueError, "crop differs"):
                provider.load(scan)
            fields["retina_band"] = scan.retina_band
            np.savez(path, surfaces=scan.surfaces[:2], **fields)
            with self.assertRaisesRegex(ValueError, "full native volume"):
                provider.load(scan)
            fields["source"] = np.array(["wrong.mat"])
            np.savez(path, surfaces=scan.surfaces, **fields)
            with self.assertRaisesRegex(ValueError, "source volume mismatch"):
                provider.load(scan)
            path.unlink()
            self.assertEqual(provider.load(scan)[2]["name"], "fallback")

    def test_saved_empty_vessel_draft_beats_proposal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            scan = fake_scan(root)
            path = root / f"{scan.scan_id}_cnv.npz"
            path.touch()
            blank = np.zeros(scan.native_shape, bool)
            record = dict(native_shape=scan.native_shape, scan_id=scan.scan_id,
                          source_volume=str(scan.source_volume), cnv_mask=blank, onh_mask=blank,
                          onh_edge_mask=blank, vasculature_mask=blank, reviewed_targets=[True, False, False],
                          vasculature_proposal_path="seed", vasculature_origin="automatic_proposal")
            with patch("cnv_review_v1.data.CL.load_label", return_value=record), patch("cnv_review_v1.data.load_proposal") as proposal:
                result = load_enface(scan, root, root)
                proposal.assert_not_called()
                self.assertFalse(result[1].any())


if __name__ == "__main__":
    unittest.main(verbosity=2)
