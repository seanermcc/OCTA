"""Focused no-data tests for the isolated eight-boundary workflow."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from eight_surface import labels
from eight_surface.config import LAYER_NAMES, SURFACE_NAMES, layer_reliability
from eight_surface.segment import segment_bscan
from eight_surface.volume import thickness_maps


class EightSurfaceTests(unittest.TestCase):
    def test_boundary_deselection_excludes_only_adjacent_bands(self):
        surfaces = np.broadcast_to(
            np.arange(len(SURFACE_NAMES), dtype=float)[None, :, None] * 10,
            (1, len(SURFACE_NAMES), 12)).copy()
        shadow = np.zeros((1, 12), bool)
        reliable = np.ones(len(SURFACE_NAMES), bool)
        reliable[SURFACE_NAMES.index("GCL_IPL")] = False
        maps = thickness_maps(surfaces, shadow, surface_reliable=reliable)
        self.assertTrue(np.isnan(maps["GCL"]).all())
        self.assertTrue(np.isnan(maps["IPL"]).all())
        self.assertTrue(np.isfinite(maps["RNFL"]).all())
        self.assertTrue(np.isfinite(maps["INL"]).all())
        self.assertEqual(
            set(name for name, value in layer_reliability(reliable).items() if not value),
            {"GCL", "IPL"})

    def test_label_round_trip_preserves_reliability(self):
        n_surf, n_col = len(SURFACE_NAMES), 64
        auto = np.arange(n_surf, dtype=float)[:, None] * 10 + np.zeros((n_surf, n_col))
        current = auto.copy()
        current[2, 10:20] += 2
        reliable = np.ones(n_surf, bool)
        reliable[2] = False
        with tempfile.TemporaryDirectory() as temp:
            path = labels.save_label(
                temp, scan_id="test", bscan=7, verdict="corrected",
                surfaces=current, auto_surfaces=auto, surface_names=SURFACE_NAMES,
                surface_edited=np.array([False, False, True, False, False, False, False, False]),
                surface_displaced=np.zeros(n_surf, bool), surface_visible=np.ones(n_surf, bool),
                surface_reliable=reliable, region_excluded=np.zeros(n_col, bool), px_um=1.12)
            record = labels.load_label(path)
        self.assertFalse(record["surface_reliable"][2])
        self.assertEqual(record["layer_names"], LAYER_NAMES)
        self.assertFalse(record["layer_reliable"][LAYER_NAMES.index("GCL")])
        self.assertFalse(record["layer_reliable"][LAYER_NAMES.index("IPL")])

    def test_segmenter_returns_eight_ordered_lines(self):
        depth, width = 260, 96
        image = np.full((depth, width), -25.0, np.float32)
        image[30:78] = -8.0
        image[78:92] = -16.0
        image[92:126] = -9.0
        image[126:146] = -16.0
        image[146:160] = -8.0
        image[160:180] = -17.0
        image[180:194] = -6.0
        image[194:208] = -15.0
        result = segment_bscan(image)
        self.assertEqual(result.surfaces.shape, (8, width))
        self.assertEqual(result.confidence.shape, (8, width))
        self.assertTrue(np.all(np.diff(result.surfaces, axis=0) >= 1.0))


if __name__ == "__main__":
    unittest.main()

