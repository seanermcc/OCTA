"""Freeze the user-authorized full manual cohort without modifying old data.

The original test allocation is historical after explicit user release. A new
dataset keeps all manual evidence, with biological scope retained as a stratum,
not a reason to reject a manually drawn boundary. Image exclusions, visibility,
reliability, displacement, and shadow remain effective. No label writer exists
in this module. The original datasets and checkpoints remain unchanged.
"""
import argparse
from collections import Counter
import copy
import datetime as dt
import json
from pathlib import Path

import numpy as np
from eight_surface.labels import load_label
from eight_surface.config import CASCADE_VERSION
from eight_surface.segment import detect_orientation, prepare_bscan
from octa.volio import ProcessedVolume
from stage_a.common import DEFAULT, OUT, fingerprint, verify, digest, output_dir, write_json, write_csv
from stage_a.geometry import PREPROCESS, preprocess, label_offset
from stage_a.partitions import validate_partition
from stage_a_inner_retina_audit import manual_valid


AUTHORIZATION = {
    "user_instruction": "Yes, use any/all of the labeled cohort as necessary. Treat those as ground truth. And continue this run until you get all the way through. When i say checkpoint i just mean provide a report and output images/files, but still continue your run",
    "former_test_animals_released": True,
    "former_test_is_no_longer_independent": True,
    "manual_truth_only": True,
    "layer_segmentation_skill_used": False,
    "checkpoint_is_not_a_stop": True,
}


def target_mask(label, shadow, height):
    valid = manual_valid(label)
    if label["verdict"] != "corrected" or label["cascade_version"] != CASCADE_VERSION:
        valid[:] = False
    rows = label["surfaces"]
    return valid & ~np.asarray(shadow, bool)[None] & (rows >= 0) & (rows <= height - 1)


