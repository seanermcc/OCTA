"""Controlled inner-band prior experiment with fixed automatic endpoint estimates.

Only RNFL_GCL/GCL_IPL are refit, as fractions of ILM->IPL_INL. The inner-band
solver never reads PR_RPE. The unchanged endpoint provider is the existing v2
pipeline and therefore still has an indirect outer-anchor dependency. This
limitation is explicit; this is not claimed to be an end-to-end outer-free model.
"""
from collections import defaultdict
import json
from pathlib import Path
import time

import numpy as np

from octa.volio import ProcessedVolume, find_retina_band
from octa.surfaces import dp_surface, median_filter1d
from octa.segment import _interp_over
from eight_surface.segment import prepare_bscan, detect_orientation, build_costs
from eight_surface.volume import average_bscans
from eight_surface.config import SURFACE_COST
from eight_surface.labels import load_label
from stage_a.common import DEFAULT, output_dir, verify, write_json, write_csv, digest
from stage_a.geometry import label_offset
from stage_a_inner_retina_audit import permitted_records, manual_valid, spread_parts, prior_summary
from stage_a_inner_retina import evaluate, sensitivity
from .volume_v2 import segment_volume


def solve_inner(images, anchors, fractions, shadow, attract=.05):
    """Pure inner path: images, ILM/IPL_INL endpoints, two fractions and shadow."""
    n_b, _, width = images.shape
    costs = [build_costs(img) for img in images]
    result = np.empty((n_b, 4, width), np.float32)
    result[:, 0], result[:, 3] = anchors[:, 0], anchors[:, 1]

    def ordered(a, b, ilm, end):
        first = np.clip(a, ilm + 2, end - 4)
        second = np.clip(b, first + 2, end - 2)
        invalid = ~np.isfinite(ilm + end) | (end - ilm < 6)
        first[invalid] = np.nan; second[invalid] = np.nan
        return first, second

    for b in range(n_b):
        ilm, end = anchors[b]
        span = end - ilm
        centres = [ilm, ilm + fractions[0] * span, ilm + fractions[1] * span, end]
        found = []
        prev = ilm + 3
        for k, name in enumerate(("RNFL_GCL", "GCL_IPL"), 1):
            half = np.minimum(.4 * (centres[k] - centres[k - 1]),
                              .4 * (centres[k + 1] - centres[k]))
            half = np.clip(half, 3, np.maximum(3, .07 * span))
            low = np.maximum(centres[k] - half, prev + 2)
            high = np.maximum(np.minimum(centres[k] + half, end - 2), low + 3)
            line = dp_surface(costs[b][SURFACE_COST[name]], max_step=2, lo=low, hi=high).astype(float)
            line = median_filter1d(_interp_over(shadow[b], line), 15)
            found.append(line)
            prev = line
        result[b, 1], result[b, 2] = ordered(*found, ilm, end)
    # Match the real pipeline's five-B-scan soft refinement, preserving endpoints.
    prior = np.stack([median_filter1d(result[:, k].T.astype(float), 5).T for k in (1, 2)], axis=1)
    for b in range(n_b):
        found = []
        for k, name in enumerate(("RNFL_GCL", "GCL_IPL")):
            line = dp_surface(costs[b][SURFACE_COST[name]], max_step=2,
                              lo=prior[b, k], hi=prior[b, k] + 1., bound_weight=attract).astype(float)
            found.append(line)
        result[b, 1], result[b, 2] = ordered(*found, *anchors[b])
    return result


