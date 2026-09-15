"""Animal-disjoint cross-validation with vectorised independent model training.

For each of seven folds: five animals train, one calibrates the entropy cutoff,
and a different animal measures coverage/error. No held or calibration labels
select model weights. Independent networks are batched only for GPU efficiency.
"""
import argparse
from collections import defaultdict
import copy
import json
from pathlib import Path
import random
import time

import numpy as np
import torch
from torch.func import functional_call, stack_module_state, vmap
from torch.nn import functional as F

from stage_a.common import DEFAULT, digest, output_dir, write_json, write_csv
from stage_a.data import Dataset
from stage_a_inner_train import InnerUNet, View, implementation_identity


def independent_losses(logits, regions, rows, valid, region_target, region_weight=.1):
    """Original Stage A objective separately for each independent network."""
    good = valid.bool()
    if not good.flatten(1).any(1).all():
        raise ValueError("Each model needs manual supervision in its sampled image")
    clean = torch.where(good, rows, torch.zeros_like(rows))
    depth = torch.arange(logits.shape[2], device=logits.device)[None, None, :, None]
    target = torch.exp(-.5 * ((depth - clean[:, :, None]) / 2.) ** 2)
    target = target / target.sum(2, keepdim=True).clamp_min(1e-12)
    ce = -(target * logits.log_softmax(2)).sum(2)
    expected = (logits.softmax(2) * depth).sum(2)
    l1 = F.smooth_l1_loss(expected, clean, reduction="none")
    counts = good.sum(2)
    per_surface = ((ce + .05 * l1) * good).sum(2) / counts.clamp_min(1)
    supported = counts > 0
    boundary = (per_surface * supported).sum(1) / supported.sum(1).clamp_min(1)
    per_pixel = F.cross_entropy(regions, region_target, ignore_index=-100, reduction="none")
    region = per_pixel.flatten(1).sum(1) / region_target.ne(-100).flatten(1).sum(1).clamp_min(1)
    return boundary + region_weight * region


def make_ensemble(count, base, heads, seed, device):
    models = []
    for _ in range(count):
        torch.manual_seed(seed)
        models.append(InnerUNet(base, heads).to(device))
    params, buffers = stack_module_state(models)
    template = copy.deepcopy(models[0]).to("meta")
    del models

    def call(p, b, x):
        return functional_call(template, (p, b), (x,))

    return params, buffers, vmap(call, in_dims=(0, 0, 0), randomness="error")


def clip_independently(params, limit=5.):
    norms = None
    for param in params.values():
        if param.grad is None:
            continue
        term = param.grad.flatten(1).square().sum(1)
        norms = term if norms is None else norms + term
    norms = norms.sqrt()
    if not torch.isfinite(norms).all() or (norms <= 0).any():
        raise FloatingPointError("Non-finite or zero ensemble gradient")
    scale = (limit / (norms + 1e-6)).clamp(max=1)
    for param in params.values():
        if param.grad is not None:
            param.grad.mul_(scale.view(-1, *([1] * (param.ndim - 1))))
    return norms


