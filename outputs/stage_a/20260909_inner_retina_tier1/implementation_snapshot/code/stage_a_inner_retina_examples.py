"""Manual-reference image examples, using frozen development data only.

No torch import: matplotlib and torch's OpenMP runtimes conflict on this host.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from stage_a.common import DEFAULT, output_dir, write_json
from stage_a_review import FrozenSplit
from stage_a_inner_retina import SURFACES, SENSITIVITY_KEY

COLORS = ["#00D9FF", "#FFE04B", "#FF8D45", "#EE74FF"]
CASES = [
    ("TS169_OS_2025-01-14_D35_s04_121533_b0164", "Clearer image · TS169"),
    ("TS325_OD_2026-01-05_D42_s05_131602_b0128", "Vessel shadows · TS325"),
    (SENSITIVITY_KEY, "Known major failure · TS325, b0510"),
]


def run(args):
    data = FrozenSplit(args.data, "validation")
    lookup = {r["key"]: r for r in data.records}
    out = output_dir(args.out)
    fig, axes = plt.subplots(3, 3, figsize=(17, 11.6), constrained_layout=True)
    details = []
    for case, (key, title) in enumerate(CASES):
        r = lookup[key]
        entry = data.cache["entries"][key]
        with np.load(entry["file"]["path"], allow_pickle=False) as c:
            img = c["x"][0]
        with np.load(r["targets"], allow_pickle=False) as c:
            truth, valid, shadow = c["rows_label"][:4], c["valid"][:4], c["shadow"]
        with np.load(Path(args.eval) / f"{key}.npz", allow_pickle=False) as c:
            pred, keep = c["rows"][:4], c["retained"][:4]
        truth = truth + entry["label_offset"]
        pred = pred + entry["label_offset"]
        observed = truth[valid & np.isfinite(truth)]
        lo, hi = max(0, observed.min() - 35), min(img.shape[0], observed.max() + 55)
        if case == 2:
            hi = min(img.shape[0], max(hi, np.quantile(pred[np.isfinite(pred)], .95) + 20))
        for j, ax in enumerate(axes[case]):
            ax.imshow(img, cmap="gray", vmin=0, vmax=1, aspect="auto")
            ax.set_ylim(hi, lo)
            ax.set_xlim(0, img.shape[1] - 1)
            ax.set_xlabel("A-line")
            ax.set_ylabel("Depth (pixels; vitreous above)")
            ax.set_title(["Your manual boundaries", "Current model · all raw predictions", "Current model · retained measurements"][j], fontsize=10)
            for k, color in enumerate(COLORS):
                values = truth[k] if j == 0 else pred[k]
                mask = valid[k] if j == 0 else np.isfinite(values) if j == 1 else keep[k]
                ax.plot(np.where(mask, values, np.nan), color=color, lw=1.35)
            if j == 2:
                for k, color in enumerate(COLORS):
                    ax.plot(np.where(valid[k], truth[k], np.nan), color=color,
                            lw=.9, ls=(0, (2, 3)), alpha=.85)
            if j == 0:
                ax.text(.015, .97, title, transform=ax.transAxes, va="top", fontsize=10,
                        color="white", bbox=dict(facecolor="black", alpha=.75, edgecolor="none"))
        error = np.abs(pred - truth)[valid] * r["px_um"]
        crosses = np.any(pred[:-1] > pred[1:], axis=0)
        details.append(dict(key=key, title=title, eligible_boundary_columns=int(valid.sum()),
            median_abs_um=float(np.median(error)), raw_crossing_alines=int(crosses.sum()),
            any_boundary_withheld_alines=int((~keep).any(axis=0).sum()), shadow_alines=int(shadow.sum())))
        axes[case, 1].text(.02, .98,
            f"Manual-supported median error: {np.median(error):.1f} µm\n"
            f"Crossing A-lines: {crosses.sum()}/{crosses.size}",
            transform=axes[case, 1].transAxes, color="white", va="top", fontsize=8,
            bbox=dict(facecolor="black", alpha=.7, edgecolor="none"))
    handles = [Line2D([], [], color=c, lw=2, label=s) for c, s in zip(COLORS, SURFACES)]
    fig.legend(handles=handles, loc="outside lower center", ncol=4, frameon=False)
    fig.suptitle("Inner-retina checkpoint: current v4 predictions compared with manual annotations\n"
                 "Reporting scope changed; segmentation predictions are unchanged. "
                 "Dotted = manual reference; gaps = withheld evidence, not zero thickness.", fontsize=13)
    path = out / "baseline_examples.png"
    fig.savefig(path, dpi=145)
    plt.close(fig)
    write_json(out / "example_measurements.json", dict(examples=details,
        selection="Two named representative cases plus the previously identified b0510 failure; not a random sample.",
        manual_masks="Frozen Stage A masks; legacy edit flags do not locate individual strokes.",
        coordinate_system="Native canonical depth, label crop offset restored; no interpolation or smoothing.",
        checkpoint_changed=False, final_test_used=False))
    print(path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT)
    parser.add_argument("--eval", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    run(parser.parse_args())
