"""Exercise full-volume navigation through real Qt widgets without label writes."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from eight_surface.review import write_review_pack
from eight_surface.label_gui import QtWidgets
from stage_a_full_volume_gui import FullVolumeWindow


class FullVolumeNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_all_images_and_pack_switch_from_last_index(self):
        with tempfile.TemporaryDirectory() as temp, patch("eight_surface.label_gui.Pack.save", return_value=None), patch("eight_surface.labels.save_label", side_effect=AssertionError("No label writes")):
            directory = Path(temp)
            paths = []
            for sid, count in (("TEST_A", 3), ("TEST_B", 2)):
                rows = np.broadcast_to(np.arange(8)[None, :, None] * 3. + 1, (count, 8, 16)).copy()
                path = directory / f"{sid}_pack.npz"
                write_review_pack(path, sid, np.zeros((count, 32, 16)), rows, np.zeros_like(rows),
                                  np.zeros((count, 16), bool), np.arange(count), [], np.zeros(count))
                paths.append(path)
            window = FullVolumeWindow(paths, directory / "labels")
            with patch.object(window.pack, "save") as save:
                window.commit_current()
                save.assert_not_called()
                window.pack.states[0].current[0, 0] += 1
                window.commit_current()
                save.assert_called_once_with(0)
            window.pack.states[1].verdict = "rejected"
            window.next_bscan(1)
            self.assertEqual(window.i, 1, "Full-volume browsing must include rejected images")
            window.bscan_choice.setValue(2)
            self.assertEqual(window.i, 2)
            self.assertEqual(window.bscan_slider.value(), 2)
            window.volume_choice.activated.emit(1)
            self.assertEqual((window.pi, window.i, window.pack.n), (1, 0, 2))
            self.assertEqual(window.bscan_choice.maximum(), 1)
            window.next_bscan(-1)
            self.assertEqual((window.pi, window.i), (0, 2))
            window.close()
            self.assertEqual(list((directory / "labels").glob("*.npz")), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
