"""Reproducible manual-evidence audit for the Tier 1 prompt's prerequisite gate.

Only development animal labels are opened. No published anatomical values,
automatic surfaces as targets, or locked final-test targets are used. Stored
automatic surfaces are a predictor in the offset experiment, never truth.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

import numpy as np

from auto_seg_8layer_v2.unet.targets import column_valid
from eight_surface.labels import load_label
from stage_a.common import DEFAULT, OUT, fingerprint, output_dir, verify, write_csv, write_json
from stage_a.partitions import validate_partition

EXPECTED = {"corrected_bscans": 101, "volumes": 27, "animals": 9,
            "lesion_bscans": 7, "lesion_columns_approx": 170}
EXPECTED_SPREAD = {"RNFL_GCL": {"PR_RPE": 41.8, "IPL_INL": 30.1},
                   "GCL_IPL": {"PR_RPE": 40.1, "IPL_INL": 25.8}}
EXPECTED_ORACLE = {"RNFL_GCL": {"bscan": 17.8, "volume": 24.5},
                   "GCL_IPL": {"bscan": 15.2, "volume": 22.6}}


def manual_valid(label):
    valid = column_valid(label, legacy_policy="surface_flag").copy()
    if not label.get("local_provenance_available", False):
        # The shared legacy helper honours edited flags but cannot distinguish
        # an edited line that ordering later moved. Exclude that whole surface
        # when no local displacement history exists, as frozen Stage A does.
        valid[np.asarray(label["surface_displaced"], bool)] = False
    return valid & np.isfinite(label["surfaces"])


def permitted_records(manifest, partitions):
    """Partition metadata may be audited; test label/target files may not be opened."""
    validate_partition(manifest, partitions)
    allowed = set(partitions["animals"]["train"] + partitions["animals"]["validation"])
    locked = set(partitions["animals"]["test"])
    if allowed & locked:
        raise ValueError("Animal leakage in partition")
    return [r for r in manifest["records"] if r["animal"] in allowed and r["verdict"] == "corrected"]


def spread_parts(records, surface, anchor, matched=False):
    """A positional observation needs manual evidence at BOTH anchors and target."""
    parts = []
    for r, label, valid in records:
        s = np.asarray(label["surfaces"], float)
        span = s[anchor] - s[0]
        good = valid[surface] & valid[0] & valid[anchor] & (span > 40)
        if matched:
            good &= valid[3] & valid[6] & ((s[3] - s[0]) > 40) & ((s[6] - s[0]) > 40)
        if good.sum() >= 20:
            parts.append((r, s[surface, good] - s[0, good], span[good]))
    return parts


def prior_summary(parts):
    if not parts:
        return dict(n_bscans=0, n_columns=0, fraction=None, residual_p95_px=None)
    fraction = float(np.median([np.median(depth / span) for _, depth, span in parts]))
    error = np.concatenate([depth - fraction * span for _, depth, span in parts])
    return dict(n_bscans=len(parts), n_columns=len(error), fraction=fraction,
                residual_p95_px=float(np.quantile(np.abs(error), .95)))


def offset_summary(records, surface, group, predictions=None):
    grouped = defaultdict(list)
    n_eligible, n_missing = 0, 0
    for r, label, valid in records:
        prediction = label["auto_surfaces"] if predictions is None else predictions.get(r["key"])
        n_eligible += int(valid[surface].sum())
        if prediction is None:
            n_missing += int(valid[surface].sum())
            continue
        good = valid[surface] & np.isfinite(prediction[surface])
        if good.sum() >= 20:
            delta = (prediction[surface] - label["surfaces"][surface])[good]
            grouped[r["key"] if group == "bscan" else r["scan_id"]].append(delta)
    if not grouped:
        return dict(n_groups=0, n_columns=0, n_eligible=n_eligible,
                    missing_prediction_columns=n_missing, residual_p95_px=None)
    # Median offset minimises absolute loss; it is not the optimum for p95 loss.
    residuals = []
    for arrays in grouped.values():
        delta = np.concatenate(arrays)
        residuals.append(delta - np.median(delta))
    error = np.concatenate(residuals)
    return dict(n_groups=len(grouped), n_columns=len(error), n_eligible=n_eligible,
                missing_prediction_columns=n_missing,
                residual_p95_px=float(np.quantile(np.abs(error), .95)))


def run(args):
    root = Path(args.data)
    manifest = json.loads((root / "manifest.json").read_text())
    partitions = json.loads((root / "partitions.json").read_text())
    verify(partitions["manifest"])
    metadata = permitted_records(manifest, partitions)
    released = bool(partitions.get("authorization", {}).get("former_test_animals_released"))
    out = output_dir(args.out)
    if any(out.iterdir()):
        raise FileExistsError("Choose an empty output directory for the prerequisite audit")
    records = []
    for r in metadata:
        verify(r["label"])
        label = load_label(r["label"]["path"])
        if label["scan_id"] != r["scan_id"] or label["bscan"] != r["bscan"]:
            raise ValueError("Manual label identity mismatch")
        valid = manual_valid(label)
        records.append((r, label, valid))

    spreads = []
    for surface, name in ((1, "RNFL_GCL"), (2, "GCL_IPL")):
        for anchor, anchor_name in ((6, "PR_RPE"), (3, "IPL_INL")):
            for matched in (False, True):
                result = prior_summary(spread_parts(records, surface, anchor, matched))
                spreads.append(dict(surface=name, outer_anchor=anchor_name,
                    cohort="matched_manual_anchors" if matched else "available_manual_anchors",
                    expected_p95_px=EXPECTED_SPREAD[name][anchor_name], **result))
    v2, v2_fingerprints = {}, {}
    for sid in sorted({r["scan_id"] for r in metadata}):
        path = OUT / "auto_seg_8layer_v2/segmented" / f"{sid}.npz"
        if not path.exists():
            continue
        v2_fingerprints[sid] = fingerprint(path)
        with np.load(path, allow_pickle=False) as d:
            if (list(d["surface_names"].astype(str)) != manifest["surface_names"]
                    or list(d["retina_band"]) != manifest["sources"][sid]["label_band"]):
                raise ValueError("Classical v2/manual label geometry mismatch")
            surfaces = d["surfaces"]
            for r in metadata:
                if r["scan_id"] == sid:
                    v2[r["key"]] = surfaces[r["bscan"]].copy()
        verify(v2_fingerprints[sid])
    offsets = []
    for predictor, predictions in (("stored_auto", None), ("stored_v2", v2)):
        for surface, name in ((1, "RNFL_GCL"), (2, "GCL_IPL")):
            for group in ("bscan", "volume"):
                offsets.append(dict(predictor=predictor, surface=name, offset_group=group,
                    expected_p95_px=EXPECTED_ORACLE[name][group],
                    **offset_summary(records, surface, group, predictions)))

    lesions, scope_fingerprints = [], {}
    scope_cache = {}
    for r, label, valid in records:
        sid = r["scan_id"]
        src = manifest["sources"][sid]
        if sid not in scope_cache:
            verify(src["scope_hash"])
            scope_fingerprints[sid] = src["scope_hash"]
            with np.load(src["scope_path"], allow_pickle=False) as d:
                scope_cache[sid] = d["signed_distance_um"] < 0
        mask = scope_cache[sid][r["bscan"]]
        if mask.any():
            lesions.append(dict(key=r["key"], animal=r["animal"],
                footprint_columns=int(mask.sum()),
                nonexcluded_footprint_columns=int((mask & ~label["region_excluded"]).sum()),
                manual_any_surface_columns=int((mask & valid.any(axis=0)).sum()),
                manual_all_inner_columns=int((mask & valid[:4].all(axis=0)).sum())))

    actual = dict(corrected_bscans=len(records), volumes=len({r["scan_id"] for r in metadata}),
                  animals=len({r["animal"] for r in metadata}), lesion_bscans=len(lesions),
                  lesion_columns=sum(r["footprint_columns"] for r in lesions))
    same_cohort = all(actual[k] == EXPECTED[k] for k in ("corrected_bscans", "volumes", "animals"))
    gate = dict(status="full_user_authorized_cohort_audited" if released else "development_cohort_audited",
        may_start_dependent_experiments=True, exact_brief_cohort_reproduced=same_cohort,
        reason=("The user explicitly released all labeled animals into development. All available corrected labels are audited; new manual annotations may increase the original 101-label count. Checkpointing does not pause execution."
            if released else "The prompt's 101-label/9-animal cohort is not available without accessing the locked "
                "final-test partition. Development-only measurements are a different cohort, not an exact reproduction. "
                "The user directed checkpoint-and-continue on the permitted cohort; no additional cohort choice is pending. "
                "No manual-evidence rule or partition is weakened to match the quoted numbers."),
        expected=EXPECTED, actual=actual,
        corrected_bscans_by_animal=dict(sorted(Counter(r["animal"] for r in metadata).items())),
        locked_animals=partitions["animals"]["test"], locked_files_opened=0,
        former_test_animals_released=released,
        local_provenance_bscans=sum(bool(l.get("local_provenance_available")) for _, l, _ in records),
        manual_truth_only=True, published_values_used=False, production_parameters_changed=False)
    for r, _, _ in records:
        verify(r["label"])
    write_csv(out / "prior_spread.csv", spreads)
    write_csv(out / "oracle_offsets.csv", offsets)
    write_csv(out / "lesion_support.csv", lesions)
    if released and "original_manifest" in manifest:
        verify(manifest["original_manifest"])
        original = json.loads(Path(manifest["original_manifest"]["path"]).read_text())
        keys = {r["key"] for r in original["records"] if r["verdict"] == "corrected"}
        historical = [item for item in records if item[0]["key"] in keys]
        historic_spread = []
        for k, name in ((1, "RNFL_GCL"), (2, "GCL_IPL")):
            for a, anchor_name in ((6, "PR_RPE"), (3, "IPL_INL")):
                for matched in (False, True):
                    historic_spread.append(dict(surface=name, outer_anchor=anchor_name,
                        cohort="matched_manual_anchors" if matched else "available_manual_anchors",
                        **prior_summary(spread_parts(historical, k, a, matched))))
        write_csv(out / "historical_101_prior_spread.csv", historic_spread)
        write_json(out / "historical_101_cohort.json", dict(corrected_bscans=len(historical),
            volumes=len({r["scan_id"] for r, _, _ in historical}), animals=len({r["animal"] for r, _, _ in historical}),
            former_test_included_with_user_authorization=True))
    write_json(out / "prerequisite_gate.json", gate)
    write_json(out / "audit_provenance.json", dict(dataset_id=manifest["dataset_id"],
        partition_id=partitions["partition_id"], labels=[r["label"] for r in metadata],
        scope_files=scope_fingerprints, classical_v2_files=v2_fingerprints, script=fingerprint(__file__),
        manual_policy=("column_valid(surface_flag): direct drawn provenance where recorded; "
                       "legacy surface-wide edit approximation otherwise, with every legacy displaced surface excluded; "
                       "both anchors must independently qualify. "
                       "No Stage A footprint-buffer or automatic-shadow restriction on the manual descriptive audit."),
        spread_estimator="Median of per-B-scan median fractions; pooled p95 absolute positional residual, >=20 columns, span>40 px.",
        offset_estimator="Subtract median automatic-minus-manual offset per B-scan or volume; pooled p95 absolute residual. Descriptive oracle, not held-out performance or p95-optimal offset.",
        lesion_estimator="Negative signed distance from the frozen manual-footprint-derived scope artifact; footprint columns are distinct A-lines, not summed surfaces.",
        legacy_limitation="A surface-wide edit flag does not recover the unrecorded location of individual manual strokes."))
    print(json.dumps(gate, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT)
    parser.add_argument("--out", type=Path, required=True)
    run(parser.parse_args())
