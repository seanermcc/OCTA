import itertools
import unittest
import numpy as np
from stage_a_decoder import graph_cut_full as graph_cut
from stage_a_decoder_sparse import exact_graph_cut, conditional_bounds


class SparseGraphTests(unittest.TestCase):
    def test_same_global_optimum_as_full_graph(self):
        for seed in range(20):
            rng = np.random.default_rng(seed)
            cost = rng.uniform(0, 10, (4, 10, 5))
            minimum, maximum = [1, 2, 1], [3, 4, 3]
            full = graph_cut(cost, minimum, maximum, max_step=seed % 3).astype(int)
            sparse = exact_graph_cut(cost, minimum, maximum, max_step=seed % 3).astype(int)
            def energy(rows):
                return cost[np.arange(4)[:, None], rows, np.arange(5)].sum()
            self.assertAlmostEqual(energy(full), energy(sparse), places=7)

    def test_pruning_removes_expensive_states_and_preserves_optimum(self):
        cost = np.full((4, 80, 20), 100.)
        for k, row in enumerate([20, 25, 29, 40]):
            cost[k, row] = 0
        rows, info = exact_graph_cut(cost, [2, 2, 2], [20, 20, 20], return_diagnostics=True)
        self.assertEqual(info["optimum_energy"], 0)
        self.assertLess(info["retained_states"], 100)
        np.testing.assert_array_equal(rows[:, 0], [20, 25, 29, 40])

    def test_uniform_ties_remain_feasible(self):
        rows = exact_graph_cut(np.zeros((4, 8, 3)), [1, 1, 1], [3, 3, 3], 0)
        self.assertTrue(np.all(np.diff(rows, axis=0) >= 1))
        self.assertTrue(np.all(np.diff(rows, axis=1) == 0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
