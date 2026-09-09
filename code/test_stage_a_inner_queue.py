import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

from stage_a_inner_queue import longest_run, triage
from eight_surface.review import write_review_pack, _spread_pick


class QueueTests(unittest.TestCase):
    def test_flagged_runs_respect_scope_and_shadow(self):
        rows = np.broadcast_to(np.arange(4)[None, :, None] * 10., (2, 4, 8)).copy()
        entropy = np.zeros_like(rows)
        entropy[0, :, 1:6] = 1
        scope = np.ones((2, 8), bool)
        shadow = np.zeros_like(scope); shadow[0, 3] = True
        reasons = np.zeros(rows.shape, np.uint8); reasons[0, :, 3] |= 2
        keep, bits, cutoff, ranked = triage(rows, entropy, reasons, scope, shadow, .5)
        self.assertEqual(cutoff, 0)
        self.assertEqual(ranked[0]["longest_flagged_run_alines"], 2)
        self.assertFalse(keep[0, :, 3].any())
        self.assertGreater(ranked[0]["priority_heuristic"], ranked[1]["priority_heuristic"])
        self.assertEqual(longest_run(np.ones(8)), 8)
        self.assertEqual(longest_run(np.zeros(8)), 0)

    def test_pick_never_reintroduces_reviewed_indices_in_fallback(self):
        excluded = {0, 2, 3, 4, 6}
        picked = _spread_pick(np.arange(8), 3, 16, exclude=excluded)
        self.assertEqual(set(picked), {1, 5, 7})

    def test_pack_loads_in_actual_gui_without_creating_labels(self):
        from eight_surface.label_gui import Pack
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            images = np.ones((3, 64, 8), np.float32)
            surfaces = np.broadcast_to(np.arange(8)[None, :, None] * 5., (3, 8, 8)).copy()
            confidence = np.full_like(surfaces, np.nan)
            shadow = np.zeros((3, 8), bool)
            with patch("eight_surface.labels.save_label", side_effect=AssertionError("Label write forbidden")):
                path = write_review_pack(root / "TS165_example_pack.npz", "TS165_example", images,
                    surfaces, confidence, shadow, [0, 2], [2], np.arange(3))
                pack = Pack(path, root / "labels")
                self.assertEqual(pack.n, 2)
                self.assertEqual(pack.n_preloaded, 0)
                self.assertTrue(all(s.verdict is None for s in pack.states))
                self.assertTrue(all(not s.edited.any() for s in pack.states))
                self.assertEqual(list(pack.bscan_index), [0, 2])
                self.assertFalse((root / "labels").exists())
            with self.assertRaises(ValueError):
                write_review_pack(root / "TS165_example_b0000.npz", "TS165_example", images,
                    surfaces, confidence, shadow, [0], [], np.arange(3))


if __name__ == "__main__":
    unittest.main(verbosity=2)
