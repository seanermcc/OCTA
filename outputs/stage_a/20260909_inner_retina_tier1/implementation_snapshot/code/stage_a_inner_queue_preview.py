"""Show unreviewed automatic candidates from the emitted GUI packs."""
import argparse
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from stage_a_inner_retina_examples import COLORS
from stage_a_inner_retina import SURFACES


def run(args):
    paths = sorted((args.queue / "packs").glob("*_pack.npz"))
    if not paths:
        raise ValueError("No review packs found")
    fig, axes = plt.subplots(len(paths), 3, figsize=(15, 4.1*len(paths)+1),
                             squeeze=False, constrained_layout=True)
    examples = []
    for row, path in enumerate(paths):
        with np.load(path, allow_pickle=False) as d:
            pack = {k: d[k].copy() for k in d.files}
        scores = pack["suspect_score"]
        priority = [i for i in np.argsort(-scores) if not pack["is_control"][i]][:2]
        controls = np.flatnonzero(pack["is_control"]).tolist()[:1]
        selected = priority + controls
        sid = str(pack["scan_id"][0])
        for column, ax in enumerate(axes[row]):
            if column >= len(selected):
                ax.set_visible(False); continue
            i = selected[column]
            image, surfaces = pack["images"][i], pack["surfaces"][i, :4]
            retained = pack["inner_retained"][i]
            role = "Control example" if pack["is_control"][i] else "Priority for review"
            ax.imshow(image, cmap="gray", aspect="auto",
                      vmin=np.percentile(image, 2), vmax=np.percentile(image, 99))
            for k, color in enumerate(COLORS):
                ax.plot(np.where(retained[k], surfaces[k], np.nan), color=color, lw=1.3)
                ax.plot(np.where(~retained[k], surfaces[k], np.nan), color=color, lw=.8, ls="--", alpha=.6)
            ax.set(xlim=(0, image.shape[1]-1), ylim=(image.shape[0]-1, 0),
                xlabel="A-line", ylabel="Depth in review crop (pixels)",
                title=f"{sid.split('_')[0]} · b{int(pack['bscan_index'][i]):04d} · {role}")
            ax.text(.02, .98, "Automatic candidates · not yet manually reviewed", transform=ax.transAxes,
                va="top", color="white", fontsize=8, bbox=dict(facecolor="black", alpha=.7, edgecolor="none"))
            examples.append(dict(scan_id=sid, bscan=int(pack["bscan_index"][i]), role=role, manually_reviewed=False))
    fig.suptitle("Review queue: two priority examples and one control from each volume\n"
        "Solid = currently retained candidate; dashed = withheld candidate. Every line still requires human review.", fontsize=13)
    fig.legend(handles=[Line2D([], [], color=c, lw=2, label=n) for c, n in zip(COLORS, SURFACES)],
               loc="outside lower center", ncol=4, frameon=False)
    fig.savefig(args.queue / "review_examples.png", dpi=150)
    plt.close(fig)
    (args.queue / "preview_examples.json").write_text(json.dumps(examples, indent=2), encoding="utf-8")
    print(args.queue / "review_examples.png")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--queue", type=Path, required=True)
    run(p.parse_args())
