"""Read-only verification of Tier 1 inputs, models, and actual GUI packs.

Run the modes in separate processes: this Windows environment must not load
torch and the GUI/matplotlib OpenMP runtimes in the same process.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from stage_a.common import DEFAULT, verify, fingerprint, write_json, digest


def run(args):
    root = args.out
    m = json.loads((args.data / "manifest.json").read_text())
    p = json.loads((args.data / "partitions.json").read_text())
    if args.mode == "inputs":
        from stage_a.partitions import validate_partition
        validate_partition(m, p); verify(p["manifest"])
        cache = json.loads((args.data / "cache_manifest.json").read_text())
        baseline = json.loads((root / "baseline/evaluation_meta.json").read_text())
        verify(baseline["identity"]["cache_manifest"])
        permitted = set(p["keys"]["train"] + p["keys"]["validation"])
        counts = dict(labels=0, targets=0, caches=0, baseline_predictions=0)
        for r in m["records"]:
            if r["key"] not in permitted:
                continue
            verify(r["targets_fingerprint"]); counts["targets"] += 1
            verify(cache["entries"][r["key"]]["file"]); counts["caches"] += 1
            if r["verdict"] == "corrected":
                verify(r["label"]); counts["labels"] += 1
        for fp in baseline["predictions"].values():
            verify(fp); counts["baseline_predictions"] += 1
        result = dict(unchanged=counts, dataset_id=m["dataset_id"], partition_id=p["partition_id"],
            final_test_files_opened=False, label_files_written=False)
    elif args.mode == "packs":
        from eight_surface.label_gui import Pack
        from unittest.mock import patch
        checked = []
        for path in sorted((root / "review_queue/packs").glob("*_pack.npz")):
            with patch("eight_surface.labels.save_label", side_effect=AssertionError("Label write forbidden")):
                pack = Pack(path, args.labels)
            if pack.n_preloaded or any(s.verdict is not None or s.edited.any() for s in pack.states):
                raise AssertionError("A queue candidate was already reviewed or carries an edit verdict")
            checked.append(dict(file=fingerprint(path), n_bscans=pack.n, n_preloaded=pack.n_preloaded,
                all_undecided=True, all_edited_flags_false=True))
        for directory in (root / "review_queue").iterdir():
            maps = directory / "experimental_measurements.npz"
            if maps.exists():
                with np.load(maps, allow_pickle=False) as d:
                    if np.isfinite(d["experimental_thickness_um"].transpose(0, 2, 1)[d["shadow"]]).any():
                        raise AssertionError("Shadowed thickness contains a measurement")
        result = dict(packs=checked, all_shadow_thickness_nan=True, label_writer_disabled_during_verification=True)
    else:
        import torch
        from stage_a.train import code_identity
        checkpoint = args.checkpoint
        ck = torch.load(checkpoint, map_location="cpu", weights_only=True)
        if fingerprint(checkpoint)["sha256"] != "855397f3d77fbce2246e619ba9b06efb6339ef56ca0127dce4b14f6a9a3c9cbd":
            raise AssertionError("Original v4 checkpoint changed")
        summary = json.loads((root / "four_head_seed20260908/training_summary.json").read_text())
        four = torch.load(root / "four_head_seed20260908/best.pt", map_location="cpu", weights_only=True)
        protocol = json.loads((root / "cv_seven_animals/protocol.json").read_text())
        for fold in protocol["folds"]:
            if (fold["held_animal"] in fold["training_animals"] or fold["calibration_animal"] in fold["training_animals"]
                    or fold["held_animal"] == fold["calibration_animal"]
                    or set(fold["training_animals"] + [fold["held_animal"], fold["calibration_animal"]]) & set(p["animals"]["test"])):
                raise AssertionError("Animal leakage in CV protocol")
        cv_exports = []
        if (root / "cv_seven_animals/training_complete.json").exists():
            from stage_a_inner_train import implementation_identity
            archived = root / "source_used/cv_training_source.py"
            if digest([implementation_identity(), archived.read_text(encoding="utf-8")]) != protocol["code_identity"]:
                raise AssertionError("Archived CV training source differs from the trained protocol")
            for fold in protocol["folds"]:
                path = root / "cv_seven_animals" / fold["held_animal"] / "last.pt"
                model = torch.load(path, map_location="cpu", weights_only=True)
                if (model["protocol_digest"] != digest(protocol) or model["epoch"] != protocol["epochs"]
                        or any(model["config"].get(k) != v for k, v in fold.items())):
                    raise AssertionError("CV export does not match its animal exclusion or budget")
                cv_exports.append(fingerprint(path))
            for method in ("dp", "soft"):
                calibration = root / f"calibration_{method}/calibration_summary.json"
                if calibration.exists():
                    for fp in json.loads(calibration.read_text())["checkpoints"].values():
                        verify(fp)
        result = dict(original_checkpoint=fingerprint(checkpoint), original_epoch=ck["epoch"],
            original_recorded_code_identity=ck["code_identity"], current_stage_a_code_identity=code_identity(),
            original_resume_code_guard_passes=ck["code_identity"] == code_identity(),
            four_head_best_epoch=four["epoch"], four_head_steps_completed=summary["steps"],
            four_head_checkpoint_reload_exact=summary["checkpoint_reload_exact"],
            four_head_training_bscans=len(summary["identity"]["training_keys"]),
            four_head_validation_bscans=len(summary["identity"]["validation_keys"]),
            cv_fold_roles_disjoint=True, cv_protocol_digest=digest(protocol),
            cv_completed_exports=cv_exports, final_test_used=False)
    write_json(root / f"verification_{args.mode}.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=("inputs", "packs", "models"), required=True)
    p.add_argument("--data", type=Path, default=DEFAULT)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--labels", type=Path, default=Path("outputs/eight_surface/labels"))
    p.add_argument("--checkpoint", type=Path, default=Path("outputs/stage_a/20260908_v4_longtrain/dev_seed20260908/best.pt"))
    run(p.parse_args())
