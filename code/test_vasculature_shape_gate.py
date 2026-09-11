"""Geometry checks for major-vessel cleanup; these do not validate real scans."""
import unittest

import numpy as np
from scipy import ndimage as ndi
from skimage.draw import line

from vasculature_shape_gate import shape_gate


class ShapeGateChecks(unittest.TestCase):
    def test_rejects_empty_round_short_and_thin(self):
        y, x = np.indices((256, 256))
        cases = {
            "empty": np.zeros((256, 256), bool),
            "round": (x-128)**2+(y-128)**2 <= 25**2,
            "short": (abs(x-128) <= 7) & (abs(y-128) <= 15),
            "thin": (abs(x-128) <= 1) & (abs(y-128) <= 100),
        }
        for name, mask in cases.items():
            with self.subTest(case=name):
                kept, _ = shape_gate(mask)
                self.assertFalse(kept.any())

    def test_keeps_long_straight_and_curved_bands(self):
        y, x = np.indices((256, 256))
        r = np.hypot(x-128, y-128)
        theta = np.arctan2(y-128, x-128)
        cases = {
            "vertical": (abs(x-128) <= 7) & (abs(y-128) <= 100),
            "horizontal": (abs(y-128) <= 7) & (abs(x-128) <= 100),
            "curved": (abs(r-75) <= 7) & (theta > -.6) & (theta < 2.8),
        }
        for name, mask in cases.items():
            with self.subTest(case=name):
                kept, _ = shape_gate(mask)
                self.assertGreater(kept.sum()/mask.sum(), .95)

    def test_branching_tree_is_not_rejected_as_round(self):
        seed = np.zeros((256, 256), bool)
        for y, x in ((30, 128), (220, 128), (128, 30), (128, 220)):
            yy, xx = line(128, 128, y, x)
            seed[yy, xx] = True
        mask = ndi.distance_transform_edt(~seed) <= 7
        kept, _ = shape_gate(mask)
        self.assertGreater(kept.sum()/mask.sum(), .95)

    def test_round_blob_removed_without_changing_separate_vessel(self):
        y, x = np.indices((256, 256))
        vessel = (abs(x-70) <= 7) & (abs(y-128) <= 100)
        blob = (x-180)**2+(y-128)**2 <= 25**2
        kept, _ = shape_gate(vessel | blob)
        np.testing.assert_array_equal(kept, vessel)

    def test_short_spur_removed_without_severing_main_band(self):
        mask = np.zeros((256, 256), bool)
        mask[20:236, 120:136] = True
        mask[120:134, 136:155] = True
        kept, _ = shape_gate(mask)
        self.assertTrue(kept[25:230, 128].all())
        self.assertFalse(kept[120:134, 146:155].any())
        self.assertFalse(np.any(kept & ~mask))

    def test_never_joins_a_gap(self):
        mask = np.zeros((256, 256), bool)
        mask[15:115, 120:136] = True
        mask[130:240, 120:136] = True
        kept, _ = shape_gate(mask)
        self.assertFalse(kept[115:130].any())
        self.assertTrue(kept[40:80, 128].all())
        self.assertTrue(kept[160:200, 128].all())


if __name__ == "__main__":
    unittest.main()