def build(args):
    out = output_dir(args.out)
    if (out / "manifest.json").exists():
        raise FileExistsError("Full-cohort snapshot already frozen; choose a new version")
    old = json.loads((args.original / "manifest.json").read_text())
    old_partition = json.loads((args.original / "partitions.json").read_text())
    old_cache = json.loads((args.original / "cache_manifest.json").read_text())
    validate_partition(old, old_partition)
    verify(old_partition["manifest"])
    by_key = {r["key"]: r for r in old["records"]}
    source = copy.deepcopy(old["sources"])
    targets_dir, cache_dir = output_dir(out / "targets"), output_dir(out / "cache")
    records, entries, audit = [], {}, []
    # Start with the frozen cohort and let an explicitly supplied review folder
    # replace matching scan/B-scan decisions.  This is deliberately keyed by
    # identity rather than by filename concatenation: a second decision for a
    # B-scan supersedes the earlier one but remains traceable in the audit.
    old_label_paths = {r["key"]: Path(r["label"]["path"]) for r in old["records"]}
    selected = dict(old_label_paths)
    supplied = set()
    for folder in args.labels:
        for path in folder.glob("*.npz"):
            label = load_label(path)
            key = f"{label['scan_id']}_b{label['bscan']:04d}"
            selected[key] = path
            supplied.add(key)
    packs = {}
    for key, path in sorted(selected.items()):
        label_fp = fingerprint(path)
        label = load_label(path)
        sid, b = label["scan_id"], label["bscan"]
        if key != f"{sid}_b{b:04d}":
            raise AssertionError("Label identity changed while importing")
        if sid not in source:
            raise ValueError(f"New source volume needs geometry verification: {sid}")
        src = source[sid]
        height = src["label_band"][1] - src["label_band"][0]
        former = by_key.get(key)
        # New reviews (including an update to a previously frozen decision)
        # are mapped again from raw image coordinates.  Older frozen labels
        # retain their verified cached image identity without a needless 2 GB
        # reread per source volume.
        refresh_geometry = key in supplied
        if former and not refresh_geometry:
            verify(former["label"])
            old_entry = old_cache["entries"][key]
            verify(old_entry["file"]); verify(former["targets_fingerprint"])
            with np.load(old_entry["file"]["path"], allow_pickle=False) as d:
                x, offset, vhi, norm = d["x"], int(d["label_offset"]), bool(d["vitreous_high"]), d["norm"]
            with np.load(former["targets"], allow_pickle=False) as d:
                shadow, original_scope = d["shadow"], d["scope"]
            record = copy.deepcopy(former)
            image_provenance = {"original_cache": old_entry["file"], "original_cache_key": old_entry["cache_key"]}
        else:
            verify(src["source"])
            if sid not in packs:
                # One bulk read also derives orientation afresh; no trusted old
                # orientation flag is used to map a new manual annotation.
                with ProcessedVolume(src["source"]["path"]) as volume:
                    full = volume.read_volume()
                vhi = bool(detect_orientation(full.mean(axis=(0, 1))))
                packs[sid] = full, vhi
            full, vhi = packs[sid]
            offset = label_offset(src["label_band"], full.shape[2], vhi)
            x, db, norm = preprocess(full[b], vhi)
            # Review packs are versioned in several output folders.  Select
            # only a pack whose recorded pixels exactly match freshly decoded
            # native coordinates; do not infer orientation from stale labels.
            matches = []
            for candidate in OUT.rglob(Path(label["source_pack"]).name):
                try:
                    with np.load(candidate, allow_pickle=False) as d:
                        indices = np.flatnonzero(d["bscan_index"] == b)
                        if len(indices) == 1 and np.array_equal(db[offset:offset + height], d["images"][int(indices[0])]):
                            matches.append(candidate)
                except (KeyError, OSError, ValueError):
                    continue
            if not matches:
                raise ValueError(f"New manual label has no pixel-aligned source pack: {key}")
            pack_path = sorted(matches, key=lambda p: str(p))[0]
            pack_fp = fingerprint(pack_path)
            with np.load(pack_path, allow_pickle=False) as d:
                i = int(np.flatnonzero(d["bscan_index"] == b)[0]); shadow = d["shadow"][i]
            with np.load(src["scope_path"], allow_pickle=False) as d:
                original_scope = d["allowed"][b]
            record = dict(key=key, scan_id=sid, bscan=b, animal=src["metadata"]["animal"],
                px_um=label["px_um"], qc_group=src["qc_group"], scope_status=src["scope_status"],
                biological_group=src["biological_group"])
            image_provenance = dict(source=src["source"], pack=pack_fp, pack_pixels_exact=True)
        valid = target_mask(label, shadow, height)
        target = targets_dir / f"{key}.npz"
        np.savez_compressed(target, rows_label=label["surfaces"].astype(np.float32),
            stored_auto=label["auto_surfaces"].astype(np.float32), valid=valid,
            reason_bits=(~valid).astype(np.uint16), scope=np.ones(len(shadow), bool),
            original_stage_a_scope=original_scope, shadow=shadow)
        target_fp = fingerprint(target)
        rows = label["surfaces"].astype(np.float32) + offset
        if np.any(valid & ((rows < 0) | (rows >= x.shape[1]) | ~np.isfinite(rows))):
            raise ValueError("Manual target escapes native image")
        identity = dict(label=label_fp, targets=target_fp, preprocessing=PREPROCESS,
            image_provenance=image_provenance, manual_policy="direct strokes; legacy edited surfaces only; no automatic target")
        cache_key = digest(identity)
        cached = cache_dir / f"{key}_{cache_key[:16]}.npz"
        np.savez_compressed(cached, x=x, rows=rows, valid=valid,
            label_offset=np.array(offset), vitreous_high=np.array(vhi), norm=np.array(norm), cache_key=np.array(cache_key))
        entries[key] = dict(file=fingerprint(cached), identity=identity, cache_key=cache_key,
            label_offset=offset, shape=list(x.shape), pack_pixels_exact=True, eligible_targets_contained=True)
        record.update(verdict=label["verdict"], label=label_fp, targets=str(target), targets_fingerprint=target_fp,
            eligible_columns_by_surface=valid.sum(1).astype(int).tolist(), eligible=bool(valid.any()),
            local_provenance_available=bool(label.get("local_provenance_available")),
            legacy_provenance="exact_local_strokes" if label.get("local_provenance_available") else "surface_wide_edit_only_local_strokes_unknown",
            original_stage_a_eligible=bool(former and former["eligible"]),
            seconds_active=label.get("seconds_active"), n_strokes=label.get("n_strokes"),
            source_decision="new_review" if key in supplied else "frozen_original")
        record.pop("reason_counts", None)
        records.append(record)
        audit.append(dict(key=key, animal=record["animal"], verdict=label["verdict"], source_decision=record["source_decision"],
            manual_inner_columns=int(valid[:4].sum()), manual_all_columns=int(valid.sum()),
            original_scope_inner_columns=int((valid[:4] & original_scope).sum()),
            local_stroke_provenance=record["local_provenance_available"],
            former_partition=next((s for s,v in old_partition["animals"].items() if record["animal"] in v), "new")))
        verify(label_fp)
    census = dict(created=dt.datetime.now().astimezone().isoformat(), completed=len(records),
        verdicts=dict(Counter(r["verdict"] for r in records)),
        corrected_by_animal=dict(Counter(r["animal"] for r in records if r["verdict"] == "corrected")),
        eligible_by_animal=dict(Counter(r["animal"] for r in records if r["eligible"])), failures=[])
    manifest = dict(version="full-manual-cohort-20260909", contract=old["contract"],
        surface_names=old["surface_names"], sources=source, records=records, census=census,
        authorization=AUTHORIZATION, original_manifest=fingerprint(args.original / "manifest.json"),
        scope_policy="All manual segmentation evidence regardless of footprint status. Original remote/control scope is retained for stratified evaluation. No within-lesion generalization claim.",
        mask_policy="Only corrected manual positions, exact local drawn provenance where present, legacy edit flags otherwise, excluding displaced/invisible/unreliable/image-excluded/outside-image/shadow columns.")
    manifest["dataset_id"] = digest(manifest)
    write_json(out / "manifest.json", manifest)
    # Train/validation are storage buckets for existing loaders. CV excludes a
    # whole animal and a distinct calibrator afresh. No independent test remains.
    members = {"train": sorted(set(r["animal"] for r in records) - set(old_partition["animals"]["validation"])),
               "validation": old_partition["animals"]["validation"], "test": []}
    partition = dict(dataset_id=manifest["dataset_id"], manifest=fingerprint(out / "manifest.json"),
        animals=members, keys={s: sorted(r["key"] for r in records if r["animal"] in animals) for s,animals in members.items()},
        final_test_locked=False, authorization=AUTHORIZATION,
        rationale="User authorized the whole labeled cohort. Original allocations remain frozen elsewhere. All performance claims here require animal-excluded development cross-validation.")
    partition["partition_id"] = digest(partition)
    validate_partition(manifest, partition)
    write_json(out / "partitions.json", partition)
    write_json(out / "cache_manifest.json", dict(dataset_id=manifest["dataset_id"], preprocessing=PREPROCESS,
        entries=entries, missing=[], failures={}))
    write_json(out / "census.json", census)
    write_csv(out / "manual_evidence_audit.csv", audit)
    write_json(out / "authorization.json", AUTHORIZATION)
    print(json.dumps(census, indent=2), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original", type=Path, default=DEFAULT)
    p.add_argument("--labels", type=Path, nargs="+", default=[],
                   help="One or more review-label folders; decisions replace frozen records by scan/B-scan identity")
    p.add_argument("--out", type=Path, required=True)
    build(p.parse_args())
