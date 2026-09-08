#!/usr/bin/env python3
"""Score candidate revision-2 settings against the human labels, honestly.

The comparison runs the **real volume pipeline** -- 3-B-scan averaging and
``attract=0.05`` slow-axis refinement -- not a single unaveraged B-scan, because
this project has already been burned once by a metric computed the cheap way.
To keep that affordable, each labelled B-scan is segmented inside a slab of
neighbouring B-scans wide enough for the averaging and the 5-B-scan slow-axis
median, and only the centre B-scan is scored.

The baseline needs no run: ``auto_surfaces`` stored in every label file is the
current shipped cascade's real-pipeline output for exactly these B-scans.

Run from ``code`` with ``octa`` activated::

    python auto_seg_8layer_v2/eval_variants.py --out ../outputs/auto_seg_8layer_v2/qc
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR))

from octa.volio import ProcessedVolume, find_retina_band  # noqa: E402

from eight_surface import labels as L  # noqa: E402
from eight_surface.config import INNER_SURFACES, RELATIVE_PRIORS, SURFACE_NAMES  # noqa: E402
from eight_surface.segment import detect_orientation  # noqa: E402

from auto_seg_8layer_v2 import segment_v2  # noqa: E402
from auto_seg_8layer_v2.fit_priors import (  # noqa: E402
    animal_of, enforce_monotone, estimate, relative_observations,
)
from auto_seg_8layer_v2.volume_v2 import segment_volume  # noqa: E402

IDX = {name: i for i, name in enumerate(SURFACE_NAMES)}
PX_UM = 1.12
SLAB_HALF = 6  # covers bscan_avg=3 and the 5-B-scan slow-axis median


def variant_priors(refit: dict[str, float], which: str) -> dict[str, float]:
    """Which of the refit inner priors a variant actually adopts."""
    out = dict(RELATIVE_PRIORS)
    if which == "shipped":
        return out
    wanted = (["RNFL_GCL", "GCL_IPL"] if which == "two" else list(INNER_SURFACES))
    for name in wanted:
        if name in refit:
            out[name] = refit[name]
    return out


def segmented_source(seg_dir: Path, scan_id: str) -> Path:
    with np.load(seg_dir / f"{scan_id}.npz", allow_pickle=False) as data:
        return Path(str(data["source"][0]))


def run_variant(records_by_scan, seg_dir: Path, priors, label: str):
    """Segment a slab around every labelled B-scan; return {(scan,b): surfaces}."""
    out = {}
    started = time.time()
    for number, (scan_id, records) in enumerate(sorted(records_by_scan.items()), 1):
        source = segmented_source(seg_dir, scan_id)
        with ProcessedVolume(source) as volume:
            full = volume.read_volume(channel="struct")
            profile = full.mean(axis=(0, 1))
            lo, hi, _stale = find_retina_band(profile)
            vitreous_at_high_index = detect_orientation(profile)
            band = full[:, :, lo:hi]
        n_b = band.shape[0]
        wanted = sorted({r["bscan"] for r in records})
        print(f"  [{label}] [{number}/{len(records_by_scan)}] {scan_id}: "
              f"{len(wanted)} labelled B-scans", flush=True)
        for bscan in wanted:
            start = max(0, bscan - SLAB_HALF)
            stop = min(n_b, bscan + SLAB_HALF + 1)
            surfaces, _conf, _shadow, _notes = segment_volume(
                band[start:stop], vitreous_at_high_index, bscan_avg=3,
                refine=True, smooth_bscans=5, px_um=PX_UM, attract=0.05,
                progress=False, prior_overrides=priors)
            out[(scan_id, bscan)] = surfaces[bscan - start].astype(float)
    print(f"  [{label}] {len(out)} B-scans in {time.time() - started:.0f}s")
    return out


def score(records, predictions, use_stored_auto: bool = False):
    """Per-surface distance to the human line, in micrometres.

    Only A-lines the human left usable count, and only surfaces the human
    actually drew, marked visible, and left reliable.
    """
    per_surface = defaultdict(list)
    for record in records:
        key = (record["scan_id"], record["bscan"])
        auto = record["auto_surfaces"] if use_stored_auto else predictions.get(key)
        if auto is None:
            continue
        good = ~record["region_excluded"]
        if good.sum() < 20:
            continue
        for name in SURFACE_NAMES:
            k = IDX[name]
            if not (record["surface_edited"][k] and record["surface_visible"][k]
                    and record["surface_reliable"][k]):
                continue
            delta = (auto[k] - record["surfaces"][k])[good] * record["px_um"]
            per_surface[name].append({
                "animal": animal_of(record["scan_id"]),
                "median_abs": float(np.median(np.abs(delta))),
                "median_signed": float(np.median(delta)),
            })
    return per_surface


def summarise(per_surface) -> dict:
    out = {}
    for name in SURFACE_NAMES:
        rows = per_surface.get(name) or []
        if not rows:
            continue
        abs_values = np.array([r["median_abs"] for r in rows])
        signed = np.array([r["median_signed"] for r in rows])
        out[name] = {
            "n_bscans": len(rows),
            "median_abs_um": float(np.median(abs_values)),
            "p90_abs_um": float(np.percentile(abs_values, 90)),
            "median_signed_um": float(np.median(signed)),
            "gross_miss_frac": float(np.mean(abs_values > 25.0)),
        }
    return out


def print_table(title: str, summary: dict) -> None:
    print(f"\n{title}")
    print(f"  {'surface':10s} {'medAbs um':>10s} {'p90Abs':>8s} "
          f"{'signed':>8s} {'>25um':>7s} {'n':>4s}")
    for name in SURFACE_NAMES:
        s = summary.get(name)
        if not s:
            continue
        print(f"  {name:10s} {s['median_abs_um']:10.1f} {s['p90_abs_um']:8.1f} "
              f"{s['median_signed_um']:+8.1f} {s['gross_miss_frac']:7.2f} "
              f"{s['n_bscans']:4d}")


def run_loao(records, by_scan, seg_dir: Path, out_dir: Path, results: dict) -> int:
    """Score every animal under priors refit from the *other* animals only.

    The five inner priors are the only thing fitted here, so this is the
    honest number: no B-scan is ever scored under a prior its own animal
    helped to choose.  The outer anchor is a fixed rule with no fitted
    parameter, so it needs no fold.
    """
    animals = sorted({animal_of(r["scan_id"]) for r in records})
    predictions = {}
    for animal in animals:
        rest = [r for r in records if animal_of(r["scan_id"]) != animal]
        observations, _skipped = relative_observations(rest)
        priors = enforce_monotone({**RELATIVE_PRIORS, **estimate(observations)})
        held = {sid: rows for sid, rows in by_scan.items()
                if animal_of(sid) == animal}
        print(f"\nfold {animal}: {len(rest)} training B-scans, "
              f"{sum(len(v) for v in held.values())} held out; priors "
              + ", ".join(f"{k}={priors[k]:.3f}" for k in INNER_SURFACES))
        predictions.update(run_variant(held, seg_dir, priors, f"loao-{animal}"))

    results["v2_outer_anchor__priors_five__leave_one_animal_out"] = summarise(
        score(records, predictions))
    print_table("LEAVE-ONE-ANIMAL-OUT (no B-scan scored under its own animal's prior)",
                results["v2_outer_anchor__priors_five__leave_one_animal_out"])
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "leave_one_animal_out.json"
    path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nwrote {path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", default="../outputs/eight_surface/labels")
    parser.add_argument("--segmented", default="../outputs/eight_surface/segmented")
    parser.add_argument("--priors", default="auto_seg_8layer_v2/priors_v2.json")
    parser.add_argument("--out", default="../outputs/auto_seg_8layer_v2/qc")
    parser.add_argument("--variants", default="two,five",
                        help="comma-separated: two, five, shipped")
    parser.add_argument("--loao", action="store_true",
                        help="leave-one-animal-out: score each animal under priors "
                             "refit without it, instead of running --variants")
    args = parser.parse_args()

    records = [r for r in L.load_labels(args.labels) if r["verdict"] == "corrected"]
    by_scan = defaultdict(list)
    for record in records:
        by_scan[record["scan_id"]].append(record)
    refit = json.loads(Path(args.priors).read_text(encoding="utf-8"))["priors"]

    results = {"baseline_shipped_cascade": summarise(score(records, {}, True))}
    print_table("BASELINE - shipped cascade (stored auto_surfaces)",
                results["baseline_shipped_cascade"])

    if args.loao:
        return run_loao(records, by_scan, Path(args.segmented), Path(args.out),
                        results)

    for which in [v.strip() for v in args.variants.split(",") if v.strip()]:
        priors = variant_priors(refit, which)
        name = f"v2_outer_anchor__priors_{which}"
        print(f"\nrunning {name}: " + ", ".join(
            f"{k}={priors[k]:.3f}" for k in INNER_SURFACES))
        predictions = run_variant(by_scan, Path(args.segmented), priors, which)
        results[name] = summarise(score(records, predictions))
        results[name]["_priors"] = {k: priors[k] for k in INNER_SURFACES}
        print_table(f"{name}", results[name])

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "variant_comparison.json"
    path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nwrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
