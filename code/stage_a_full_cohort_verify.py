"""Read-only full-cohort identity, model-role and GUI-pack verification.

Run modes in separate processes to avoid the Windows torch/GUI OpenMP conflict.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from stage_a.common import fingerprint, verify, digest, write_json


def run(args):
    root = args.out
    manifest = json.loads((root / "data/manifest.json").read_text())
    if args.mode == "folds-ready":
        import torch
        cv = root / "cv_full_cohort"
        protocol = json.loads((cv / "protocol.json").read_text())
        fps = []
        for fold in protocol["folds"]:
            path = cv / fold["held_animal"] / "last.pt"
            ck = torch.load(path, map_location="cpu", weights_only=True)
            if (ck["epoch"] != protocol["epochs"] or ck["protocol_digest"] != digest(protocol)
                    or ck["identity"] != protocol["dataset_identity"]
                    or any(ck["config"].get(k) != v for k,v in fold.items())
                    or set(fold["training_animals"]) & {fold["held_animal"], fold["calibration_animal"]}):
                raise AssertionError("An evaluation fold is incomplete or contains animal leakage")
            fps.append(fingerprint(path))
        write_json(cv / "fold_evaluation_ready.json", dict(protocol_digest=digest(protocol),
            evaluation_folds=len(fps), checkpoints=fps,
            scope="Only independent evaluation folds are complete. This marker does not claim all-label training is complete."))
        print("All nine independent folds verified; calibration may proceed while all-label training continues")
        return
    elif args.mode == "inputs":
        from stage_a.partitions import validate_partition
        partition = json.loads((root / "data/partitions.json").read_text())
        validate_partition(manifest, partition)
        verify(partition["manifest"])
        if not partition["authorization"]["former_test_animals_released"] or partition["animals"]["test"]:
            raise AssertionError("Full-cohort release and partition disagree")
        cache = json.loads((root / "data/cache_manifest.json").read_text())
        for r in manifest["records"]:
            verify(r["label"]); verify(r["targets_fingerprint"]); verify(cache["entries"][r["key"]]["file"])
        verify(manifest["original_manifest"])
        original_path = Path(manifest["original_manifest"]["path"])
        old = json.loads(original_path.read_text())
        old_cache = json.loads((original_path.parent / "cache_manifest.json").read_text())
        for r in old["records"]:
            verify(r["label"]); verify(r["targets_fingerprint"]); verify(old_cache["entries"][r["key"]]["file"])
        result = dict(new_snapshot_records=len(manifest["records"]), unchanged_original_records=len(old["records"]),
            corrected_manual_bscans=sum(r["verdict"] == "corrected" for r in manifest["records"]),
            labels_unchanged=True, targets_and_caches_unchanged=True, original_manifest_unchanged=True,
            former_test_access_explicitly_authorized=True, untouched_final_test_estimate_claimed=False)
    elif args.mode == "models":
        import torch
        from stage_a.train import code_identity
        from stage_a.data import Dataset
        from stage_a_inner_cv import verify_completed
        from stage_a_inner_train import implementation_identity
        cv = root / "cv_full_cohort"
        protocol = json.loads((cv / "protocol.json").read_text())
        archive = root / "source_used/cv_training_source.py"
        if digest([implementation_identity(), archive.read_text(encoding="utf-8")]) != protocol["code_identity"]:
            raise AssertionError("Archived training source does not match the trained protocol")
        data = Dataset(root / "data", "train")
        if protocol["dataset_identity"] != data.identity:
            raise AssertionError("Training dataset identity changed")
        paths = list(cv.glob("*/last.pt"))
        before = [fingerprint(p) for p in paths]
        if not verify_completed(cv, protocol, 9): raise AssertionError("Training is incomplete")
        for fp in before: verify(fp)
        manual_animals = {r["animal"] for r in manifest["records"] if r["eligible"]}
        for fold in protocol["folds"]:
            train = set(fold["training_animals"])
            if (train != manual_animals - {fold["held_animal"], fold["calibration_animal"]}
                    or len(train) != 7 or fold["held_animal"] == fold["calibration_animal"]):
                raise AssertionError("Training/calibration/evaluation animal leakage")
        if set(protocol["all_labels_model"]["training_animals"]) != manual_animals:
            raise AssertionError("All-label model omitted a supported animal")
        for method in ("dp", "soft"):
            calibration = json.loads((root / f"calibration_{method}/calibration_summary.json").read_text())
            if "ALL_LABELLED" in calibration["checkpoints"] or len(calibration["checkpoints"]) != 9:
                raise AssertionError("All-label model entered independent calibration")
            for fp in calibration["checkpoints"].values(): verify(fp)
        original = Path("outputs/stage_a/20260908_v4_longtrain/dev_seed20260908/best.pt")
        if fingerprint(original)["sha256"] != "855397f3d77fbce2246e619ba9b06efb6339ef56ca0127dce4b14f6a9a3c9cbd":
            raise AssertionError("Original v4 model changed")
        old = torch.load(original, map_location="cpu", weights_only=True)
        if old["code_identity"] != code_identity():
            raise AssertionError("Original core Stage A resume identity changed")
        result = dict(models=before, nine_folds_animal_disjoint=True, all_label_model_separate=True,
            completed_resume_did_not_rewrite_exports=True, original_v4_model_unchanged=True,
            original_stage_a_code_guard_passes=True, archived_training_source_matches=True,
            training_budget=protocol["epochs"]*protocol["steps_per_epoch"])
    elif args.mode == "packs":
        from eight_surface.label_gui import Pack
        from unittest.mock import patch
        packs = []
        for path in sorted((root / "review_queue/packs").glob("*_pack.npz")):
            with patch("eight_surface.labels.save_label", side_effect=AssertionError("No label writes allowed")):
                pack = Pack(path, Path("outputs/eight_surface/labels"))
            if pack.n_preloaded or any(s.verdict is not None or s.edited.any() for s in pack.states):
                raise AssertionError("Review candidate is already reviewed or edited")
            packs.append(dict(file=fingerprint(path), bscans=pack.n, all_undecided=True, n_preloaded=0))
        summaries = json.loads((root / "review_queue/queue_summary.json").read_text())
        if len(packs) != 4 or sum(p["bscans"] for p in packs) != 36:
            raise AssertionError("Incomplete planned review packs")
        for v in summaries["volumes"]:
            with np.load(root / "review_queue" / v["scan_id"] / "experimental_measurements.npz", allow_pickle=False) as d:
                maps, shadow = d["experimental_thickness_um"], d["shadow"]
                if np.isfinite(maps.transpose(0, 2, 1)[shadow]).any():
                    raise AssertionError("Shadowed thickness must remain NaN")
                if np.any(np.diff(d["canonical_rows"], axis=1) < 0):
                    raise AssertionError("Constrained volume surfaces cross")
        result = dict(packs=packs, label_writer_disabled_during_check=True,
            shadow_thickness_all_nan=True, full_volumes_crossing_free=True)
    else:
        checks = {mode: json.loads((root / f"verification_{mode}.json").read_text()) for mode in ("inputs", "models", "packs")}
        write_json(root / "verification_complete.json", dict(passed=True, checks=checks,
            limits="Implementation/data/protocol checks do not establish deployment accuracy. Model precision is BF16 during training and FP32 during inference."))
        print(root / "verification_complete.json")
        return
    write_json(root / f"verification_{args.mode}.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--mode", choices=("inputs", "models", "packs", "complete", "folds-ready"), required=True)
    run(p.parse_args())
