"""Evaluation harness: predictions versus human labels, in micrometres.

Scoring convention is inherited unchanged from ``eval_variants.py`` so that
numbers produced here are directly comparable with the ones already reported in
``outputs/auto_seg_8layer_v2/REPORT.md`` and ``qc/variant_comparison.json``:

* only A-lines the human did not exclude count;
* only surfaces the human drew, marked visible, and left reliable count;
* a B-scan contributes its own **median** absolute error, and the reported
  figure is the median (and 90th percentile) **over B-scans**;
* ``gross_miss_frac`` is the fraction of B-scans whose median error exceeds
  25 um.

``selftest_baseline`` re-derives the shipped-cascade column of that JSON from
the stored ``auto_surfaces`` and asserts it matches.  If it does not, the
harness is wrong, not the baseline.

Layer thickness is scored separately, because two boundaries can both move and
leave the layer correct.  Strata: acquisition QC group (from
``outputs/eight_surface/qc_review_groups.csv``) and control vs CNV.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from eight_surface.config import ANALYSIS_LAYER_DEFS, LAYER_DEFS, SURFACE_NAMES

from .folds import animal_of
from .targets import IDX, layer_supervised, surface_supervised, column_supervised

GROSS_MISS_UM = 25.0
MIN_GOOD_ALINES = 20
# A day label that is not a post-laser time point: no CNV has been induced yet.
CONTROL_DAY_LABELS = {"wt", "before laser", "beforelaser", "d0", "baseline"}


# ---------------------------------------------------------------- strata ----

def load_qc_groups(path) -> dict:
    """``{scan_id: quality_group}`` from the acquisition-QC review table."""
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return {r["scan_id"]: r["quality_group"] for r in rows}


def load_day_labels(path) -> dict:
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return {r["scan_id"]: r["day_label"] for r in rows}


def lesion_group(scan_id: str, day_labels: dict | None = None) -> str:
    """``control`` for WT and pre-laser scans, ``cnv`` for post-laser ones.

    A pre-laser acquisition of an animal that is later lasered is a control
    acquisition; the animal's eventual fate is not a property of the image.
    """
    label = (day_labels or {}).get(scan_id)
    if label is None:
        parts = str(scan_id).split("_")
        label = parts[3] if len(parts) > 3 else ""
    key = str(label).strip().lower().replace(" ", "")
    if key in {k.replace(" ", "") for k in CONTROL_DAY_LABELS}:
        return "control"
    return "cnv"


# --------------------------------------------------------------- scoring ----

def identity_predictions(records) -> dict:
    """Mock predictor returning the human answer: the harness must score 0."""
    return {(r["scan_id"], int(r["bscan"])): np.asarray(r["surfaces"], float)
            for r in records}


def stored_auto_predictions(records) -> dict:
    """Mock predictor returning the shipped cascade's stored output."""
    return {(r["scan_id"], int(r["bscan"])): np.asarray(r["auto_surfaces"], float)
            for r in records}


def surface_errors(record, predicted) -> dict:
    """Per-surface signed error in um for one B-scan, over usable A-lines.

    ``predicted`` is ``[8, A-line]`` in **original image coordinates**.
    Returns ``{surface: array}`` for supervised surfaces only.
    """
    predicted = np.asarray(predicted, float)
    human = np.asarray(record["surfaces"], float)
    if predicted.shape != human.shape:
        raise AssertionError(
            f"{record['scan_id']} b{record['bscan']}: prediction {predicted.shape} "
            f"does not match label {human.shape}")
    good = column_supervised(record)
    if good.sum() < MIN_GOOD_ALINES:
        return {}
    supervised = surface_supervised(record)
    out = {}
    for name in SURFACE_NAMES:
        k = IDX[name]
        if not supervised[k]:
            continue
        out[name] = (predicted[k] - human[k])[good] * record["px_um"]
    return out


def layer_errors(record, predicted) -> dict:
    """Per-layer signed thickness error in um for one B-scan."""
    predicted = np.asarray(predicted, float)
    human = np.asarray(record["surfaces"], float)
    good = column_supervised(record)
    if good.sum() < MIN_GOOD_ALINES:
        return {}
    usable = layer_supervised(record)
    out = {}
    for name, top, bottom in LAYER_DEFS:
        if name == "TOTAL":
            ok = surface_supervised(record)[IDX[top]] and \
                surface_supervised(record)[IDX[bottom]]
        else:
            ok = usable[name]
        if not ok:
            continue
        p = predicted[IDX[bottom]] - predicted[IDX[top]]
        h = human[IDX[bottom]] - human[IDX[top]]
        out[name] = ((p - h)[good] * record["px_um"])
    return out


