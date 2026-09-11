"""Experimental major-vessel proposals from structural en-face contrast.

No trained model and no human-label writes. Work in native [B-scan, A-line]
coordinates using exactly the GUI's mean-dB retinal-band projection.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import ndimage as ndi
from skimage import morphology

from octa.volio import ProcessedVolume
from eight_surface.cnv_data import _mean_db_dataset
from eight_surface.cnv_labels import load_label

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "outputs/vasculature_baseline/20260909_major_vessels"
SCAN_IDS = [
    "TS165_OD_2025-04-29_WT_s06_114517",
    "TS165_OS_2025-04-29_WT_s02_121711",
    "TS247_OD_2024-10-30_D14_s05_105423",
    "TS267_OD_2025-04-16_D56_s03_102014",
    "TS305_OD_2025-08-07_D35_s01_114451",
    "TS325_OD_2026-03-03_D98_s01_131308",
]


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_projection(scan_id, out):
    path = out / "projections" / f"{scan_id}.npz"
    seg_path = ROOT / "outputs/eight_surface/segmented" / f"{scan_id}.npz"
    with np.load(seg_path, allow_pickle=False) as z:
        source = str(z["source"][0])
        band = np.asarray(z["retina_band"], dtype=int)
    stat = Path(source).stat()
    if path.exists():
        with np.load(path, allow_pickle=False) as z:
            if (str(z["source"][0]) == source
                    and int(z["source_mtime_ns"][0]) == stat.st_mtime_ns
                    and np.array_equal(z["retina_band"], band)):
                return z["structural_enface"].copy()
    print(f"Reading native projection: {scan_id}", flush=True)
    # Full-band projection is invariant to depth reversal. No B-scan, depth
    # reorientation, stored orientation flag, or predicted surface is used.
    with ProcessedVolume(source) as volume:
        projection = _mean_db_dataset(volume.struct, slice(*band))
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, structural_enface=projection,
                        source=np.array([source]), retina_band=band,
                        source_mtime_ns=np.array([stat.st_mtime_ns]),
                        projection_version=np.array(["1-retina-band-mean-db"]),
                        axis_order=np.array(["B-scan,A-line"]))
    return projection


def display_image(im):
    lo, hi = np.percentile(im[np.isfinite(im)], [1, 99])
    return np.clip((im - lo) / max(hi - lo, 1e-6), 0, 1)


def vessel_evidence(im):
    im = np.asarray(im, dtype=np.float64)
    if im.ndim != 2 or not np.isfinite(im).all():
        raise ValueError("Expected a finite native-grid 2D projection")
    # The outer ten pixels contain acquisition-frame edges, not reliable vessel
    # evidence. Reflect the interior before filtering so the black frame cannot
    # dominate either the Hessian or contrast normalization.
    rim = 10
    im = im.copy()
    for axis in (0, 1):
        differences = np.diff(im, axis=axis)
        interior = differences[:, rim:-rim] if axis == 0 else differences[rim:-rim, :]
        median_delta = np.median(interior, axis=1-axis)
        agreement = np.mean(np.sign(interior) == np.expand_dims(
            np.sign(median_delta), axis=1-axis), axis=1-axis)
        net = np.abs(ndi.uniform_filter1d(median_delta, 49))
        variation = ndi.uniform_filter1d(np.abs(median_delta), 49)
        coherence = net / np.maximum(variation, 1e-10)
        # Correct only abrupt, field-wide additive steps. A normally curving
        # vessel edge does not move nearly every pixel in the same direction.
        # A dark vessel has opposing entry/exit edges. Requiring a persistent
        # net step prevents deleting a straight, field-spanning vessel.
        jump = np.where((agreement > .85) & (np.abs(median_delta) > .05)
                        & (coherence > .75),
                        median_delta, 0)
        offset = np.r_[0., np.cumsum(jump)]
        im -= offset[:, None] if axis == 0 else offset[None, :]
    im = np.pad(im[rim:-rim, rim:-rim], rim, mode="reflect")
    smooth = ndi.gaussian_filter(im, 1.2)
    background = ndi.gaussian_filter(im, 24)
    dark = np.maximum(background - smooth, 0)
    scale = max(float(np.percentile(dark[rim:-rim, rim:-rim], 98)), 1e-6)
    dark /= scale
    # Normalized Hessian: prefer a valley across the vessel and relatively
    # little curvature along it. Round lesion spots have two large eigenvalues.
    strength = np.zeros(im.shape)
    for sigma in (2.5, 4., 6., 8., 11.):
        yy = ndi.gaussian_filter(smooth, sigma, order=(2, 0)) * sigma**2
        xx = ndi.gaussian_filter(smooth, sigma, order=(0, 2)) * sigma**2
        xy = ndi.gaussian_filter(smooth, sigma, order=(1, 1)) * sigma**2
        delta = np.sqrt((xx - yy)**2 + 4 * xy**2)
        a, b = (xx + yy - delta) / 2, (xx + yy + delta) / 2
        swap = np.abs(a) > np.abs(b)
        small, large = np.where(swap, b, a), np.where(swap, a, b)
        ratio = np.abs(small) / np.maximum(np.abs(large), 1e-10)
        ridge = np.maximum(large, 0) * np.exp(-ratio**2 / (2 * .5**2))
        strength = np.maximum(strength, ridge)
    strength /= max(float(np.percentile(strength[rim:-rim, rim:-rim], 98)), 1e-6)
    score = np.sqrt(np.clip(strength, 0, 2) * np.clip(dark, 0, 2))
    score[:rim] = score[-rim:] = 0
    score[:, :rim] = score[:, -rim:] = 0
    return score.astype(np.float32), dark.astype(np.float32), strength.astype(np.float32)


def make_mask(score, threshold, onh=None):
    mask = score >= threshold
    mask = morphology.opening(mask, morphology.disk(2))
    mask = morphology.closing(mask, morphology.disk(2))
    mask = morphology.remove_small_objects(mask, max_size=149)
    mask = morphology.remove_small_holes(mask, max_size=39)
    if onh is not None:
        mask &= ~onh
    return mask


def metrics(pred, truth, valid):
    tp = int((pred & truth & valid).sum())
    fp = int((pred & ~truth & valid).sum())
    fn = int((~pred & truth & valid).sum())
    return dict(dice=2*tp / max(2*tp+fp+fn, 1),
                precision=tp / max(tp+fp, 1), recall=tp / max(tp+fn, 1),
                tp=tp, fp=fp, fn=fn)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    records = []
    for scan_id in SCAN_IDS:
        projection = load_projection(scan_id, out)
        label_path = ROOT / "outputs/cnv_labels" / f"{scan_id}_cnv.npz"
        label = load_label(label_path) if label_path.exists() else None
        rec = dict(scan_id=scan_id, projection=projection, label=label,
                   label_path=label_path,
                   label_hash=file_hash(label_path) if label else None)
        records.append(rec)
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    for rec, ax in zip(records, axes.flat):
        ax.imshow(display_image(rec["projection"]), cmap="gray", vmin=0, vmax=1)
        ax.set_title(rec["scan_id"], fontsize=9)
        ax.axis("off")
    fig.tight_layout()
    fig.savefig(out / "inputs.png", dpi=140)
    plt.close(fig)
    if args.prepare_only:
        return
    for rec in records:
        rec["score"], rec["dark"], rec["ridge"] = vessel_evidence(rec["projection"])
    reviewed = [r for r in records if r["label"] is not None
                and r["label"]["reviewed_targets"][1]]
    if len(reviewed) != 2:
        raise RuntimeError("This pilot expects exactly two reviewed vessel masks")
    # Both images informed method development. Even leave-one-image threshold
    # transfer is a development diagnostic, NOT independent validation.
    thresholds = np.round(np.arange(.08, .401, .02), 2)
    sweep = []
    for rec in reviewed:
        for t in thresholds:
            label = rec["label"]
            mask = make_mask(rec["score"], t, label["onh_mask"])
            sweep.append(dict(scan_id=rec["scan_id"], threshold=float(t),
                              **metrics(mask, label["vasculature_mask"], ~label["onh_mask"])))
    with (out / "threshold_sweep.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(sweep[0]))
        writer.writeheader()
        writer.writerows(sweep)
    threshold = float(max(thresholds, key=lambda t: np.mean(
        [r["dice"] for r in sweep if r["threshold"] == t])))
    transfer = []
    for source in reviewed:
        best = max([r for r in sweep if r["scan_id"] == source["scan_id"]],
                   key=lambda r: r["dice"])
        target = next(r for r in reviewed if r is not source)
        transferred = next(r for r in sweep if r["scan_id"] == target["scan_id"]
                           and r["threshold"] == best["threshold"])
        transfer.append(dict(threshold_selected_on=source["scan_id"],
                             measured_on=target["scan_id"],
                             threshold=best["threshold"], dice=transferred["dice"]))
    (out / "threshold_transfer.json").write_text(json.dumps(transfer, indent=2))
    audit = []
    (out / "proposals").mkdir(exist_ok=True)
    for rec in records:
        label = rec["label"]
        onh = label["onh_mask"] if label is not None else None
        raw_pred = make_mask(rec["score"], threshold)
        pred = make_mask(rec["score"], threshold, onh)
        rec["pred"] = pred
        unassessed = np.ones(pred.shape, bool)
        unassessed[10:-10, 10:-10] = False
        row = dict(scan_id=rec["scan_id"], threshold=threshold,
                   predicted_pixels=int(pred.sum()),
                   human_vasculature_reviewed=bool(label is not None and label["reviewed_targets"][1]),
                   label_sha256=rec["label_hash"],
                   border_unassessed_pixels=int(unassessed.sum()),
                   onh_exclusion="human area mask" if onh is not None and onh.any() else "none")
        if row["human_vasculature_reviewed"]:
            valid = ~onh if onh is not None else np.ones(pred.shape, bool)
            row.update(metrics(pred, label["vasculature_mask"], valid))
            row["unassisted_full_grid"] = metrics(raw_pred, label["vasculature_mask"],
                                                  np.ones(pred.shape, bool))
        audit.append(row)
        np.savez_compressed(out / "proposals" / f"{rec['scan_id']}_proposal.npz",
                            predicted_vasculature_mask=pred, evidence=rec["score"],
                            unassisted_vasculature_mask=raw_pred,
                            unassessed_border_mask=unassessed,
                            human_onh_exclusion_mask=(onh if onh is not None else
                                                      np.zeros(pred.shape, bool)),
                            scan_id=np.array([rec["scan_id"]]),
                            method=np.array(["major-vessel-contrast-hessian-v1"]),
                            code_sha256=np.array([file_hash(__file__)]),
                            provenance=np.array(["automatic classical proposal; not a human label"]),
                            threshold=np.array([threshold]),
                            axis_order=np.array(["B-scan,A-line"]),
                            human_reviewed=np.array([False]))
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))
        for ax in axes:
            ax.imshow(display_image(rec["projection"]), cmap="gray", vmin=0, vmax=1)
            ax.axis("off")
        axes[0].set_title("Original structural en-face")
        overlay = np.zeros((*pred.shape, 4))
        overlay[pred] = [.1, .65, 1, .55]
        if onh is not None:
            overlay[onh] = [.2, 1, .4, .55]
        axes[1].imshow(overlay)
        axes[1].set_title("Automatic proposal" + (
            " | green = your ONH mask" if onh is not None and onh.any() else ""))
        if row["human_vasculature_reviewed"]:
            human = np.zeros_like(overlay)
            human[label["vasculature_mask"]] = [.1, .65, 1, .55]
            human[onh] = [.2, 1, .4, .6]
            axes[2].imshow(human)
            axes[2].set_title(f"Your brush mask | Dice {row['dice']:.3f}")
        else:
            axes[2].imshow(rec["score"], cmap="magma", vmin=0, vmax=1)
            axes[2].set_title("Contrast-and-shape evidence (not probability)")
        fig.suptitle(rec["scan_id"], fontsize=11)
        fig.tight_layout()
        fig.savefig(out / f"{rec['scan_id']}.png", dpi=130)
        plt.close(fig)
        if label is not None and file_hash(rec["label_path"]) != rec["label_hash"]:
            raise RuntimeError("Human label changed during the experiment; rerun audit")
    (out / "metrics.json").write_text(json.dumps(audit, indent=2))
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    for rec, ax in zip(records, axes.flat):
        ax.imshow(display_image(rec["projection"]), cmap="gray", vmin=0, vmax=1)
        overlay = np.zeros((*rec["pred"].shape, 4))
        overlay[rec["pred"]] = [.1, .65, 1, .6]
        onh = rec["label"]["onh_mask"] if rec["label"] is not None else None
        if onh is not None:
            overlay[onh] = [.2, 1, .4, .6]
        ax.imshow(overlay)
        ax.set_title(rec["scan_id"], fontsize=9)
        ax.axis("off")
    fig.suptitle("Major vessels: classical proposals on six scans\n"
                 "Blue = automatic proposal; green = existing human ONH mask; review required",
                 fontsize=13)
    fig.tight_layout()
    fig.savefig(out / "overview.png", dpi=140)
    plt.close(fig)
    report = [
        "# Major-vessel segmentation pilot — 2026-09-09", "",
        "A no-training contrast-and-shape method produced proposals for six scans. "
        "It is a useful starting mask, but does not yet replace human review. "
        "Only clearly visible major vessels are the target; capillaries and faint branches are outside this pilot.", "",
        "![Six proposals](overview.png)", "",
        "## Saved human work", "",
        "Both new masks were found in `outputs/cnv_labels`: TS165 OD WT s06, saved 10:12, "
        "and TS165 OS WT s02, saved 10:18. They are two eyes of one animal from one session. "
        "No human annotation was written or edited; saved hashes were checked after the run. "
        "Four additional scans from TS247, TS267, TS305 and TS325 have no reviewed vessel masks, "
        "so their accuracy cannot be scored.", "",
        "## Measurements", "",
        "Dice measures area overlap (1 = identical). These are development comparisons against "
        "freehand brush masks, not independent accuracy estimates. Both labeled images informed "
        "the preprocessing and threshold choice. Differences include vessel location, width, "
        "missing branches, and extra detections; a single Dice number does not separate them. "
        "The brush masks were not altered to agree with the algorithm.", "",
        "| Scan | Dice | Precision | Recall | ONH handling |", "|---|---:|---:|---:|---|",
    ]
    for row in audit[:2]:
        report.append(f"| {row['scan_id']} | {row['dice']:.3f} | {row['precision']:.3f} | "
                      f"{row['recall']:.3f} | {row['onh_exclusion']} |")
    report += ["", "The OS comparison excludes the existing human ONH area, including 186 pixels "
               "where vessel and ONH brush masks overlap. This is not automatic ONH detection. "
               "Without that human ONH exclusion, full-grid Dice is "
               f"{audit[0]['unassisted_full_grid']['dice']:.3f} (OD) and "
               f"{audit[1]['unassisted_full_grid']['dice']:.3f} (OS). "
               "The outer ten pixels are unassessed because of image-frame artifacts; "
               "labeled vessel pixels there still count as misses in the reported Dice/recall.", "",
               f"The final shared threshold is {threshold:.2f}, selected by mean Dice on the two masks "
               "over 0.08–0.40 in steps of 0.02. Threshold transfer between eyes gives "
               + ", ".join(f"{r['dice']:.3f} at threshold {r['threshold']:.2f}" for r in transfer)
               + ". This remains a same-animal development diagnostic; it is not a held-out test.", "",
               "## What the images show", "",
               "Large vessel trunks are recovered in several different appearances. Remaining "
               "errors include missed lower-contrast stretches, incorrect widths, extra small "
               "branches, and false positives at acquisition seams, lesion margins and the optic disc. "
               "TS267 D56 is a deliberately difficult example with motion streaks and lesion disruption; "
               "its proposal needs substantial correction. Inspect all six, including the failures.", "",
               "## Method and provenance", "",
               "The input is the original processed-volume structural projection, not a screenshot: "
               "mean 20*log10(amplitude) over the same stored retinal band used by the GUI. "
               "No retinal surfaces define the projection. The depth average is invariant to "
               "depth reversal; no stored orientation flag is used and the native [B-scan, A-line] "
               "grid is retained. Source MATLAB files are opened read-only.", "",
               "Processing: remove abrupt intensity jumps shared by more than 85% of a row/column "
               "when the median jump exceeds 0.05 dB and the net-to-total derivative ratio "
               "over 49 pixels exceeds 0.75 (to retain the opposing edges of straight vessels); "
               "reflect the interior across a 10-pixel frame; "
               "smooth at 1.2 pixels; subtract from a 24-pixel background; combine local darkness "
               "with a scale-normalized Hessian ridge response at sigma 2.5, 4, 6, 8 and 11 pixels "
               "(eigenvalue-ratio weight beta 0.5). Normalize each response by its interior 98th "
               "percentile, take the geometric mean, threshold, open/close with radius 2, remove "
               "components smaller than 150 pixels and fill holes smaller than 40 pixels. "
               "Very broad dark structures could still be affected by step correction. "
               "The evidence array is a filter response, not a "
               "calibrated probability or an acquisition-quality score.", "",
               "No network, forest, or learned segmentation weights were trained. Threshold "
               "selection still uses labels and is therefore calibration. The four additional "
               "scans use the same method and threshold. The green mask is reused human ONH "
               "annotation; ONH segmentation is not solved by this experiment.", "",
               "## How much labeling next", "",
               "The 32 scans belong to the existing general review queue (16 low, 8 medium, "
               "8 high); 32 is not a measured vessel-training requirement. Pause full tracing. "
               "A practical next pilot is 4–6 additional reviewed/corrected vessel masks "
               "from several other animals, spanning clean, low-contrast, motion-affected and "
               "lesion-containing scans. That is 6–8 total, a staged effort budget rather than "
               "a promise of sufficiency. Check completion/correction time and missed major "
               "branches, alongside overlap. Keep new animals separate while tuning and testing; "
               "random patches from the same scan are not independent test examples. Add more "
               "only when new scans expose errors or the learning curve still improves.", "",
               "If these rules need too much correction, the next candidate is a small pixel "
               "classifier (random forest using multiscale intensity, edge and ridge features) "
               "with vessel/background/artifact examples. It can use sparse annotations. "
               "A compact 2D U-Net is a later option if spatial context is still necessary; "
               "the current two same-animal masks cannot establish its performance or sample "
               "requirement. Structural vessel shadows are the current target, not OCTA "
               "capillary flow or CNV vessel density.", "",
               "Sources: [scikit-image ridge filters](https://scikit-image.org/docs/0.25.x/auto_examples/edges/plot_ridge_filter.html); "
               "[ilastik pixel classification](https://www.ilastik.org/documentation/pixelclassification/pixelclassification).", "",
               "## Review files", ""]
    for rec in records:
        report.append(f"- [{rec['scan_id']}]({rec['scan_id']}.png)")
    report += ["", "`proposals/*_proposal.npz` are automatic proposals with explicit provenance, "
               "native-grid masks, unassessed border, raw unassisted mask and human ONH dependency. "
               "They are not labels and are not used by the training pipeline. "
               "`metrics.json`, `threshold_sweep.csv`, `threshold_transfer.json` and the cached "
               "projections preserve the quantitative audit.", "",
               "Reproduce from the project directory after activating the `octa` environment: "
               "`python code/vasculature_baseline.py`. This writes only to the pilot output directory."]
    (out / "START_HERE.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps(audit, indent=2), flush=True)


if __name__ == "__main__":
    main()