def run(args):
    torch.set_num_threads(4)
    torch.backends.cudnn.benchmark = False
    torch.use_deterministic_algorithms(True, warn_only=True)
    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    datasets = [Dataset(args.data, s) for s in ("train", "validation")]
    animals = sorted(set(a for d in datasets for a in d.animals))
    if len(animals) < 4:
        raise ValueError("Too few animals for disjoint train/calibration/evaluation roles")
    folds = []
    for i, held in enumerate(animals):
        calibration = animals[(i + 1) % len(animals)]
        training = [a for a in animals if a not in (held, calibration)]
        folds.append(dict(held_animal=held, calibration_animal=calibration, training_animals=training))
    out = output_dir(args.out)
    protocol = dict(folds=folds, heads=args.heads, epochs=args.epochs, steps_per_epoch=args.steps_per_epoch,
        seed=args.seed, base=args.base, lr=3e-4, region_weight=.1,
        weight_selection="fixed budget, no calibration or held-animal loss used",
        final_test_used=False, dataset_identity=datasets[0].identity,
        code_identity=digest([implementation_identity(), Path(__file__).read_text(encoding="utf-8")]))
    if (out / "protocol.json").exists() and json.loads((out / "protocol.json").read_text()) != protocol:
        raise ValueError("Cross-validation protocol changed; choose a new directory")
    write_json(out / "protocol.json", protocol)
    for first in range(0, len(folds), args.batch_folds):
        group = folds[first:first + args.batch_folds]
        checkpoint = out / f"ensemble_{first:02d}.pt"
        views = [View(datasets, args.heads, set(f["training_animals"])) for f in group]
        groups = [{a: [i for i, r in enumerate(v.records) if r["animal"] == a] for a in v.animals} for v in views]
        rngs = [random.Random(args.seed) for _ in group]
        params, buffers, forward = make_ensemble(len(group), args.base, args.heads, args.seed, device)
        opt = torch.optim.AdamW(list(params.values()), lr=3e-4, weight_decay=1e-4)
        epoch, history = 0, []
        if checkpoint.exists():
            ck = torch.load(checkpoint, map_location=device, weights_only=True)
            if ck["protocol_digest"] != digest(protocol):
                raise ValueError("Ensemble resume identity mismatch")
            with torch.no_grad():
                for name, p in params.items(): p.copy_(ck["params"][name])
                for name, b in buffers.items(): b.copy_(ck["buffers"][name])
            opt.load_state_dict(ck["optimizer"])
            for rng, state in zip(rngs, ck["rngs"]): rng.setstate(state)
            epoch, history = ck["epoch"], ck["history"]
        started = time.monotonic()
        while epoch < args.epochs:
            epoch_losses = []
            for _ in range(args.steps_per_epoch):
                samples = []
                for view, groups_i, rng in zip(views, groups, rngs):
                    animal = rng.choice(view.animals)
                    index = rng.choice(groups_i[animal])
                    samples.append(view.sample(index, "cpu", rng.random() < .5))
                arrays = [torch.cat([s[k] for s in samples], dim=0).to(device) for k in range(4)]
                x, rows, valid, region = arrays
                opt.zero_grad(set_to_none=True)
                logits, regions = forward(params, buffers, x[:, None])
                loss = independent_losses(logits[:, 0], regions[:, 0], rows, valid, region)
                if not torch.isfinite(loss).all():
                    raise FloatingPointError("Non-finite independent-model loss")
                loss.sum().backward()
                clip_independently(params)
                opt.step()
                epoch_losses.append(loss.detach().cpu().numpy())
            epoch += 1
            average = np.mean(epoch_losses, axis=0)
            for i, fold in enumerate(group):
                history.append(dict(epoch=epoch, held_animal=fold["held_animal"], train_loss=float(average[i])))
            state = dict(params=params, buffers=buffers, optimizer=opt.state_dict(), epoch=epoch,
                         history=history, rngs=[rng.getstate() for rng in rngs], protocol_digest=digest(protocol))
            tmp = checkpoint.with_suffix(".writing.pt")
            torch.save(state, tmp); tmp.replace(checkpoint)
            write_csv(out / f"ensemble_{first:02d}_history.csv", history)
            print(json.dumps(dict(first_fold=first, epoch=epoch, folds=len(group),
                mean_train_loss=float(average.mean()), elapsed_s=time.monotonic()-started)), flush=True)
        for i, fold in enumerate(group):
            directory = output_dir(out / fold["held_animal"])
            model_state = {name: p[i].detach().cpu() for name, p in params.items()}
            model_state.update({name: b[i].detach().cpu() for name, b in buffers.items()})
            exported = dict(format="inner-retina-experiment-v1", model=model_state,
                config=dict(base=args.base, heads=args.heads, **fold), identity=datasets[0].identity,
                epoch=epoch, step=epoch * args.steps_per_epoch, inference_only=True,
                training_resume=str(checkpoint), protocol_digest=digest(protocol), experimental=True, validated=False)
            torch.save(exported, directory / "last.pt")
        del params, buffers, opt, forward
        if device.startswith("cuda"): torch.cuda.empty_cache()
    write_json(out / "training_complete.json", dict(folds=len(folds), epochs=args.epochs,
        heads=args.heads, protocol_digest=digest(protocol), final_test_used=False))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, default=DEFAULT)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--heads", type=int, choices=(4, 8), default=8)
    p.add_argument("--base", type=int, default=8)
    p.add_argument("--epochs", type=int, default=124)
    p.add_argument("--steps-per-epoch", type=int, default=48)
    p.add_argument("--batch-folds", type=int, default=7)
    p.add_argument("--seed", type=int, default=20260908)
    p.add_argument("--device")
    run(p.parse_args())