def run(args):
    root = Path(args.data)
    m = json.loads((root / "manifest.json").read_text())
    p = json.loads((root / "partitions.json").read_text())
    verify(p["manifest"])
    metadata = permitted_records(m, p)
    records = []
    for r in metadata:
        verify(r["label"])
        lab = load_label(r["label"]["path"])
        records.append((r, lab, manual_valid(lab)))
    out = output_dir(args.out)
    by_scan = defaultdict(list)
    for r in metadata:
        by_scan[r["scan_id"]].append(r)
    priors, predictions, baseline, targets = {}, {}, {}, {}
    for animal in sorted({r["animal"] for r in metadata}):
        training = [item for item in records if not args.loao or item[0]["animal"] != animal]
        fitted = [prior_summary(spread_parts(training, k, 3)) for k in (1, 2)]
        fractions = [f["fraction"] for f in fitted]
        if any(f is None for f in fractions) or not 0 < fractions[0] < fractions[1] < 1:
            raise ValueError("Insufficient or unordered manual inner-band priors")
        priors[animal] = dict(fractions=fractions, observations=fitted,
                             training_animals=sorted({r["animal"] for r, _, _ in training}))
    started = time.monotonic()
    for number, (sid, scan_records) in enumerate(sorted(by_scan.items()), 1):
        src = m["sources"][sid]
        animal = scan_records[0]["animal"]
        config = dict(source=src["source"], priors=priors[animal], bscan_avg=3, attract=.05,
                      implementation=digest(Path(__file__).read_text(encoding="utf-8")),
                      endpoints="unchanged_full_v2_provider", loao=bool(args.loao))
        job_id = digest(config)
        saved = out / f"{sid}_predictions.npz"
        if saved.exists():
            with np.load(saved, allow_pickle=False) as d:
                if str(d["job_id"]) != job_id:
                    raise ValueError("Stored classical experiment configuration changed")
                raw, candidate, shadows, bscans = d["baseline"], d["candidate"], d["shadow"], d["bscans"]
        else:
            verify(src["source"])
            with ProcessedVolume(src["source"]["path"]) as volume:
                full = volume.read_volume(channel="struct")
            profile = full.mean(axis=(0, 1))
            lo, hi, _ = find_retina_band(profile)
            vhi = detect_orientation(profile)
            band = full[:, :, lo:hi]
            offset = label_offset([lo, hi], full.shape[2], vhi) - label_offset(src["label_band"], full.shape[2], vhi)
            raw, candidate, shadows, bscans = [], [], [], []
            for r in scan_records:
                b = r["bscan"]
                start, end = max(0, b - 6), min(len(band), b + 7)
                slab = band[start:end]
                original, _, shadow, _ = segment_volume(slab, vhi, bscan_avg=3,
                    refine=True, smooth_bscans=5, attract=.05, progress=False)
                images = average_bscans(np.stack([prepare_bscan(img, vhi) for img in slab]), 3)
                changed = solve_inner(images, original[:, [0, 3]], priors[animal]["fractions"], shadow)
                centre = b - start
                np.testing.assert_array_equal(changed[centre, [0, 3]], original[centre, [0, 3]])
                raw.append(original[centre, :4] + offset)
                candidate.append(changed[centre] + offset)
                shadows.append(shadow[centre]); bscans.append(b)
            raw, candidate, shadows, bscans = map(np.asarray, (raw, candidate, shadows, bscans))
            np.savez_compressed(saved, baseline=raw, candidate=candidate, shadow=shadows,
                                bscans=bscans, job_id=np.array(job_id))
            del full, band
        for r in scan_records:
            index = int(np.flatnonzero(bscans == r["bscan"])[0])
            with np.load(r["targets"], allow_pickle=False) as d:
                t = {k: d[k].copy() for k in d.files}
            targets[r["key"]] = t
            keep = np.broadcast_to(t["scope"] & ~shadows[index], (4, len(t["scope"]))).copy()
            baseline[r["key"]] = dict(rows=raw[index], retained=keep)
            predictions[r["key"]] = dict(rows=candidate[index], retained=keep)
        print(f"Classical {'LOAO' if args.loao else 'fit'} {number}/{len(by_scan)}: {sid} ({time.monotonic()-started:.1f}s)", flush=True)
    metrics = []
    for name, pred in (("fixed_v2_endpoints_original_priors", baseline), ("inner_band_two_priors", predictions)):
        for scenario, selected in sensitivity(metadata):
            report = evaluate(selected, targets, pred, m["sources"])
            metrics.extend(dict(predictor=name, sensitivity=scenario, **r) for r in report["summary"])
            write_json(out / f"{name}_{scenario}.json", report)
    write_csv(out / "metrics.csv", metrics)
    write_json(out / "experiment.json", dict(priors=priors, leave_one_animal_out=bool(args.loao),
        n_manual_bscans=len(metadata), elapsed_s=time.monotonic()-started,
        IPL_INL_refit=False, attract=.05, bscan_avg=3,
        final_test_used=bool(p.get("authorization", {}).get("former_test_animals_released")),
        outer_free_inner_solver=True, outer_free_endpoint_provider=False,
        limitation="New fractions are animal-held-out. Endpoints and shadow remain the fixed original v2 pipeline, including its prior fitting history and indirect PR_RPE dependency. This controlled experiment cannot establish an end-to-end outer-independent method.",
        production_adopted=False))
