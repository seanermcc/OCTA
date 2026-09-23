"""No-data checks for integrated en-face and one-line surface review."""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from eight_surface import cnv_labels
from eight_surface.cnv_data import CnvScan
from eight_surface.cnv_gui import MainWindow, QtWidgets
from eight_surface.config import SURFACE_NAMES
from eight_surface.label_gui import Pack


class EnfaceSegmentationGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_overlay_brush_save_and_single_line_pack(self):
        n_bscan, n_aline, n_depth = 4, 16, 32
        surfaces = np.broadcast_to(
            np.linspace(3, 27, len(SURFACE_NAMES), dtype=np.float32)[None, :, None],
            (n_bscan, len(SURFACE_NAMES), n_aline)).copy()
        scan = CnvScan(
            scan_id="TS999_TEST", segmentation_path=Path("segmented.npz"),
            source_volume=Path("source_processedVolumes.mat"),
            structural_band=np.full((n_bscan, n_aline, n_depth), 10, np.float32),
            structural_enface=np.arange(n_bscan * n_aline, dtype=np.float32).reshape(n_bscan, n_aline),
            octa_enface=np.ones((n_bscan, n_aline), np.float32),
            surfaces=surfaces, confidence=np.ones_like(surfaces),
            shadow=np.zeros((n_bscan, n_aline), bool),
            surface_names=tuple(SURFACE_NAMES), px_um=1.12,
            retina_band=(100, 132), vitreous_at_high_index=False,
            animal="TS999", eye="OD", day_label="D7")

        with tempfile.TemporaryDirectory() as temp, patch(
                "eight_surface.cnv_gui.read_scan", return_value=scan):
            root = Path(temp)
            window = MainWindow(
                [root / "segmented.npz"], root / "enface_labels",
                root / "surface_labels", root / "line_review")
            window.navigate(2, 7)
            self.assertEqual(len(window.bscan._auto_items), len(SURFACE_NAMES))
            self.assertTrue(all(item.isVisible() for item in window.bscan._auto_items))

            window.apply_stroke(
                [(2, 2), (12, 2)], "vasculature_brush_add")
            self.assertTrue(window.vasculature_mask.any())
            self.assertTrue(window.reviewed_targets[1])
            saved = window.save()
            record = cnv_labels.load_label(saved)
            self.assertTrue(np.array_equal(
                record["vasculature_mask"], window.vasculature_mask))
            self.assertTrue(record["reviewed_targets"][1])
            self.assertFalse(record["reviewed_targets"][0])

            pack_path = window._write_line_review_pack(2)
            pack = Pack(pack_path, root / "surface_labels")
            self.assertEqual(pack.bscan_index.tolist(), [2])
            self.assertEqual(pack.images.shape, (1, n_depth, n_aline))
            self.assertTrue(np.array_equal(pack.surfaces[0], surfaces[2]))

            window.open_surface_editor()
            key = (scan.scan_id, 2)
            self.assertIn(key, window.surface_windows)
            editor = window.surface_windows[key]
            self.assertEqual(editor.pack.bscan_index.tolist(), [2])
            editor.close()
            QtWidgets.QApplication.processEvents()
            window.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
