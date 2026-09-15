"""Original-coordinate overlays and a development-only entropy/error study.

Lives outside the `stage_a` package on purpose: `train.code_identity()` hashes
every module in that directory, so analysis code added there would invalidate
resume for already-trained checkpoints.

Reads the prediction arrays a `stage_a.evaluate` run already wrote, the frozen
derived targets and the frozen image caches. It never re-reads human labels,
never touches the repeatability tree and refuses the test split. Overlays are
drawn in original disk coordinates: the cached canonical image is flipped back
and every row is mapped with the frozen inverse, so nothing here depends on a
second orientation decision.

Any entropy threshold printed here is a *candidate* read off development data.
It is not calibrated and is not an acceptance criterion.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from stage_a.common import DEFAULT, output_dir, write_json, write_csv, verify, fingerprint
from stage_a.partitions import validate_partition
from stage_a.geometry import PREPROCESS
from eight_surface.config import SURFACE_NAMES
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Deliberately torch-free. `stage_a.data.Dataset` imports torch, and loading
# torch's libomp into the same process as matplotlib's MKL libiomp5md aborts
# with "OMP: Error #15" on this Windows environment. Nothing here needs a
# tensor, so `FrozenSplit` repeats Dataset's integrity checks without it.

GROSS_UM = 25.0  # provisional reporting cutoff, not an acceptance threshold


class FrozenSplit:
    """Dataset.__init__'s identity and fingerprint checks, without torch."""

    def __init__(self, path, split):
        self.path = Path(path)
        self.manifest = json.loads((self.path / "manifest.json").read_text())
        self.partitions = json.loads((self.path / "partitions.json").read_text())
        self.cache = json.loads((self.path / "cache_manifest.json").read_text())
        validate_partition(self.manifest, self.partitions)
        verify(self.partitions["manifest"])
        if (self.cache["dataset_id"] != self.manifest["dataset_id"]
                or self.cache["preprocessing"] != PREPROCESS):
            raise ValueError("Cache/dataset preprocessing identity mismatch")
        self.records = [r for r in self.manifest["records"]
                        if r["key"] in self.partitions["keys"][split]]
        if not self.records:
            raise ValueError("Empty partition")
        missing = [r["key"] for r in self.records if r["key"] not in self.cache["entries"]]
        if missing:
            raise FileNotFoundError(f"Missing caches: {missing}")
        for r in self.records:
            verify(self.cache["entries"][r["key"]]["file"])
            verify(r["targets_fingerprint"])
        self.identity = dict(dataset_id=self.manifest["dataset_id"],
                             partition_id=self.partitions["partition_id"],
                             preprocessing=PREPROCESS,
                             cache_manifest=fingerprint(self.path / "cache_manifest.json"))


def longest_run(mask):
    bounds = np.diff(np.r_[False, np.asarray(mask, bool), False].astype(int))
    start = np.flatnonzero(bounds == 1)
    end = np.flatnonzero(bounds == -1)
    return int(np.max(end - start)) if len(start) else 0


def _average_ranks(values):
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), float)
    ranks[order] = np.arange(1, len(values) + 1, dtype=float)
    s = values[order]
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and s[j + 1] == s[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + 1 + j + 1) / 2.0
        i = j + 1
    return ranks


