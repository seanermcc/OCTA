"""Check that batching independent CV models preserves the original objective."""
import unittest
import json
from pathlib import Path
import tempfile
import numpy as np
import torch
from stage_a.model import losses
from stage_a_inner_train import InnerUNet
from stage_a.common import digest
from stage_a_inner_cv import (independent_losses, make_ensemble, clip_independently,
                              verify_completed, validate_resume_state)


class IndependentTrainingTests(unittest.TestCase):
    def test_resume_rejects_silent_broadcast_and_swapped_folds(self):
        group = [{"held_animal": "A"}, {"held_animal": "B"}]
        protocol = {"batch_folds": 2}
        params = {"weight": torch.zeros(2, 3, 4)}
        ck = dict(protocol_digest=digest(protocol), group_folds=group,
                  rngs=[None, None], params={"weight": torch.zeros(1, 3, 4)}, buffers={})
        with self.assertRaisesRegex(ValueError, "broadcasting"):
            validate_resume_state(ck, group, params, {}, protocol)
        ck["params"]["weight"] = torch.zeros(2, 3, 4)
        validate_resume_state(ck, group, params, {}, protocol)
        with self.assertRaisesRegex(ValueError, "grouping"):
            validate_resume_state(ck, list(reversed(group)), params, {}, protocol)

    def test_completed_run_is_read_only_and_checks_legacy_batching(self):
        folds = [dict(held_animal=a, calibration_animal="C", training_animals=["D"])
                 for a in ("A", "B")]
        old = dict(folds=folds, base=8, heads=8, epochs=2, steps_per_epoch=3,
                   dataset_identity={"id": "frozen"}, code_identity="old-source")
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            (out / "protocol.json").write_text(json.dumps(old))
            (out / "training_complete.json").write_text(json.dumps({"protocol_digest": digest(old)}))
            for fold in folds:
                folder = out / fold["held_animal"]
                folder.mkdir()
                torch.save(dict(protocol_digest=digest(old), config=dict(base=8, heads=8, **fold),
                    identity=old["dataset_identity"], epoch=2, step=6,
                    training_resume="ensemble_00.pt", model={"x": torch.ones(1)}), folder / "last.pt")
            before = {p: (p.stat().st_mtime_ns, p.read_bytes()) for p in out.rglob("*") if p.is_file()}
            current = {**old, "code_identity": "new-source", "batch_folds": 2}
            self.assertTrue(verify_completed(out, current, 2))
            self.assertEqual(before, {p: (p.stat().st_mtime_ns, p.read_bytes()) for p in before})
            with self.assertRaisesRegex(ValueError, "batching"):
                verify_completed(out, {**current, "batch_folds": 1}, 1)
            with self.assertRaisesRegex(ValueError, "steps_per_epoch"):
                verify_completed(out, {**current, "steps_per_epoch": 4}, 2)

    def test_four_boundary_three_band_shapes(self):
        model = InnerUNet(8, 4)
        a, b = model(torch.zeros(1, 1, 65, 33))
        self.assertEqual(tuple(a.shape), (1, 4, 65, 33))
        self.assertEqual(tuple(b.shape), (1, 3, 65, 33))

    def test_vectorised_networks_match_individual_losses_and_gradients(self):
        torch.manual_seed(11)
        x = torch.randn(2, 1, 1, 64, 32)
        rows = torch.ones(2, 4, 32) * torch.arange(1, 5)[None, :, None] * 10
        valid = torch.ones_like(rows, dtype=torch.bool)
        valid[0, 2, :12] = False
        valid[1, 0, :] = False
        region = torch.full((2, 64, 32), -100, dtype=torch.long)
        region[:, 12:18] = 0
        params, buffers, forward = make_ensemble(2, 8, 4, 17, "cpu")
        a, b = forward(params, buffers, x)
        joint = independent_losses(a[:, 0], b[:, 0], rows, valid, region)
        joint.sum().backward()
        clip_independently(params)
        for i in range(2):
            torch.manual_seed(17)
            single = InnerUNet(8, 4)
            a, b = single(x[i])
            value, _ = losses(a, b, rows[i:i+1], valid[i:i+1], region[i:i+1])
            np.testing.assert_allclose(float(joint[i].detach()), float(value.detach()), rtol=1e-6)
            value.backward()
            torch.nn.utils.clip_grad_norm_(single.parameters(), 5.)
            for name, p in single.named_parameters():
                torch.testing.assert_close(params[name].grad[i], p.grad, rtol=3e-4, atol=2e-6)


if __name__ == "__main__":
    torch.set_num_threads(2)
    unittest.main(verbosity=2)
