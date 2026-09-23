"""GUI lifecycle tests for automatic vessel drafts and preserved manual work."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from eight_surface import cnv_labels as CL
from eight_surface.cnv_data import CnvScan
from eight_surface.cnv_gui import MainWindow, QtWidgets
from eight_surface.config import SURFACE_NAMES
from eight_surface.vasculature_proposals import PROPOSAL_VERSION, load_proposal


def fake_scan(scan_id="TS999_TEST"):
    surfaces = np.broadcast_to(np.linspace(3, 27, len(SURFACE_NAMES))[None, :, None],
                               (32, len(SURFACE_NAMES), 48)).astype(np.float32).copy()
    return CnvScan(
        scan_id=scan_id, segmentation_path=Path(f"{scan_id}.npz"),
        source_volume=Path("source_processedVolumes.mat"),
        structural_band=np.full((32, 48, 32), 10, np.float32),
        structural_enface=np.arange(32*48, dtype=np.float32).reshape(32, 48),
        octa_enface=np.ones((32, 48), np.float32), surfaces=surfaces,
        confidence=np.ones_like(surfaces), shadow=np.zeros((32, 48), bool),
        surface_names=tuple(SURFACE_NAMES), px_um=1.12, retina_band=(100, 132),
        vitreous_at_high_index=False, animal="TS999", eye="OD", day_label="D7")


def write_proposal(directory, scan, mask):
    directory.mkdir(exist_ok=True)
    path = directory / f"{scan.scan_id}_proposal.npz"
    np.savez_compressed(
        path, predicted_vasculature_mask=mask, scan_id=np.array([scan.scan_id]),
        source_volume=np.array([str(scan.source_volume)]),
        retina_band=np.array(scan.retina_band), axis_order=np.array(["B-scan,A-line"]),
        proposal_format_version=np.array([PROPOSAL_VERSION]),
        human_reviewed=np.array([False]), method=np.array(["test-rule"]))
    return path


class VesselProposalGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.scan = fake_scan()
        self.mask = np.zeros(self.scan.native_shape, bool)
        self.mask[3:29, 20:29] = True
        self.proposals = self.root / "proposals"
        write_proposal(self.proposals, self.scan, self.mask)
        self.read_patch = patch("eight_surface.cnv_gui.read_scan", return_value=self.scan)
        self.read_patch.start()
        self.windows = []

    def tearDown(self):
        for window in self.windows:
            window.close()
        self.read_patch.stop()
        self.temp.cleanup()

    def open(self):
        window = MainWindow([self.scan.segmentation_path], self.root / "labels",
                            self.root / "surfaces", self.root / "lines", self.proposals)
        self.windows.append(window)
        return window

    def existing_label(self, vessels, reviewed, **kwargs):
        return CL.save_label(
            self.root / "labels", scan_id=self.scan.scan_id,
            cnv_mask=np.zeros(self.scan.native_shape, bool), vasculature_mask=vessels,
            source_volume=self.scan.source_volume, source_segmentation=self.scan.segmentation_path,
            retina_band=self.scan.retina_band, vitreous_at_high_index=False,
            reviewed_targets=[True, reviewed, False], **kwargs)

    def test_seed_starts_unreviewed_and_close_without_edits_writes_no_label(self):
        window = self.open()
        np.testing.assert_array_equal(window.vasculature_mask, self.mask)
        self.assertFalse(window.reviewed_targets.any())
        self.assertFalse(window.dirty)
        window.close()
        self.assertFalse(CL.label_path(self.root / "labels", self.scan.scan_id).exists())

    def test_edit_undo_redo_save_review_and_reload_preserve_seed_provenance(self):
        window = self.open()
        window.brush_size.setValue(5)
        window.apply_stroke([(24, 12), (24, 20)], "vasculature_brush_erase")
        edited = window.vasculature_mask.copy()
        touched = window.vasculature_brush_touched.copy()
        self.assertTrue(touched.any())
        self.assertFalse(window.reviewed_targets[1])
        window.undo()
        np.testing.assert_array_equal(window.vasculature_mask, self.mask)
        self.assertFalse(window.vasculature_brush_touched.any())
        window.redo()
        np.testing.assert_array_equal(window.vasculature_brush_touched, touched)
        record = CL.load_label(window.save())
        np.testing.assert_array_equal(record["vasculature_initial_mask"], self.mask)
        np.testing.assert_array_equal(record["vasculature_mask"], edited)
        self.assertFalse(record["reviewed_targets"][1])
        self.assertEqual(record["vasculature_origin"], "automatic_proposal")
        self.assertEqual(len(record["vasculature_proposal_sha256"]), 64)
        window.review_checks[1].setChecked(True)
        window.save()
        # A newly generated proposal must not overwrite a saved correction.
        write_proposal(self.proposals, self.scan, np.ones_like(self.mask))
        window.load_scan(0)
        np.testing.assert_array_equal(window.vasculature_mask, edited)
        self.assertTrue(window.reviewed_targets[1])
        self.assertEqual(window.vasculature_brush_touched.sum(), touched.sum())

    def test_saved_empty_draft_is_not_reseeded(self):
        window = self.open()
        window.brush_size.setValue(160)
        window.apply_stroke([(24, 16)], "vasculature_brush_erase")
        self.assertFalse(window.vasculature_mask.any())
        self.assertFalse(window.reviewed_targets[1])
        window.save()
        window.load_scan(0)
        self.assertFalse(window.vasculature_mask.any())
        self.assertFalse(window.reviewed_targets[1])
        self.assertTrue(window.vasculature_proposal_path)

    def test_saved_manual_mask_and_reviewed_absence_take_priority(self):
        for reviewed, manual in ((True, ~self.mask), (False, ~self.mask),
                                 (True, np.zeros_like(self.mask))):
            with self.subTest(reviewed=reviewed, nonempty=bool(manual.any())):
                path = self.existing_label(manual, reviewed)
                before_hash = hashlib.sha256(path.read_bytes()).hexdigest()
                window = self.open()
                np.testing.assert_array_equal(window.vasculature_mask, manual)
                self.assertFalse(window.vasculature_proposal_path)
                window.close()
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before_hash)

    def test_unreviewed_blank_class_gets_seed_without_changing_cnv_or_onh(self):
        onh = np.zeros_like(self.mask); onh[1:5, 1:5] = True
        path = self.existing_label(np.zeros_like(self.mask), False, onh_mask=onh, notes="existing notes")
        window = self.open()
        np.testing.assert_array_equal(window.vasculature_mask, self.mask)
        np.testing.assert_array_equal(window.onh_mask, onh)
        self.assertEqual(window.notes.toPlainText(), "existing notes")
        self.assertEqual(window.reviewed_targets.tolist(), [True, False, False])
        saved = CL.load_label(window.save())
        self.assertFalse(saved["reviewed_targets"][1])
        self.assertTrue(saved["reviewed_targets"][0])

    def test_navigation_autosaves_draft_without_promoting_review(self):
        window = self.open()
        window.apply_stroke([(24, 16)], "vasculature_brush_erase")
        edited = window.vasculature_mask.copy()
        window.load_scan(0)  # exercises the same save-before-navigation lifecycle
        np.testing.assert_array_equal(window.vasculature_mask, edited)
        record = CL.load_label(CL.label_path(self.root / "labels", self.scan.scan_id))
        self.assertFalse(record["reviewed_targets"][1])
        self.assertTrue(record["vasculature_brush_touched"].any())

    def test_loader_rejects_wrong_grid_and_source(self):
        write_proposal(self.proposals, self.scan, np.zeros((48, 32), bool))
        with self.assertRaises(ValueError):
            load_proposal(self.proposals, self.scan)
        write_proposal(self.proposals, self.scan, self.mask)
        self.scan.source_volume = Path("wrong_processedVolumes.mat")
        with self.assertRaises(ValueError):
            load_proposal(self.proposals, self.scan)

    def test_version_three_human_mask_still_loads(self):
        path = self.existing_label(self.mask, True)
        with np.load(path, allow_pickle=False) as data:
            payload = {k: data[k] for k in data.files if not k.startswith("vasculature_") or k == "vasculature_mask"}
        payload["label_format_version"] = np.array([CL.V3_CNV_LABEL_FORMAT_VERSION])
        np.savez_compressed(path, **payload)
        window = self.open()
        np.testing.assert_array_equal(window.vasculature_mask, self.mask)
        self.assertFalse(window.vasculature_proposal_path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
