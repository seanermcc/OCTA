"""Exact optimality and geometry tests for the independent decoder experiment."""
import itertools
import unittest
import numpy as np

from stage_a_decoder import graph_cut, dp_project, pava


def brute_force(cost, minimum, maximum, step):
    n, depth, width = cost.shape
    columns = [np.array(c) for c in itertools.combinations(range(depth), n)
               if np.all(np.diff(c) >= minimum) and np.all(np.diff(c) <= maximum)]
    best = float("inf")
    for candidate in itertools.product(columns, repeat=width):
        rows = np.stack(candidate, axis=1)
        if np.any(np.abs(np.diff(rows, axis=1)) > step):
            continue
        value = float(cost[np.arange(n)[:, None], rows, np.arange(width)[None]].sum())
        best = min(best, value)
    return best


class DecoderTests(unittest.TestCase):
    def test_cut_matches_exhaustive_joint_optimum(self):
        for seed in range(5):
            rng = np.random.default_rng(seed)
            cost = rng.normal(size=(4, 7, 2))
            minimum, maximum = np.array([1, 1, 1]), np.array([2, 3, 2])
            rows = graph_cut(cost, minimum, maximum, 1).astype(int)
            energy = cost[np.arange(4)[:, None], rows, np.arange(2)[None]].sum()
            self.assertAlmostEqual(energy, brute_force(cost, minimum, maximum, 1), places=9)

    def test_cut_minimum_and_maximum_separations(self):
        cost = np.full((4, 15, 3), 10.)
        for k, z in enumerate([13, 2, 12, 3]):
            cost[k, z] = 0
        rows = graph_cut(cost, [2, 2, 2], [3, 3, 3], 2)
        self.assertTrue((np.diff(rows, axis=0) >= 2).all())
        self.assertTrue((np.diff(rows, axis=0) <= 3).all())
        self.assertTrue((np.abs(np.diff(rows, axis=1)) <= 2).all())

    def test_cut_zero_step_and_depth_edge_feasibility(self):
        cost = np.random.default_rng(19).normal(size=(4, 7, 2))
        rows = graph_cut(cost, [2, 2, 2], [3, 3, 3], 0)
        self.assertTrue(np.array_equal(rows[:, 0], [0, 2, 4, 6]))
        self.assertTrue(np.array_equal(rows[:, 0], rows[:, 1]))

    def test_pava_known_projection(self):
        np.testing.assert_allclose(pava([1, 0, 3, 2]), [.5, .5, 2.5, 2.5])

    def test_dp_control_order_bounds_and_step(self):
        cost = np.random.default_rng(12).normal(size=(4, 32, 24))
        rows = dp_project(cost, [2, 3, 2], [20, 20, 20], 2)
        self.assertTrue((np.diff(rows, axis=0) >= np.array([2, 3, 2])[:, None] - 1e-8).all())
        self.assertTrue((np.abs(np.diff(rows, axis=1)) <= 2 + 1e-8).all())
        self.assertGreaterEqual(rows.min(), 0)
        self.assertLess(rows.max(), 32)

    def test_reject_infeasible_or_nonfinite_input(self):
        for func in (graph_cut, dp_project):
            with self.assertRaises(ValueError):
                func(np.zeros((4, 5, 2)), [2, 2, 2], [3, 3, 3])
            with self.assertRaises(ValueError):
                func(np.full((4, 10, 2), np.nan), [1, 1, 1], [3, 3, 3])


if __name__ == "__main__":
    unittest.main(verbosity=2)
