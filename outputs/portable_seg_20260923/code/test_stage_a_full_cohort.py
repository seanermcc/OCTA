"""Manual provenance and independent reduced-precision training checks."""
import unittest
import numpy as np
import torch
from eight_surface.config import CASCADE_VERSION
from eight_surface import provenance as P
from stage_a_full_cohort import target_mask
from stage_a_inner_train import InnerUNet
from stage_a_inner_cv import make_ensemble, independent_losses, clip_independently


class FullCohortTests(unittest.TestCase):
    def test_exact_strokes_do_not_expand_to_untouched_or_displaced_columns(self):
        width = 10
        label = dict(surfaces=np.full((8, width), 20.), verdict="corrected", cascade_version=CASCADE_VERSION,
            surface_edited=np.ones(8, bool), surface_displaced=np.zeros(8, bool),
            surface_visible=np.ones(8, bool), surface_reliable=np.ones(8, bool),
            region_excluded=np.zeros(width, bool), local_provenance_available=True,
            provenance_code=np.full((8, width), P.PROV_AUTO, np.uint8))
        label["provenance_code"][:, 2:7] = P.PROV_DRAWN
        label["provenance_code"][:, 4] = P.PROV_DRAWN_DISPLACED
        shadow = np.zeros(width, bool); shadow[5] = True
        expected = np.zeros((8, width), bool); expected[:, [2, 3, 6]] = True
        np.testing.assert_array_equal(target_mask(label, shadow, 60), expected)
        label["verdict"] = "rejected"
        self.assertFalse(target_mask(label, shadow, 60).any())

    @unittest.skipUnless(torch.cuda.is_available() and torch.cuda.is_bf16_supported(), "CUDA BF16 unavailable")
    def test_bf16_batched_folds_match_independent_models(self):
        torch.manual_seed(41)
        x = torch.randn(2, 1, 1, 64, 32, device="cuda")
        rows = torch.arange(1, 9, device="cuda")[None, :, None].expand(2, 8, 32).float()*6
        valid = torch.ones_like(rows, dtype=torch.bool)
        valid[0, 2, :10] = False
        region = torch.full((2, 64, 32), -100, dtype=torch.long, device="cuda"); region[:, 16:19] = 1
        params, buffers, forward = make_ensemble(2, 8, 8, 17, "cuda")
        with torch.autocast("cuda", dtype=torch.bfloat16):
            a, b = forward(params, buffers, x)
        joint = independent_losses(a[:, 0].float(), b[:, 0].float(), rows, valid, region)
        joint.sum().backward(); clip_independently(params)
        for i in range(2):
            torch.manual_seed(17)
            single = InnerUNet(8, 8).cuda()
            with torch.autocast("cuda", dtype=torch.bfloat16):
                a, b = single(x[i])
            loss = independent_losses(a.float(), b.float(), rows[i:i+1], valid[i:i+1], region[i:i+1])
            torch.testing.assert_close(joint[i], loss[0], rtol=.002, atol=.002)
            loss.sum().backward(); torch.nn.utils.clip_grad_norm_(single.parameters(), 5.)
            batched, separate = [], []
            for name, p in single.named_parameters():
                batched.append(params[name].grad[i].flatten()); separate.append(p.grad.flatten())
            batched, separate = torch.cat(batched), torch.cat(separate)
            # BF16 batched and individual convolutions can select different
            # reduction kernels. Compare the full gradient direction/magnitude,
            # rather than relative errors of individual near-zero entries.
            relative = float((batched-separate).norm()/separate.norm())
            cosine = float(torch.nn.functional.cosine_similarity(batched, separate, dim=0))
            print(f"BF16 independent fold {i}: relative gradient L2={relative:.6f}, cosine={cosine:.6f}", flush=True)
            self.assertLess(relative, .03)
            self.assertGreater(cosine, .999)
        changed = x.clone(); changed[1] += 10
        with torch.autocast("cuda", dtype=torch.bfloat16):
            initial, _ = forward(params, buffers, x)
            perturbed, _ = forward(params, buffers, changed)
        torch.testing.assert_close(initial[0], perturbed[0], rtol=0, atol=0)


if __name__ == "__main__":
    torch.set_num_threads(2)
    unittest.main(verbosity=2)
