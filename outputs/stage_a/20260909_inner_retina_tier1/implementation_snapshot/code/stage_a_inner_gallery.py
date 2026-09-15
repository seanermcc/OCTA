"""Static scientific comparisons against manual annotations; no torch imports."""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

from stage_a.common import DEFAULT, output_dir, write_json
from stage_a_review import FrozenSplit
from stage_a_inner_retina_examples import CASES, COLORS
from stage_a_inner_retina import SURFACES


def run(args):
    if args.split not in ("train", "validation", "development"):
        raise ValueError("Final-test images are locked")
    splits = ("train", "validation") if args.split == "development" else (args.split,)
    data = [FrozenSplit(args.data, split) for split in splits]
    lookup = {r["key"]: r for d in data for r in d.records}
    cache = {key: entry for d in data for key, entry in d.cache["entries"].items()}
    cases = [item.split("=", 1) for item in args.cases] if args.cases else CASES
    methods = [item.split("=", 1) for item in args.methods]
    out = output_dir(args.out)
    fig, axes = plt.subplots(len(cases), len(methods) + 1, figsize=(5.4 * (len(methods)+1), 3.9*len(cases)),
                             constrained_layout=True, squeeze=False)
    measurements = []
    for i, (key, title) in enumerate(cases):
        r = lookup[key]; entry = cache[key]
        with np.load(entry["file"]["path"], allow_pickle=False) as d:
            img = d["x"][0]
        with np.load(r["targets"], allow_pickle=False) as d:
            truth, valid = d["rows_label"][:4] + entry["label_offset"], d["valid"][:4]
        predictions = []
        for name, directory in methods:
            with np.load(Path(directory.format(animal=r["animal"])) / f"{key}.npz", allow_pickle=False) as d:
                predictions.append(d["rows"][:4] + entry["label_offset"])
        reference = truth[valid]
        lo, hi = max(0, reference.min()-25), min(img.shape[0], reference.max()+35)
        if i == 2:
            lo = max(0, min(lo, *(np.nanquantile(p, .01)-10 for p in predictions)))
            hi = min(img.shape[0], max(hi, *(np.nanquantile(p, .99)+10 for p in predictions)))
        for j, ax in enumerate(axes[i]):
            ax.imshow(img, cmap="gray", vmin=0, vmax=1, aspect="auto")
            ax.set(xlim=(0, img.shape[1]-1), ylim=(hi, lo), xlabel="A-line", ylabel="Depth (pixels)")
            ax.set_title("Manual reference" if j == 0 else methods[j-1][0], fontsize=11)
            if j == 0:
                for k, color in enumerate(COLORS):
                    ax.plot(np.where(valid[k], truth[k], np.nan), color=color, lw=1.6)
                ax.text(.02, .97, title, transform=ax.transAxes, va="top", color="white", fontsize=9,
                        bbox=dict(facecolor="black", alpha=.7, edgecolor="none"))
            else:
                pred = predictions[j-1]
                for k, color in enumerate(COLORS):
                    ax.plot(pred[k], color=color, lw=1.35)
                    ax.plot(np.where(valid[k], truth[k], np.nan), color=color, lw=1, ls=(0, (2, 3)))
                error = np.abs(pred - truth)[valid] * r["px_um"]
                crossing = int(np.any(pred[:-1] > pred[1:], axis=0).sum())
                measurements.append(dict(key=key, method=methods[j-1][0], median_abs_um=float(np.median(error)),
                    crossing_alines=crossing, eligible_columns=int(valid.sum())))
                ax.text(.02, .97, f"Median error {np.median(error):.1f} µm\nCrossings {crossing}/512 A-lines",
                    transform=ax.transAxes, va="top", color="white", fontsize=9,
                    bbox=dict(facecolor="black", alpha=.72, edgecolor="none"))
    fig.suptitle(args.title + "\nSolid = raw prediction; dotted = eligible manual reference. "
                 "These examples do not establish average performance.", fontsize=13)
    fig.legend(handles=[Line2D([], [], color=c, lw=2, label=n) for c, n in zip(COLORS, SURFACES)],
               loc="outside lower center", ncol=4, frameon=False)
    fig.savefig(out / "comparison_examples.png", dpi=145)
    plt.close(fig)
    write_json(out / "measurements.json", dict(examples=measurements, final_test_used=False,
        coordinates="Native canonical depth; frozen crop offset restored without interpolation"))
    print(out / "comparison_examples.png")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, default=DEFAULT)
    p.add_argument("--split", choices=("train", "validation", "development"), default="validation")
    p.add_argument("--cases", nargs="+", help="Explicit key=caption pairs; defaults to the three validation examples")
    p.add_argument("--methods", nargs="+", required=True, help="Display label=prediction directory")
    p.add_argument("--title", required=True)
    p.add_argument("--out", type=Path, required=True)
    run(p.parse_args())