def collect(records, predictions, use_stored_auto: bool = False,
            qc_groups=None, day_labels=None) -> list[dict]:
    """One row per (B-scan, surface) and (B-scan, layer), with strata attached.

    ``predictions`` maps ``(scan_id, bscan)`` to ``[8, A-line]`` rows in
    original image coordinates.  ``use_stored_auto`` scores the shipped
    cascade's own output stored in the label file, which needs no re-run.
    """
    qc_groups = qc_groups or {}
    rows = []
    for record in records:
        key = (record["scan_id"], int(record["bscan"]))
        predicted = (record["auto_surfaces"] if use_stored_auto
                     else predictions.get(key))
        if predicted is None:
            continue
        common = {
            "scan_id": record["scan_id"], "bscan": int(record["bscan"]),
            "animal": animal_of(record["scan_id"]),
            "qc_group": qc_groups.get(record["scan_id"], "unknown"),
            "lesion_group": lesion_group(record["scan_id"], day_labels),
        }
        for name, delta in surface_errors(record, predicted).items():
            rows.append({**common, "kind": "surface", "name": name,
                         "median_abs": float(np.median(np.abs(delta))),
                         "median_signed": float(np.median(delta))})
        for name, delta in layer_errors(record, predicted).items():
            rows.append({**common, "kind": "layer", "name": name,
                         "median_abs": float(np.median(np.abs(delta))),
                         "median_signed": float(np.median(delta))})
    return rows


def summarise(rows, kind: str = "surface", names=None) -> dict:
    """Median / p90 / signed / gross-miss over B-scans, per name."""
    names = names or (SURFACE_NAMES if kind == "surface"
                      else [n for n, _, _ in ANALYSIS_LAYER_DEFS] + ["TOTAL"])
    by_name = defaultdict(list)
    for row in rows:
        if row["kind"] == kind:
            by_name[row["name"]].append(row)
    out = {}
    for name in names:
        group = by_name.get(name) or []
        if not group:
            continue
        abs_values = np.array([r["median_abs"] for r in group])
        signed = np.array([r["median_signed"] for r in group])
        out[name] = {
            "n_bscans": len(group),
            "median_abs_um": float(np.median(abs_values)),
            "p90_abs_um": float(np.percentile(abs_values, 90)),
            "median_signed_um": float(np.median(signed)),
            "gross_miss_frac": float(np.mean(abs_values > GROSS_MISS_UM)),
        }
    return out


def summarise_by(rows, key: str, kind: str = "surface") -> dict:
    """``{stratum: summary}`` -- the same summary within each group."""
    groups = sorted({row[key] for row in rows})
    return {group: summarise([r for r in rows if r[key] == group], kind=kind)
            for group in groups}


def print_table(title: str, summary: dict) -> None:
    print(f"\n{title}")
    print(f"  {'name':14s} {'medAbs um':>10s} {'p90Abs':>8s} {'signed':>8s} "
          f"{'>25um':>7s} {'n':>4s}")
    for name, s in summary.items():
        print(f"  {name:14s} {s['median_abs_um']:10.1f} {s['p90_abs_um']:8.1f} "
              f"{s['median_signed_um']:+8.1f} {s['gross_miss_frac']:7.2f} "
              f"{s['n_bscans']:4d}")


def write_rows(rows, path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


# -------------------------------------------------------------- self-test ----

def compare_to_reference(summary: dict, reference: dict, tol: float = 1e-9):
    """Field-by-field comparison against a published summary block."""
    problems = []
    keys = ("n_bscans", "median_abs_um", "p90_abs_um", "median_signed_um",
            "gross_miss_frac")
    for name, expected in reference.items():
        if name.startswith("_"):
            continue
        got = summary.get(name)
        if got is None:
            problems.append(f"{name}: missing from harness output")
            continue
        for key in keys:
            a, b = float(got[key]), float(expected[key])
            if abs(a - b) > tol * max(1.0, abs(b)):
                problems.append(f"{name}.{key}: harness {a!r} != reported {b!r}")
    extra = sorted(set(summary) - {k for k in reference if not k.startswith("_")})
    if extra:
        problems.append(f"surfaces scored here but absent from the reference: {extra}")
    return problems


def selftest_baseline(records, reference_json, qc_groups=None, day_labels=None,
                      block: str = "baseline_shipped_cascade", tol: float = 1e-9):
    """Reproduce a published block of ``variant_comparison.json``.

    The shipped-cascade block needs no segmentation run: every label file stores
    the cascade's real-pipeline output for exactly that B-scan.
    """
    reference = json.loads(Path(reference_json).read_text(encoding="utf-8"))[block]
    rows = collect(records, {}, use_stored_auto=True, qc_groups=qc_groups,
                   day_labels=day_labels)
    summary = summarise(rows, kind="surface")
    return summary, compare_to_reference(summary, reference, tol=tol), rows
