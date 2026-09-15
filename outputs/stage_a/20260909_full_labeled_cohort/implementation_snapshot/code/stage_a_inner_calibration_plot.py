"""Plot animal-held-out coverage/error curves without importing torch."""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


def run(args):
    decoder = json.loads((args.calibration / "calibration_summary.json").read_text())["decoder"]
    decoder_name = {"dp_project": "ordered DP", "soft": "original soft estimator", "graph_cut": "joint graph cut"}[decoder]
    with (args.calibration / "held_animal_curves.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    animals = sorted({r["held_animal"] for r in rows})
    colors = dict(zip(animals, plt.get_cmap("tab10").colors))
    for title, names, filename in (
        ("Boundary error", ["ILM", "RNFL_GCL", "GCL_IPL", "IPL_INL"], "coverage_error_boundaries.png"),
        ("Thickness error", ["RNFL", "GCL", "IPL", "INNER_RETINA"], "coverage_error_thickness.png")):
        fig, axes = plt.subplots(2, 2, figsize=(12, 9.2), constrained_layout=True)
        for name, ax in zip(names, axes.flat):
            for animal in animals:
                for sensitivity, style in (("with_b0510", "-"), ("without_b0510", "--")):
                    if sensitivity == "without_b0510" and animal != "TS325":
                        continue
                    selected = sorted([r for r in rows if r["held_animal"] == animal
                        and r["name"] == name and r["sensitivity"] == sensitivity],
                        key=lambda r: float(r["calibration_quantile"]))
                    selected = [r for r in selected if r["coverage"] and r["p95_abs_um"]]
                    if not selected:
                        continue
                    ax.plot([float(r["coverage"])*100 for r in selected],
                        [float(r["p95_abs_um"]) for r in selected], style,
                        color=colors[animal], marker="o", ms=3, lw=1.7)
            ax.set(title=name, xlabel="Retained manual-reference columns (%)",
                   ylabel="Retained p95 absolute error (µm)", xlim=(0, 101), yscale="log")
            ax.grid(alpha=.2, which="both")
        handles = [Line2D([], [], color=colors[a], lw=2, label=a) for a in animals]
        handles.append(Line2D([], [], color="black", ls="--", label="TS325 without b0510"))
        fig.legend(handles=handles, loc="outside lower center", ncol=4, frameon=False)
        fig.suptitle(f"{title} ({decoder_name}): {len(animals)}-animal development cross-validation\n"
            "Each cutoff comes from a different calibration animal. Dashed TS325 curve shows b0510 sensitivity.\n"
            "Conditional error among retained columns; withholding is missing evidence, not a zero error.", fontsize=12)
        fig.savefig(args.calibration / filename, dpi=160)
        plt.close(fig)
        print(args.calibration / filename)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--calibration", type=Path, required=True)
    run(p.parse_args())
