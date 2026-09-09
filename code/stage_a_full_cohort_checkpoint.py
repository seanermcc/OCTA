"""Package a completed full-cohort run with an image-first guide and source hashes."""
import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from stage_a.common import fingerprint, verify, write_json
from stage_a_full_cohort_report import read_rows, filtered
from stage_a_inner_progress_report import compare_table, calibration_table


def run(args):
    root = args.out.resolve()
    repo = Path(__file__).resolve().parents[1]
    status = json.loads((root / "execution_checkpoint.json").read_text())
    verification = json.loads((root / "verification_complete.json").read_text())
    if status["status"] != "complete" or not verification["passed"]:
        raise ValueError("Finish all calculations and verification before packaging")
    test_logs = sorted((root / "test_logs").glob("test_*.txt"))
    tests = []
    for path in test_logs:
        raw = path.read_bytes()
        text = raw.decode("utf-16" if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else "utf-8-sig")
        match = re.search(r"Ran (\d+) tests? in", text)
        if not match or not text.rstrip().endswith("OK"):
            raise ValueError(f"Missing passing test result: {path}")
        tests.append(dict(file=fingerprint(path), passed=int(match[1])))
    if len(tests) != 7 or sum(t["passed"] for t in tests) != 33:
        raise ValueError("Expected all seven test modules and 33 passing checks")
    queue = json.loads((root / "review_queue/queue_summary.json").read_text())
    def link(label, path):
        return f"[{label}](<{path.as_posix()}>)"
    def fig(label, path):
        return "!" + link(label, path)
    metrics = read_rows(root / "held_animal_comparison/metrics.csv")
    table = compare_table(filtered(metrics, "decoder", "soft", "full_manual_cohort"),
                          filtered(metrics, "decoder", "dp_project", "full_manual_cohort"),
                          left="Animal-excluded soft", right="Animal-excluded ordered DP")
    pack_table = ["| Volume | Complete B-scans | New candidates | Review file |", "|---|---:|---:|---|"]
    for volume in queue["volumes"]:
        path = Path(volume["pack"]["path"])
        verify(volume["pack"])
        pack_table.append(f"| {volume['scan_id']} | {volume['n_bscans']} | {len(volume['selected_bscans'])} | {link('Open pack in labeling GUI', path)} |")
    packs = "\n".join(pack_table)
    guide = ["# Completed full labeled-cohort run", "",
        "All three stages are complete. No cohort decision or approval is pending. A checkpoint means saved reports and artifacts while the run continues; this run has now finished its planned calculations.", "",
        "The run used all 102 corrected B-scans from nine animals and 27 volumes. Manual segmentation is the only ground truth. The 59 rejected decisions supplied no position targets. Unedited automatic, displaced, invisible, unreliable, excluded, and shadowed positions were excluded according to recorded provenance; older labels retain their documented surface-level provenance limitation.", "",
        "## What worked, and what did not", "",
        "The ordered decoder removed all 7,751 crossing columns in the 102 manually supported B-scans and reduced every pooled large-error tail. Median thickness errors measured on excluded animals were 3.36 µm for RNFL, 2.84 µm for GCL, and 3.46 µm for IPL. These are development cross-validation results; some per-animal errors worsened, so the strict no-regression requirement failed. The output remains experimental.", "",
        "The earlier four-head retraining experiment lost, so the eight-head network is retained with four inner boundaries reported. Classical inner-band fractions improved some errors but failed the same no-regression requirement. Replacing the learned middle boundaries with classical costs also lost. Neither classical change was adopted.", "",
        "The separate inference model trains on all nine animals. Its own training-set fit is not independent accuracy. No untouched final-test set remains after the explicitly authorized cohort release. Uncertainty transfer varied widely between animals; the queue uses a per-volume workload rule, without a universal reliability promise or a lesion-core claim.", "",
        "## See the result", "",
        "Left: manual reference. Middle: prediction from a model that excluded this animal. Right: the same model with the ordered decoder. Solid lines are predictions; dotted lines are eligible manual reference. These selected examples illustrate behavior; the complete tables include every animal and the failures.", "",
        fig("Manual and animal-excluded predictions", root / "examples_held_animal/comparison_examples.png"), "",
        link("Additional exact-stroke annotation: old, animal-excluded, and all-label predictions", root / "examples_new_manual_strokes/comparison_examples.png"), "",
        link("All-label model fit examples (in-sample only)", root / "examples_all_label_fit/comparison_examples.png"), "",
        "## Review files and model", "",
        "Four entire volumes were processed: 2,048 B-scans. Each pack contains eight priority candidates and one control, for 36 unreviewed automatic proposals. All four packs passed the actual GUI-reader check with label writing disabled. Existing manual labels were unchanged. Shadowed thickness remains NaN, and unsupported outer layers are explicitly unreliable.", "", packs, "",
        link("Review-candidate image sheet", root / "review_queue/review_examples.png"), "",
        link("All-label inference model", root / "cv_full_cohort/ALL_LABELLED/last.pt") + " · " + link("Manual-derived decoder constraints", root / "all_label_constraints/constraints.json"), "",
        "Each volume subfolder under `review_queue` contains its experimental measurement arrays. These outputs cover the four listed volumes; the 314-scan acquisition batch is outside this completed run. The model and candidate lines remain proposals for review, not accepted manual labels.", "",
        "## Reports and verification", "",
        link("Complete report, all animals, sensitivities, and calibration plots", root / "RUN_REPORT.md"), "",
        link("Phase 1: scope and model comparison", root / "PHASE_1_REPORT.md") + " · " + link("Phase 2: ordered decoder", root / "PHASE_2_REPORT.md") + " · " + link("Phase 3: calibration and review queue", root / "PHASE_3_REPORT.md"), "",
        link("Reproduction instructions", root / "REPRODUCE.md") + " · " + link("Verification results", root / "verification_complete.json") + " · " + link("Checkpoint manifest", root / "checkpoint_manifest.json"), "",
        "All 33 implementation checks passed. Input identities, excluded-animal roles, checkpoint reloads, and GUI compatibility were also verified. These checks establish implementation integrity, not deployment accuracy.", ""]
    (root / "START_HERE.md").write_text("\n".join(guide), encoding="utf-8")
    phase1 = ["# Phase 1 — complete", "",
        "Manual-only cohort audit, unchanged-v4 inner-retina baseline, and classical leave-one-animal-out comparisons are complete on the expanded cohort. The exact historical 101-label subset is reproduced, plus one new annotation. The prompt's numerical prerequisite values do not reproduce under the stated masks and estimators; the measured direction of inner-anchor conditioning does reproduce. The user's instruction authorized continuing after reporting that discrepancy.", "",
        "Four-head retraining lost in the completed earlier equal-budget experiment. Eight heads are retained with four reported; this architecture experiment was not repeated as a sweep on the expanded cohort. Both full-cohort classical controls failed strict no-regression. No production prior changed, and IPL_INL was not refit.", "",
        link("Complete measurements and provenance", root / "RUN_REPORT.md") + " · " + link("Historical equal-budget architecture experiment", root.parent / "20260909_inner_retina_tier1/PHASE_1_COMPLETE.md"), ""]
    (root / "PHASE_1_REPORT.md").write_text("\n".join(phase1), encoding="utf-8")
    phase2 = ["# Phase 2 — complete, strict acceptance failed", "",
        "The three-way comparison of the original soft decoder, ordered DP, and true joint graph cut was completed in the historical Tier 1 run. The inexpensive DP control was carried forward for nine-animal development cross-validation. Constraints are fitted from manual training-animal evidence, excluding the evaluated and calibration animals.", "",
        table, "",
        "All values are µm. Every pooled p95 includes its with/without-b0510 sensitivity. Crossings fell from 7,751/52,224 to 0/52,224, but 95 pooled/per-animal metric cells worsened across both sensitivities. The strict no-regression criterion failed; there is no production promotion.", "",
        link("All errors, coverage, and movement summaries", root / "held_animal_comparison") + " · " + link("Historical joint graph-cut comparison", root.parent / "20260909_inner_retina_tier1/PHASE_2_REPORT.md"), ""]
    (root / "PHASE_2_REPORT.md").write_text("\n".join(phase2), encoding="utf-8")
    phase3 = ["# Phase 3 — complete", "",
        "Nine separate evaluation networks each exclude an evaluated animal and a distinct calibration animal, training on the remaining seven. The separate all-label model is never used in the calibration accuracy estimate. At the 90th calibration percentile, the held-animal retained coverage and conditional p95 ranges below show the spread, including b0510 sensitivity.", "",
        calibration_table(root / "calibration_dp"), "",
        "This is small-cohort development cross-validation, not untouched final-test or lesion-core evidence. No universal 90% retained-coverage guarantee is supported. The review queue therefore uses an experimental per-volume entropy quantile to prioritize workload. Its longest flagged run is an uncertainty/crossing proxy, not a measured gross-error run. Acquisition QC remains separate.", "",
        packs, "",
        "The four volumes supply 2,048 full B-scans and 36 unreviewed candidates. The actual GUI reader loaded all four packs; no label writer was allowed during verification. Shadowed thickness is NaN. Unsupported outer layers are explicitly unreliable. These files complete the automated workflow; no automatic acceptance or further manual annotation was performed.", "",
        link("Boundary coverage/error curves", root / "calibration_dp/coverage_error_boundaries.png") + " · " + link("Thickness coverage/error curves", root / "calibration_dp/coverage_error_thickness.png") + " · " + link("Review examples", root / "review_queue/review_examples.png"), ""]
    (root / "PHASE_3_REPORT.md").write_text("\n".join(phase3), encoding="utf-8")
    snapshot = root / "implementation_snapshot"
    sources = sorted((repo / "code").rglob("*.py")) + [repo / name for name in ("README.md", "PIPELINE.md", "AGENTS.md", "CLAUDE.md") if (repo / name).exists()]
    copied = []
    for source in sources:
        dest = snapshot / source.relative_to(repo)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and fingerprint(dest)["sha256"] != fingerprint(source)["sha256"]:
            raise ValueError(f"Refusing to rewrite a frozen source snapshot: {dest}")
        if not dest.exists(): shutil.copy2(source, dest)
        copied.append(dict(source=fingerprint(source), copy=fingerprint(dest)))
    write_json(snapshot / "source_manifest.json", dict(scope="Repository Python source snapshot for reproducibility; includes inherited code and does not imply authorship of every file. Exact training source is separately archived in source_used.", files=copied))
    exclude = {"implementation_snapshot", "cv_nine_animals", "cv_nine_animals_bf16"}
    artifacts = [fingerprint(path) for path in sorted(root.rglob("*"))
        if path.is_file() and not any(part in exclude or part == "__pycache__" for part in path.relative_to(root).parts)
        and path.name != "checkpoint_manifest.json"]
    write_json(root / "checkpoint_manifest.json", dict(status="complete", created_utc=datetime.now(timezone.utc).isoformat(),
        inputs_read_only=True, manual_labels_written=False, former_test_animals_released_by_user=True,
        untouched_final_test_estimate_claimed=False, implementation_checks_passed=33, test_logs=tests,
        source_snapshot=fingerprint(snapshot / "source_manifest.json"), artifacts=artifacts,
        excluded_discarded_probes=sorted(exclude - {"implementation_snapshot"}), production_promoted=False))
    print(json.dumps(dict(guide=str(root / "START_HERE.md"), artifacts=len(artifacts), source_files=len(copied), tests_passed=33)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    run(parser.parse_args())
