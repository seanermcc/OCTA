"""Behavioral checks for the experimental contrast baseline, not validation on animals."""
import unittest

import numpy as np

from vasculature_baseline import make_mask, vessel_evidence


class VesselBaselineChecks(unittest.TestCase):
    def test_uniform_field_is_empty(self):
        score, _, _ = vessel_evidence(np.full((256, 256), 60.))
        self.assertFalse(make_mask(score, .18).any())

    def test_persistent_intensity_step_is_not_a_vessel(self):
        image = np.full((256, 256), 60.)
        image[:, 128:] += 4
        score, _, _ = vessel_evidence(image)
        self.assertFalse(make_mask(score, .18).any())

    def test_field_spanning_vessels_survive_step_correction(self):
        y, x = np.indices((256, 256))
        for name, distance in (("vertical", x-128), ("horizontal", y-128),
                               ("diagonal", (x-y)/np.sqrt(2))):
            with self.subTest(direction=name):
                image = 60-4*np.exp(-distance**2/(2*5**2))
                score, _, _ = vessel_evidence(image)
                mask = make_mask(score, .18)
                center = ((abs(distance) < 3) & (x > 20) & (x < 236)
                          & (y > 20) & (y < 236))
                self.assertGreater(float(mask[center].mean()), .95)

    def test_nonfinite_data_rejected(self):
        with self.assertRaises(ValueError):
            vessel_evidence(np.full((64, 64), np.nan))


if __name__ == "__main__":
    unittest.main()
