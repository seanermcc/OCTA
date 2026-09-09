import unittest
import numpy as np
from stage_a_inner_calibrate import apply_threshold
from auto_seg_8layer_v2.inner_learned_anchors import solve_with_missing_endpoints


class CalibrationTests(unittest.TestCase):
    def test_threshold_keeps_existing_abstentions_and_does_not_mutate_predictions(self):
        entropy = np.array([[.1, .2, .8, np.nan]] * 4)
        reasons = np.zeros((4, 4), np.uint8); reasons[:, 1] = 2
        original = dict(rows=np.ones((4, 4)), entropy=entropy, retained=reasons == 0, reason_bits=reasons)
        result = apply_threshold({"example": original}, .5)["example"]
        np.testing.assert_array_equal(result["retained"][0], [True, False, False, False])
        np.testing.assert_array_equal(result["reason_bits"][0], [0, 2, 16, 16])
        np.testing.assert_array_equal(original["reason_bits"][0], [0, 2, 0, 0])

    def test_missing_endpoint_columns_do_not_poison_other_columns(self):
        depth, width = 160, 40
        image = np.broadcast_to(np.sin(np.arange(depth)[:, None] / 6), (depth, width)).copy()
        images = np.stack([image] * 3)
        anchors = np.empty((3, 2, width)); anchors[:, 0] = 20; anchors[:, 1] = 130
        anchors[1, 1, 10] = 19
        anchors[1, 0, 14] = np.nan
        anchors[1, 0, 16] = -1
        anchors[1, 1, 18] = depth
        result = solve_with_missing_endpoints(images, anchors, [.5, .65], np.zeros((3, width), bool))
        np.testing.assert_array_equal(result[:, [0, 3]], anchors)
        self.assertTrue(np.isnan(result[1, 1:3, [10, 14, 16, 18]]).all())
        valid = np.ones(width, bool); valid[[10, 14, 16, 18]] = False
        self.assertTrue(np.isfinite(result[1, 1:3][:, valid]).all())


if __name__ == "__main__":
    unittest.main(verbosity=2)
