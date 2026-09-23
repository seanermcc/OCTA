"""Small deterministic tests for acquisition-QC helpers."""

import unittest

import numpy as np

from scan_quality import (_adjacent_correlations, _block_mean,
                          _registered_corr, _stripe_fraction)


class ScanQualityTests(unittest.TestCase):
    def test_adjacent_identical_rows(self):
        row = np.linspace(-1, 1, 64)
        img = np.tile(row, (12, 1))
        self.assertTrue(np.allclose(_adjacent_correlations(img), 1.0))

    def test_registration_recovers_shifted_structure(self):
        y, x = np.mgrid[:128, :128]
        a = (np.exp(-((x - 45) ** 2 + (y - 70) ** 2) / 180.0) +
             0.7 * np.exp(-((x - 90) ** 2 + (y - 35) ** 2) / 90.0))
        b = np.roll(np.roll(a, 7, axis=0), -5, axis=1)
        corr, dy, dx = _registered_corr(a, b)
        self.assertGreater(corr, 0.99)
        self.assertEqual(abs(dy), 7)
        self.assertEqual(abs(dx), 5)

    def test_striping_increases_high_frequency_power(self):
        x = np.linspace(0, 2 * np.pi, 128)
        base = np.tile(np.sin(x), (128, 1))
        striped = base + ((np.arange(128) % 2) * 2 - 1)[:, None]
        self.assertGreater(_stripe_fraction(striped), _stripe_fraction(base))

    def test_block_mean_size(self):
        self.assertEqual(_block_mean(np.zeros((512, 512))).shape, (128, 128))


if __name__ == "__main__":
    unittest.main()
