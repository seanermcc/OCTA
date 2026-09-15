"""No-data tests for the en-face CNV annotation and pack-selection workflow."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import h5py
import numpy as np
from skimage.draw import polygon

from eight_surface import cnv_labels
from eight_surface.cnv_gui import _rasterize_edge, _smooth_stroke
from eight_surface.cnv_review import (
    ZONE_CORE,
    ZONE_NEARBY,
    ZONE_REMOTE,
    ZONE_RIM,
    lesion_zones,
    select_bscans,
    write_pack,
)
from eight_surface.config import CASCADE_VERSION, SURFACE_NAMES
from eight_surface.label_gui import Pack


class CnvWorkflowTests(unittest.TestCase):
    def test_cnv_label_round_trip_is_versioned_and_surface_free(self):
        mask = np.zeros((32, 48), dtype=bool)
        mask[8:20, 12:35] = True
        onh = np.zeros_like(mask)
        onh[2:24, 3] = True
        with tempfile.TemporaryDirectory() as temp:
            path = cnv_labels.save_label(
                temp, scan_id="TS999_OD_D7_s01", cnv_mask=mask,
                onh_edge_mask=onh, source_volume="source_processedVolumes.mat",
                source_segmentation="segmented.npz", retina_band=(10, 210),
                vitreous_at_high_index=True, animal="TS999", eye="OD")
            first = cnv_labels.load_label(path)
            cnv_labels.save_label(
                temp, scan_id="TS999_OD_D7_s01", cnv_mask=mask,
                source_volume="source_processedVolumes.mat",
                source_segmentation="segmented.npz", retina_band=(10, 210),
                vitreous_at_high_index=True, animal="TS999", eye="OD")
            second = cnv_labels.load_label(path)
            with np.load(path, allow_pickle=False) as raw:
                keys = set(raw.files)
        self.assertTrue(np.array_equal(first["cnv_mask"], mask))
        self.assertTrue(first["reviewed"])
        self.assertTrue(first["lesion_present"])
        self.assertTrue(np.array_equal(first["onh_edge_mask"], onh))
        self.assertTrue(first["onh_edge_present"])
        self.assertEqual(first["label_format_version"],
                         cnv_labels.CNV_LABEL_FORMAT_VERSION)
        self.assertEqual(first["revision"], 1)
        self.assertEqual(second["revision"], 2)
        self.assertNotIn("surfaces", keys)
        self.assertNotIn("thickness", keys)

    def test_freehand_cnvs_close_smoothly_and_onh_stays_an_open_edge(self):
        # A slightly wobbly, incomplete circle closes on release and creates a
        # filled footprint; an ONH trace remains a line for later distances.
        contour = [(8, 18), (12, 10), (21, 8), (29, 13), (31, 22), (25, 30),
                   (15, 31), (8, 25)]
        smooth = _smooth_stroke(contour, closed=True)
        self.assertGreaterEqual(len(smooth), 12)
        rr, cc = polygon(smooth[:, 1], smooth[:, 0], shape=(40, 40))
        filled = np.zeros((40, 40), bool)
        filled[rr, cc] = True
        self.assertTrue(filled[20, 20])
        edge = _rasterize_edge([(0, 5), (7, 8), (15, 13), (20, 20)], (32, 32))
        self.assertTrue(edge.any())
        self.assertFalse(edge[0, 20])  # no artificial closing segment

    def test_empty_reviewed_mask_is_valid_no_cnv_decision(self):
        with tempfile.TemporaryDirectory() as temp:
            path = cnv_labels.save_label(
                temp, scan_id="TS999_WT", cnv_mask=np.zeros((8, 10), bool),
                source_volume="source.mat", source_segmentation="seg.npz",
                retina_band=(0, 100), vitreous_at_high_index=False)
            record = cnv_labels.load_label(path)
        self.assertTrue(record["reviewed"])
        self.assertFalse(record["lesion_present"])
        self.assertEqual(record["lesion_pixel_count"], 0)

    def test_zone_map_partitions_native_grid(self):
        mask = np.zeros((180, 220), dtype=bool)
        mask[60:120, 75:155] = True
        zones, info = lesion_zones(
            mask, bscan_um=2.85, aline_um=2.85,
            rim_um=30.0, nearby_um=90.0)
        self.assertEqual(zones.shape, mask.shape)
        self.assertEqual(set(np.unique(zones)),
                         {ZONE_REMOTE, ZONE_NEARBY, ZONE_RIM, ZONE_CORE})
        self.assertEqual(zones[90, 110], ZONE_CORE)
        self.assertEqual(zones[60, 75], ZONE_RIM)
        self.assertEqual(zones[45, 110], ZONE_NEARBY)
        self.assertEqual(zones[0, 0], ZONE_REMOTE)
        self.assertGreater(info["inner_rim_um"], 0)

    def test_selection_includes_all_requested_spatial_roles(self):
        mask = np.zeros((240, 256), dtype=bool)
        mask[80:160, 70:190] = True
        zones, _ = lesion_zones(
            mask, bscan_um=2.85, aline_um=2.85,
            rim_um=30.0, nearby_um=100.0)
        selected = select_bscans(
            mask, zones, bscan_um=2.85, aline_um=2.85,
            n_core=3, n_rim=2, n_nearby=2, n_remote=2, min_sep=8)
        roles = [role for _row, role in selected]
        rows = [row for row, _role in selected]
        self.assertEqual(len(rows), len(set(rows)))
        self.assertEqual(roles.count("core"), 3)
        self.assertEqual(roles.count("rim"), 2)
        self.assertEqual(roles.count("nearby"), 2)
        self.assertEqual(roles.count("remote"), 2)

    def test_no_lesion_creates_no_lesion_pack_selection(self):
        mask = np.zeros((40, 50), dtype=bool)
        zones, _ = lesion_zones(mask, 2.85, 2.85)
        self.assertTrue(np.all(zones == ZONE_REMOTE))
        self.assertEqual(select_bscans(
            mask, zones, bscan_um=2.85, aline_um=2.85), [])

    def test_written_cnv_pack_opens_in_eight_surface_gui(self):
        n_bscan, n_aline, n_depth = 48, 64, 120
        mask = np.zeros((n_bscan, n_aline), dtype=bool)
        mask[14:34, 18:48] = True
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source_processedVolumes.mat"
            with h5py.File(source, "w") as handle:
                # Positive amplitude is enough for the pack's structural read.
                handle.create_dataset(
                    "frame_3DAvg",
                    data=np.full((n_bscan, n_aline, n_depth), 10.0, np.float32))
            seg_path = root / "TS999_CNV.npz"
            surfaces = np.broadcast_to(
                np.linspace(10, 85, len(SURFACE_NAMES), dtype=np.float32)[None, :, None],
                (n_bscan, len(SURFACE_NAMES), n_aline)).copy()
            np.savez_compressed(
                seg_path, surfaces=surfaces,
                confidence=np.ones_like(surfaces, dtype=np.float16),
                shadow=np.zeros((n_bscan, n_aline), dtype=bool),
                surface_names=np.array(SURFACE_NAMES),
                cascade_version=np.array([CASCADE_VERSION]),
                scan_id=np.array(["TS999_CNV"]), source=np.array([str(source)]),
                retina_band=np.array([10, 110], dtype=np.int32),
                px_um=np.array([1.12], dtype=np.float32))
            cnv_path = cnv_labels.save_label(
                root / "cnv", scan_id="TS999_CNV", cnv_mask=mask,
                source_volume=source, source_segmentation=seg_path,
                retina_band=(10, 110), vitreous_at_high_index=True,
                field_um=48.0)
            cnv = cnv_labels.load_label(cnv_path)
            args = SimpleNamespace(
                rim_um=3.0, nearby_um=8.0, n_core=2, n_rim=2,
                n_nearby=2, n_remote=2, min_sep=3, overwrite=False)
            pack_path, manifest = write_pack(
                cnv, seg_path, root / "packs", args)
            pack = Pack(pack_path, root / "surface_labels")
        self.assertEqual(pack.scan_id, "TS999_CNV")
        self.assertEqual(pack.images.shape[0], len(manifest))
        self.assertEqual(pack.images.shape[1:], (100, n_aline))
        self.assertEqual(pack.surfaces.shape[1], len(SURFACE_NAMES))
        self.assertEqual(pack.selection_role.shape, (len(manifest),))
        self.assertEqual(pack.lesion_zone.shape, (len(manifest), n_aline))
        self.assertEqual(sum(row["selection_role"] == "core" for row in manifest), 2)


if __name__ == "__main__":
    unittest.main()
