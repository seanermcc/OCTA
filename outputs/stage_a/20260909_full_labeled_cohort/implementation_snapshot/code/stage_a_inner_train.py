"""Isolated four/eight-head experiments and animal-disjoint calibration folds.

The original stage_a package and delivered checkpoints are never modified.
Each run checkpoints every epoch; completed resumes leave history untouched.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import random
import time

import numpy as np
import torch
from torch import nn

from stage_a.common import DEFAULT, digest, output_dir, write_json, write_csv
from stage_a.data import Dataset
from stage_a.model import BoundaryUNet, decode, losses


class InnerUNet(BoundaryUNet):
    def __init__(self, base=8, heads=4):
        if heads not in (4, 8):
            raise ValueError("Only the four/eight-head comparison is supported")
        super().__init__(base)
        self.heads = heads
        if heads == 4:
            self.boundary = nn.Conv2d(base, 4, 1)
            self.region = nn.Conv2d(base, 3, 1)


class View:
    def __init__(self, datasets, heads, animals=None):
        self.heads = heads
        self.items = [(d, i) for d in datasets for i, r in enumerate(d.records)
                      if sum(r["eligible_columns_by_surface"][:heads]) > 0
                      and (animals is None or r["animal"] in animals)]
        self.records = [d.records[i] for d, i in self.items]
        self.animals = sorted({r["animal"] for r in self.records})
        if not self.records:
            raise ValueError("No eligible manual training evidence")

    def sample(self, index, device="cpu", flip=False):
        d, i = self.items[index]
        x, rows, valid, region = d.sample(i, device, flip)
        rows, valid = rows[:, :self.heads], valid[:, :self.heads]
        region = torch.where(region < self.heads - 1, region, -100)
        return x, rows, valid, region


def implementation_identity():
    here = Path(__file__).resolve()
    paths = [here] + [here.parent / "stage_a" / f"{name}.py" for name in
                     ("model", "data", "eligibility", "geometry", "common", "partitions")]
    return digest({p.name: p.read_text(encoding="utf-8") for p in paths})


def load(path, device="cpu"):
    ck = torch.load(path, map_location="cpu", weights_only=True)
    if ck.get("format") != "inner-retina-experiment-v1":
        raise ValueError("Not an isolated inner-retina experiment checkpoint")
    model = InnerUNet(ck["config"]["base"], ck["config"]["heads"]).to(device)
    model.load_state_dict(ck["model"])
    return model, ck


def save(path, model, opt, identity, config, step, epoch, best, rng, history):
    checkpoint = dict(format="inner-retina-experiment-v1", model=model.state_dict(),
        optimizer=opt.state_dict(), identity=identity, config=config, step=step, epoch=epoch,
        best_validation=best, rng=rng.getstate(), torch_rng=torch.get_rng_state(),
        cuda_rng=torch.cuda.get_rng_state_all() if torch.cuda.is_available() else [],
        code_identity=implementation_identity(), history=history, experimental=True, validated=False)
    tmp = Path(path).with_suffix(".writing.pt")
    torch.save(checkpoint, tmp)
    tmp.replace(path)


def validation_loss(model, view, device, region_weight):
    by = defaultdict(list)
    model.eval()
    with torch.no_grad():
        for i, r in enumerate(view.records):
            x, rows, valid, region = view.sample(i, device)
            logits, regions = model(x)
            value, _ = losses(logits, regions, rows, valid, region, region_weight)
            by[r["animal"]].append(float(value))
    return float(np.mean([np.mean(v) for v in by.values()]))


def run(args):
    torch.set_num_threads(4)
    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    training = Dataset(args.data, "train")
    validation = Dataset(args.data, "validation")
    permitted = sorted(set(training.animals + validation.animals))
    fold = bool(args.held_animal)
    if fold:
        held, calibration = args.held_animal, args.calibration_animal
        if held not in permitted or calibration not in permitted or held == calibration:
            raise ValueError("A fold requires two distinct permitted animals for held-out evaluation and calibration")
        animals = set(permitted) - {held, calibration}
        train = View([training, validation], args.heads, animals)
        val = None  # Fixed budget; neither held nor calibration animal selects weights.
    else:
        if args.calibration_animal:
            raise ValueError("Calibration animal requires a held-out fold")
        train = View([training], args.heads)
        val = View([validation], args.heads)
    identity = dict(**training.identity, training_keys=[r["key"] for r in train.records],
                    validation_keys=[] if val is None else [r["key"] for r in val.records])
    config = dict(heads=args.heads, base=args.base, lr=args.lr, region_weight=args.region_weight,
        seed=args.seed, steps_per_epoch=args.steps_per_epoch,
        held_animal=args.held_animal, calibration_animal=args.calibration_animal,
        training_animals=train.animals, weight_selection="fixed_epoch_budget" if fold else "animal_macro_validation_loss",
        sampling="uniform_animal_then_uniform_eligible_bscan", augmentation="horizontal_flip_only")
    out = output_dir(args.out)
    if (out / "last.pt").exists() and not args.resume:
        raise FileExistsError("Choose a new output or explicitly resume this isolated experiment")
    rng = random.Random(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
    torch.backends.cudnn.benchmark = False
    torch.use_deterministic_algorithms(True, warn_only=True)
    model = InnerUNet(args.base, args.heads).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    step, epoch, best, history = 0, 0, None, []
    if args.resume:
        model, ck = load(args.resume, device)
        if ck["identity"] != identity or ck["config"] != config or ck["code_identity"] != implementation_identity():
            raise ValueError("Resume data/config/implementation mismatch")
        opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
        opt.load_state_dict(ck["optimizer"])
        rng.setstate(ck["rng"])
        torch.set_rng_state(ck["torch_rng"])
        if ck["cuda_rng"]:
            torch.cuda.set_rng_state_all(ck["cuda_rng"])
        step, epoch, best, history = ck["step"], ck["epoch"], ck["best_validation"], ck["history"]
    target = args.epochs * args.steps_per_epoch
    if step >= target:
        print(f"Already complete at step {step}; checkpoint and history preserved", flush=True)
        return
    groups = {a: [i for i, r in enumerate(train.records) if r["animal"] == a] for a in train.animals}
    start = time.monotonic()
    while step < target:
        model.train()
        values, gradients, sampled = [], [], []
        for _ in range(args.steps_per_epoch):
            animal = rng.choice(train.animals)
            index = rng.choice(groups[animal])
            flip = rng.random() < .5
            x, rows, valid, region = train.sample(index, device, flip)
            opt.zero_grad(set_to_none=True)
            logits, regions = model(x)
            loss, _ = losses(logits, regions, rows, valid, region, args.region_weight)
            if not torch.isfinite(loss):
                raise FloatingPointError("Non-finite training loss")
            loss.backward()
            grads = [p.grad for p in model.parameters() if p.grad is not None]
            if not all(torch.isfinite(g).all() for g in grads):
                raise FloatingPointError("Non-finite gradient")
            norm = float(torch.nn.utils.clip_grad_norm_(model.parameters(), 5.))
            if norm <= 0:
                raise RuntimeError("Zero gradient")
            opt.step()
            step += 1
            values.append(float(loss.detach()))
            gradients.append(norm)
            sampled.append([train.records[index]["key"], flip])
        epoch += 1
        v = None if val is None else validation_loss(model, val, device, args.region_weight)
        event = dict(epoch=epoch, step=step, train_loss=float(np.mean(values)),
            validation_loss=v, min_gradient=min(gradients), max_gradient=max(gradients),
            sampling_digest=digest(sampled), elapsed_this_invocation_s=time.monotonic() - start)
        history.append(event)
        improved = v is not None and (best is None or v < best)
        if improved:
            best = v
            save(out / "best.pt", model, opt, identity, config, step, epoch, best, rng, history)
        save(out / "last.pt", model, opt, identity, config, step, epoch, best, rng, history)
        write_csv(out / "history.csv", history)
        print(json.dumps(event), flush=True)
    model.eval()
    x, *_ = train.sample(0, device)
    with torch.no_grad():
        expected = model(x)[0]
        restored, _ = load(out / "last.pt", device)
        restored.eval()
        actual = restored(x)[0]
        if not torch.equal(expected, actual):
            raise AssertionError("Checkpoint reload changed predictions")
    write_json(out / "training_summary.json", dict(config=config, identity=identity,
        epochs=epoch, steps=step, best_validation=best, checkpoint_reload_exact=True,
        parameters=sum(p.numel() for p in model.parameters()),
        code_identity=implementation_identity(), elapsed_this_invocation_s=time.monotonic() - start,
        final_test_accessed=False, experimental=True, validated=False))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, default=DEFAULT)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--heads", type=int, choices=(4, 8), default=4)
    p.add_argument("--base", type=int, default=8)
    p.add_argument("--lr", type=float, default=3e-4)
    p.add_argument("--region-weight", type=float, default=.1)
    p.add_argument("--seed", type=int, default=20260908)
    p.add_argument("--epochs", type=int, default=200)
    p.add_argument("--steps-per-epoch", type=int, default=48)
    p.add_argument("--device")
    p.add_argument("--resume", type=Path)
    p.add_argument("--held-animal")
    p.add_argument("--calibration-animal")
    run(p.parse_args())