def auroc(score, positive):
    """Rank-based AUROC; sklearn is not installed in this environment."""
    score, positive = np.asarray(score, float), np.asarray(positive, bool)
    n1, n0 = int(positive.sum()), int((~positive).sum())
    if not n1 or not n0:
        return None
    ranks = _average_ranks(score)
    return float((ranks[positive].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def spearman(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3:
        return None
    ra, rb = _average_ranks(a), _average_ranks(b)
    if ra.std() == 0 or rb.std() == 0:
        return None
    return float(np.corrcoef(ra, rb)[0, 1])


def overlay(path, image, truth, valid, pred, entropy, title, vhi, offset):
    """Draw in original disk coordinates. Canonical rows are mapped back."""
    native_depth = image.shape[0]
    disk = image[::-1] if vhi else image
    to_disk = (lambda r: native_depth - 1 - np.asarray(r)) if vhi else (lambda r: np.asarray(r).copy())
    fig, ax = plt.subplots(2, 1, figsize=(11, 7.4), height_ratios=[4, 1],
                           constrained_layout=True)
    ax[0].imshow(disk, cmap="gray", aspect="auto", vmin=-0.1, vmax=1.1,
                 extent=[0, disk.shape[1], disk.shape[0], 0])
    colours = plt.cm.turbo(np.linspace(.05, .95, len(SURFACE_NAMES)))
    x = np.arange(disk.shape[1])
    shown = []
    for k, name in enumerate(SURFACE_NAMES):
        p = to_disk(pred[k] + offset)
        ax[0].plot(x, p, color=colours[k], lw=1.0, label=name)
        t = np.where(valid[k], to_disk(truth[k] + offset), np.nan)
        ax[0].plot(x, t, color=colours[k], lw=2.4, ls=":", alpha=.85)
        shown.append(p)
        if np.isfinite(t).any():
            shown.append(t)
    stacked = np.concatenate([np.asarray(s, float).ravel() for s in shown])
    stacked = stacked[np.isfinite(stacked)]
    if stacked.size:
        ax[0].set_ylim(min(disk.shape[0], stacked.max() + 70), max(0, stacked.min() - 70))
    ax[0].set_title(title, fontsize=8)
    ax[0].set_ylabel("original disk depth (px)")
    ax[0].legend(fontsize=6, ncol=8, loc="lower center", framealpha=.35)
    for k in range(len(SURFACE_NAMES)):
        ax[1].plot(x, entropy[k], color=colours[k], lw=.8)
    top = float(np.nanmax(entropy)) if np.isfinite(entropy).any() else 1.0
    ax[1].set_ylim(0, max(.05, top * 1.1))
    ax[1].set_xlim(0, disk.shape[1])
    ax[1].set_ylabel("entropy")
    ax[1].set_xlabel("A-line (original column order) | solid = prediction, dotted = human target where eligible")
    fig.savefig(path, dpi=130)
    plt.close(fig)


def run(args):
    root = Path(args.data)
    if args.split == "test":
        raise ValueError("Final-test animals are locked")
    m = json.loads((root / "manifest.json").read_text())
    data = FrozenSplit(root, args.split)
    out = output_dir(args.out)
    figures = output_dir(out / "overlays")
    evaldir = Path(args.eval)

    per_key, columns = [], []
    for r in data.records:
        path = evaldir / f"{r['key']}.npz"
        if not path.exists():
            continue
        with np.load(path, allow_pickle=False) as p:
            pred = {k: p[k].copy() for k in p.files}
        with np.load(r["targets"], allow_pickle=False) as t:
            tgt = {k: t[k].copy() for k in t.files}
        valid = tgt["valid"]
        if not valid.any():
            continue
        err = (pred["rows"] - tgt["rows_label"]) * r["px_um"]
        gross = valid & (np.abs(err) > GROSS_UM)
        runs = [longest_run(gross[k]) for k in range(len(SURFACE_NAMES))]
        per_key.append(dict(key=r["key"], animal=r["animal"], qc_group=r["qc_group"],
            scope_status=r["scope_status"], biological_group=r["biological_group"],
            n_eligible=int(valid.sum()),
            median_abs_um=float(np.median(np.abs(err[valid]))),
            p95_abs_um=float(np.quantile(np.abs(err[valid]), .95)),
            max_abs_um=float(np.abs(err[valid]).max()),
            gross_fraction=float(gross.sum() / valid.sum()),
            longest_gross_columns=int(max(runs)),
            worst_surface=SURFACE_NAMES[int(np.argmax(runs))],
            mean_entropy=float(pred["entropy"][valid].mean()) if "entropy" in pred else None))
        if "entropy" in pred:
            for k, name in enumerate(SURFACE_NAMES):
                sel = valid[k]
                if sel.any():
                    columns.append(dict(key=r["key"], animal=r["animal"], surface=name,
                        entropy=pred["entropy"][k][sel], abs_err=np.abs(err[k][sel])))

    per_key.sort(key=lambda d: d["key"])
    write_csv(out / "per_bscan_localized_failure.csv", per_key)

    # --- entropy as a candidate error signal, development validation only ---
    analysis, curve = [], []
    if columns:
        pooled_e = np.concatenate([c["entropy"] for c in columns])
        pooled_a = np.concatenate([c["abs_err"] for c in columns])
        groups = [("pooled", "all", pooled_e, pooled_a)]
        for name in SURFACE_NAMES:
            sel = [c for c in columns if c["surface"] == name]
            if sel:
                groups.append(("surface", name,
                               np.concatenate([c["entropy"] for c in sel]),
                               np.concatenate([c["abs_err"] for c in sel])))
        for animal in sorted({c["animal"] for c in columns}):
            sel = [c for c in columns if c["animal"] == animal]
            groups.append(("animal", animal,
                           np.concatenate([c["entropy"] for c in sel]),
                           np.concatenate([c["abs_err"] for c in sel])))
        for axis, group, e, a in groups:
            bad = a > GROSS_UM
            analysis.append(dict(axis=axis, group=group, n_columns=int(len(e)),
                spearman_entropy_vs_abs_error=spearman(e, a),
                auroc_entropy_predicts_gross=auroc(e, bad),
                gross_rate=float(bad.mean()),
                median_entropy=float(np.median(e)),
                median_entropy_gross=float(np.median(e[bad])) if bad.any() else None,
                median_entropy_ok=float(np.median(e[~bad])) if (~bad).any() else None))
        for q in (1.0, .99, .95, .9, .8, .7, .6, .5, .4, .3, .2, .1):
            threshold = float(np.quantile(pooled_e, q))
            keep = pooled_e <= threshold
            curve.append(dict(target_coverage=q, entropy_threshold=threshold,
                actual_coverage=float(keep.mean()),
                retained_median_abs_um=float(np.median(pooled_a[keep])) if keep.any() else None,
                retained_p95_abs_um=float(np.quantile(pooled_a[keep], .95)) if keep.any() else None,
                retained_gross_fraction=float((pooled_a[keep] > GROSS_UM).mean()) if keep.any() else None,
                gross_columns_remaining_per_1000_eligible=float(
                    (pooled_a[keep] > GROSS_UM).sum() / len(pooled_a) * 1000),
                note="candidate only; not calibrated, not an acceptance threshold"))
    write_csv(out / "entropy_error_analysis.csv", analysis)
    write_csv(out / "entropy_risk_coverage.csv", curve)

    # --- overlays ----------------------------------------------------------
    chosen = {}
    worst = sorted(per_key, key=lambda d: (-d["longest_gross_columns"], -d["max_abs_um"]))[:args.worst]
    for d in worst:
        chosen[d["key"]] = f"worst_localized_{d['longest_gross_columns']:03d}col"
    by_animal = {}
    for d in sorted(per_key, key=lambda d: d["median_abs_um"]):
        by_animal.setdefault((d["animal"], d["qc_group"]), []).append(d)
    for (animal, qc), items in sorted(by_animal.items()):
        chosen.setdefault(items[len(items) // 2]["key"], f"representative_{animal}_{qc}_median")
        chosen.setdefault(items[0]["key"], f"representative_{animal}_{qc}_best")
    index = []
    for r in data.records:
        if r["key"] not in chosen:
            continue
        entry = data.cache["entries"][r["key"]]
        with np.load(entry["file"]["path"], allow_pickle=False) as c:
            image, vhi = c["x"][0], bool(c["vitreous_high"])
        with np.load(evaldir / f"{r['key']}.npz", allow_pickle=False) as p:
            pred = {k: p[k].copy() for k in p.files}
        with np.load(r["targets"], allow_pickle=False) as t:
            tgt = {k: t[k].copy() for k in t.files}
        stat = next(d for d in per_key if d["key"] == r["key"])
        title = (f"{chosen[r['key']]} | {r['key']} | {r['animal']} QC={r['qc_group']} | "
                 f"{r['scope_status']} | median {stat['median_abs_um']:.1f} um, "
                 f"p95 {stat['p95_abs_um']:.1f} um, longest gross run {stat['longest_gross_columns']} col "
                 f"on {stat['worst_surface']} | EXPERIMENTAL, not validated")
        name = f"{chosen[r['key']]}__{r['key']}.png"
        overlay(figures / name, image, tgt["rows_label"], tgt["valid"], pred["rows"],
                pred.get("entropy", np.zeros_like(pred["rows"])), title,
                vhi, int(entry["label_offset"]))
        index.append(dict(figure=name, role=chosen[r["key"]], **stat))
    write_csv(out / "overlay_index.csv", index)
    write_json(out / "review_meta.json", dict(dataset_id=m["dataset_id"], split=args.split,
        eval_dir=str(evaldir), gross_um=GROSS_UM, n_bscans=len(per_key), n_overlays=len(index),
        coordinates="original disk depth; canonical rows mapped with the frozen inverse",
        entropy_note=("Entropy thresholds here are development candidates only; "
                      "no calibrated abstention is claimed."),
        experimental=True, validated=False))
    print(json.dumps(analysis[:1], indent=2))
    print(f"{len(per_key)} evaluated B-scans, {len(index)} overlays -> {figures}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, default=DEFAULT)
    p.add_argument("--split", choices=["train", "validation"], default="validation")
    p.add_argument("--eval", required=True, help="directory of a stage_a.evaluate run")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--worst", type=int, default=4)
    run(p.parse_args())
