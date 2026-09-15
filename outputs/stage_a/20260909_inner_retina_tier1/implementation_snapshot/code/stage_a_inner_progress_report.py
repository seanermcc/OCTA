"""Write reviewable checkpoint reports without stopping the running experiments."""
import argparse
import csv
import json
from pathlib import Path

from stage_a_inner_retina_report import csv_rows, paired_table, fmt
from stage_a_inner_retina import SURFACES, BANDS
from stage_a.common import write_json


def compare_table(a, b, group="all", left="Existing 8", right="Four heads"):
    def index(rows):
        return {(r["name"], r["sensitivity"]): r for r in rows if r["mode"] == "raw"
                and r["group"] == group and r["axis"] == ("pooled" if group == "all" else "animal")}
    a, b = index(a), index(b)
    lines = [f"| Surface / band | {left}: median | {right}: median | {left}: p95 with / without b0510 | {right}: p95 with / without b0510 |",
             "|---|---:|---:|---:|---:|"]
    for name in list(SURFACES) + list(BANDS):
        pair = lambda d: " / ".join(fmt(d[name, s]["p95_abs_um"]) for s in ("with_b0510", "without_b0510"))
        lines.append(f"| {name} | {fmt(a[name, 'with_b0510']['median_abs_um'])} | "
                     f"{fmt(b[name, 'with_b0510']['median_abs_um'])} | {pair(a)} | {pair(b)} |")
    return "\n".join(lines)


def calibration_table(root, quantile=.9):
    rows = csv_rows(root / "per_animal_spread.csv")
    lookup = {(r["name"], r["sensitivity"]): r for r in rows
              if float(r["calibration_quantile"]) == quantile}
    lines = ["| Surface / band | Coverage range with / without b0510 (%) | Retained p95 range with / without b0510 (µm) |",
             "|---|---:|---:|"]
    for name in list(SURFACES) + list(BANDS):
        coverage, tails = [], []
        for sensitivity in ("with_b0510", "without_b0510"):
            r = lookup[name, sensitivity]
            coverage.append(f"{100*float(r['coverage_min']):.1f}–{100*float(r['coverage_max']):.1f}")
            tails.append(f"{float(r['retained_p95_min_um']):.2f}–{float(r['retained_p95_max_um']):.2f}")
        lines.append(f"| {name} | {' / '.join(coverage)} | {' / '.join(tails)} |")
    return "\n".join(lines)


def run(args):
    root = args.out
    baseline = csv_rows(root / "baseline/metrics.csv")
    four = csv_rows(root / "four_head_eval/metrics.csv")
    classical = csv_rows(root / "classical_loao/metrics.csv")
    eight_ck = "../20260908_v4_longtrain/dev_seed20260908/best.pt"
    parts = ["# Inner-retina Tier 1 — current execution report", "",
        "Checkpoints are outputs, not approval gates. The user's clarification supersedes the attached prompt's cohort-mismatch stopping instruction. Work uses the seven permitted development animals; final-test animals stay locked.", "",
        "Only manual annotations supply segmentation ground truth. The layer-segmentation skill and published thickness tables were not used for fitting, scoring, or acceptance. Legacy labels identify edited surfaces but not individual strokes; eligible surface-wide columns remain an imperfect approximation of what was drawn.", "",
        "## Decisions reached", "",
        "- Reporting now uses ILM, RNFL_GCL, GCL_IPL, IPL_INL, RNFL, GCL, IPL, and INNER_RETINA.",
        "- Keep the existing eight-head v4 model. The single-seed, equal-budget four-head experiment failed the no-regression criterion.",
        "- The two classical inner fractions improved their target-boundary errors under a matched-endpoint LOAO comparison, but GCL thickness worsened on the matched validation cohort. No production prior was changed.",
        "- The constrained decoder eliminates crossings and markedly improves the worst example, but fails the strict no-regression rule. The cheaper ordered DP is available for experimental human review.",
        "- Held-animal calibration measures large variation in retained coverage. The saved review queue uses per-volume quantiles for triage, without a universal accuracy guarantee.", "",
        "## Phase 1c: equal-budget retraining", "",
        "Both runs use the frozen five training animals and two eligible validation animals, 200 epochs × 48 updates, base width 8, AdamW learning rate 0.0003, region weight 0.1, and seed 20260908. Four heads select epoch 49 using four-boundary validation loss; eight heads use the delivered epoch 124 selected using the original eight-boundary loss. These are their respective validation-selected models, not a multi-seed architecture conclusion.", "",
        "All values below are micrometres. Medians include b0510; every p95 is paired with its sensitivity excluding that one preidentified B-scan. Raw errors use the same frozen manual-reference columns; retained errors, coverage, gross errors, and missing-value denominators are also preserved in the machine-readable results.", "",
        compare_table(baseline, four), "",
        "### TS169", "", compare_table(baseline, four, "TS169"), "",
        "### TS325", "", compare_table(baseline, four, "TS325"), "",
        "The ILM/RNFL large-error tails worsened materially, including when b0510 is excluded. Improvements in IPL_INL and some IPL summaries do not establish an overall win. Eight heads are retained, with four reported.", "",
        "![Manual reference and model comparison](examples_retraining/comparison_examples.png)", "",
        "## Phase 1b: measured classical control", "",
        "Each evaluation animal's two fractions are fitted using only the other permitted animals' manually supported ILM, inner boundary, and IPL_INL coordinates. The 17-volume calculation uses N=3 B-scan averaging and five-scan refinement with attraction 0.05. ILM and IPL_INL endpoint arrays are exactly unchanged between the two arms; IPL_INL is not refit.", "",
        compare_table([r for r in classical if r["predictor"] == "fixed_v2_endpoints_original_priors"],
                      [r for r in classical if r["predictor"] == "inner_band_two_priors"],
                      left="Original priors", right="Inner fractions"), "",
        "This classical table covers the permitted corrected cohort (68 corrected B-scans; 62 Stage-A-eligible), whereas the neural architecture comparison covers 14 eligible validation B-scans. Do not compare the two pooled tables as if their cohorts were identical. `classical_validation/` provides the same validation cohort for direct comparisons.", "",
        "The inner solver itself accepts only images, ILM/IPL_INL arrays, shadow, and two fractions. The unchanged old endpoint provider still depends on PR_RPE and carries prior fitting history, so the LOAO claim applies to the newly fitted fractions. The separate animal-excluded learned-endpoint control below tests an inference path that consumes no outer-surface coordinate.", "",
        "On the same 14 eligible validation B-scans, GCL thickness median error rises from 3.868 to 4.376 µm; this is a negative result for the strict no-regression criterion despite the better RNFL_GCL/GCL_IPL boundary medians. All p95 values and the paired sensitivity are in `classical_validation/metrics.csv`.", "",
        "## Prerequisite audit and baseline", "",
        "The original prompt's 101/27/9 cohort is incompatible with keeping final-test animals locked. On 68 corrected B-scans from 17 volumes and seven permitted animals, matched-manual prior half-widths decrease from 37.64 to 27.25 px for RNFL_GCL and from 35.03 to 22.73 px for GCL_IPL. This reproduces the direction, not the original cohort counts.", "",
        "The specified scalar-offset residuals did not reproduce under the documented median-offset calculation; the exact masks and offset convention were not specified in the prompt. Six permitted B-scans intersect a drawn lesion footprint (199 footprint columns; 139 with any manually supported inner surface; 96 with all four). No within-lesion claim is made.", "",
        "See `PHASE_1_REPORT.md` for the historical full baseline and prerequisite audit, `baseline/` for frozen per-animal and sensitivity tables, and `comparison/` for stored classical comparators. Stored v2 predictions lack TS169 completely: their shared three-way comparison covers 11 of 14 eligible B-scans and is TS325-only.", "",
        ""]
    hybrid_path = root / "outer_free_hybrid_loao/metrics.csv"
    if hybrid_path.exists():
        hybrid = csv_rows(hybrid_path)
        parts += ["### Additional control: learned endpoints without an outer coordinate", "",
            "Seven animal-excluded networks supply only ILM and IPL_INL to the classical inner solver. Each network trains on five other animals. The two fractions use manual annotations from the other six animals, excluding the evaluated animal. The control is that same held-animal network's four inner predictions. Eight-head training still used outer auxiliary labels; no PR_RPE coordinate is consumed at inference. This is a hybrid, not an independently solved classical IPL_INL endpoint.", "",
            compare_table([r for r in hybrid if r["predictor"] == "held_animal_unet_inner"],
                          [r for r in hybrid if r["predictor"] == "held_animal_anchors_inner_classical"],
                          left="Held-animal network", right="Same endpoints + classical inner costs"), "",
            "Both arms share exactly the same ILM/IPL_INL endpoint arrays. The classical costs retain N=3 averaging and attraction 0.05. Infeasible endpoint columns leave the two middle boundaries missing, and shadowed thickness remains missing. Pooled results cover the permitted corrected cohort; per-animal and raw/retained results are in `outer_free_hybrid_loao/metrics.csv`, with the identical 14-B-scan validation scope in `outer_free_hybrid_validation/`.", ""]
        parts += ["**Hybrid outcome: failed no-regression; not adopted.** RNFL_GCL median error rises from 2.745 to 6.464 µm and GCL_IPL from 2.653 to 6.303 µm. Only 95.45% and 95.47% of their eligible columns have finite hybrid predictions, respectively, versus 100% for the neural control. The hybrid's conditional errors must be read alongside those missing predictions. Some thickness tails improve, but they do not rescue the worse target-boundary errors and reduced coverage.", ""]
    parts += ["## Phase 2: decoder comparison", ""]
    decoder_path = root / "decoder_comparison/metrics.csv"
    if decoder_path.exists():
        rows = csv_rows(decoder_path)
        for method in ("dp_project", "graph_cut"):
            parts += [f"### {method}", "", compare_table(baseline,
                      [r for r in rows if r["decoder"] == method], right=method), ""]
            for animal in ("TS169", "TS325"):
                parts += [f"#### {animal}", "", compare_table(baseline,
                          [r for r in rows if r["decoder"] == method], group=animal, right=method), ""]
        movement = csv_rows(root / "decoder_comparison/movement.csv")
        counts = {method: sum(int(r["crossing_alines"]) for r in movement if r["method"] == method)
                  for method in ("soft", "dp_project", "graph_cut")}
        parts += [f"Across every one of the 14 manually supported validation B-scans, crossing A-line counts are {counts}. The denominator is 7,168 distinct A-lines. The other 24 validation decisions have no eligible manual targets and are not part of this accuracy comparison. This denominator also differs from the old boundary-column denominator.", "",
            "**Strict phase-2 no-regression criterion: failed.** Both constrained estimators improve the pooled medians and tails including b0510, but RNFL_GCL median error for TS169 rises from 2.106 to 2.143 µm and the pooled sensitivity without b0510 rises from 2.408 to 2.443 µm. TS169 INNER_RETINA median also rises from 4.165 to 4.398 µm. These small tradeoffs are reported, not rounded into a pass.", "",
            "**Experimental workflow choice: ordered DP plus minimum-gap projection.** The graph cut gives very similar manual-reference errors and substantially greater computational cost. It has not earned adoption over the cheaper control. The original soft estimator remains the scientific baseline; constrained candidates and measurements remain experimental.", "",
            "![Manual reference and decoder comparison](examples_decoders/comparison_examples.png)", "",
            "Large movements (>5 pixels) affect 7.8% of eligible ILM columns, 8.7% RNFL_GCL, 5.9% GCL_IPL, and 15.2% IPL_INL. Their mean entropy is higher than the other columns for all four boundaries (approximately 0.45–0.55 versus 0.35). This supports an uncertainty association; it does not calibrate entropy as a quality score. Full >0.5, >2, and >5 pixel results are in `decoder_diagnostics_checkpoint/`.", "",
            "Manual-reference consistency check: 18/4,580 GCL pairs lie outside the training-derived interval; RNFL and IPL pairs all lie within their intervals. Between 0.13% and 1.27% of eligible adjacent-column manual boundary steps exceed two pixels. The hard constraints therefore cannot represent every manual coordinate exactly. Validation did not tune the bounds.", ""]
    else:
        parts += ["Running the unchanged soft estimator, per-surface DP plus minimum-gap isotonic projection, and a true joint PyMaxflow graph cut on the same v4 logits. Results will be added when the comparison finishes.", ""]
    parts += ["Bounds use only the five original training animals' manual adjacent-pair thicknesses: q01/q99 widened outward by 20% of each endpoint. Minimum/maximum gaps in pixels: RNFL 18/235, GCL 3/37, IPL 28/82. Adjacent-A-line step is at most 2 pixels. No published anatomical value set these bounds.", "",
        "The graph construction uses minimum closed sets and hard implication arcs, with PyMaxflow providing the minimum cut. Small exhaustive searches verify its global energy against all feasible solutions. [Li, Wu, Chen and Sonka method](https://pmc.ncbi.nlm.nih.gov/articles/PMC2646122/); [PyMaxflow API](https://pmneila.github.io/PyMaxflow/maxflow.html).", "",
        "PyMaxflow 1.3.2 is isolated in this output directory's `dependencies/` without changing conda packages. Environment imports, a NumPy dot product, and a matplotlib rendering passed after installation.", "",
        "## Phase 3: animal-excluded calibration and review queue", ""]
    cv = root / "cv_seven_animals"
    history = csv_rows(cv / "ensemble_00_history.csv") if (cv / "ensemble_00_history.csv").exists() else []
    epoch = max((int(r["epoch"]) for r in history), default=0)
    parts += [f"Seven independent models: epoch {epoch}/124 at this checkpoint. Each fold has five training animals, one separate calibration animal, and one held-out evaluation animal. Roles rotate deterministically. Weight selection uses the fixed 124-epoch budget, never calibration or held-animal losses. Vectorised batching was checked against separate model losses and gradients.", "",
        "The 124-epoch budget comes from development-selected v4 training. This is development cross-validation of a fixed workflow, not an untouched final-test estimate or proof of deployment coverage.", "",
        "The queue builder writes packs accepted by the actual eight-surface GUI reader. Previously reviewed B-scans are excluded. A longest flagged run is explicitly an uncertainty/crossing proxy: true gross-error runs cannot be known on unlabelled images. The priority heuristic is not yet a measurement of human time saved. Acquisition-QC axes are stored separately.", "",
        "No deployment coverage number is justified. The held-animal curves measure development cross-validation, with per-animal spread and the b0510 sensitivity. A per-volume entropy quantile may be used for experimental review triage; it is not a promised error guarantee.", "",
    ]
    calibrated = all((root / f"calibration_{method}/calibration_summary.json").exists()
                     for method in ("dp", "soft"))
    if calibrated:
        parts += ["### Completed held-animal calibration", "",
            "All seven folds completed 124 epochs × 48 updates. None selected a checkpoint or entropy cutoff using the evaluated animal. All 62 eligible development B-scans had nonempty manual region supervision (minimum 1,780 region pixels), so the empty-region optimizer edge case does not arise in this run.", "",
            "The following ranges compare a cutoff placed at the 90th entropy percentile on a *different calibration animal*, then transferred to the held-out animal. This is not a pooled p95, and 90% is the calibration quantile, not a promised retained fraction. Each cell gives the range across seven held animals, first with b0510 and then without it. Boundary-specific and paired-boundary thickness coverage have different denominators.", ""]
        for folder, name in (("calibration_dp", "Ordered DP"), ("calibration_soft", "Original soft estimator")):
            thresholds = [float(r["threshold"]) for r in csv_rows(root / folder / "transferred_thresholds.csv")
                          if float(r["calibration_quantile"]) == .9]
            parts += [f"#### {name}", "",
                f"The seven calibration-animal cutoffs themselves range from {min(thresholds):.4f} to {max(thresholds):.4f}.", "",
                calibration_table(root / folder), "",
                f"![{name}: held-animal boundary coverage and error]({folder}/coverage_error_boundaries.png)", "",
                f"![{name}: held-animal thickness coverage and error]({folder}/coverage_error_thickness.png)", ""]
        parts += ["The full 50th–100th percentile transfer curves, fixed-threshold curves, eligible and retained counts, gross-error fractions, and per-animal sensitivities are saved alongside these plots. A universal threshold is not selected: the small, heterogeneous development cohort does not justify a deployment coverage/error guarantee. Per-volume quantiles remain an experimental way to allocate review, with high-priority cases and control cases both sampled.", ""]
        parts += ["For example, ordered-DP RNFL thickness coverage spans 38.8–96.2% across held animals at the 90th calibration percentile (38.8–98.4% without b0510), while the retained p95 error range is 6.00–25.51 µm in both sensitivities. TS165, the WT control animal, supplies the least favourable tail in this comparison. These results argue against quoting the earlier two-animal 90%-coverage figure as transferable reliability.", ""]
        if (root / "examples_held_animal/comparison_examples.png").exists():
            parts += ["### What the held-animal results look like", "",
                "These are independent fold models, so their numbers differ from the delivered v4 model's earlier gallery. The first row is the largest ordered-DP median error among the WT animal's three manually supported B-scans: median error changes from 6.3 to 6.9 µm despite crossings reaching zero. The second is the previously shown TS169 case; the third is the preidentified b0510 case, where median error falls from 29.7 to 2.2 µm. All errors use eligible manual columns only. The displayed raw curves extend into unlabelled areas; those areas are not accuracy evidence.", "",
                "![Manual annotations versus animal-excluded predictions](examples_held_animal/comparison_examples.png)", ""]
    if (root / "review_queue/queue_summary.json").exists():
        queue = json.loads((root / "review_queue/queue_summary.json").read_text())
        parts += ["### Completed full-volume review queue", "",
            "Two complete volumes, 1,024 B-scans, and 18 new review candidates (eight priorities plus one control per volume) are saved. The actual GUI pack reader confirms that every candidate is undecided, has no edited flags, and preloads no existing label.", "",
            "| Volume | Raw crossing A-lines | Ordered-DP crossings | Total A-lines | Experimental entropy cutoff |", "|---|---:|---:|---:|---:|"]
        for v in queue["volumes"]:
            parts.append(f"| {v['scan_id']} | {v['raw_crossing_alines']:,} | {v['crossing_alines']} | {v['n_alines']:,} | {v['entropy_cutoff']:.4f} |")
        parts += ["", "The per-volume 90th entropy percentile deliberately retains approximately 90% of available, in-scope, unshadowed boundary columns by construction. That percentage is not evidence of 90% accurate coverage. Shadowed thickness is NaN in both volumes. INL, OPL, PHOTORECEPTOR, RPE, and full-retina TOTAL remain explicitly unreliable/NaN in these inner-retina outputs.", "",
            "`review_queue/review_queue.csv` ranks all B-scans; `selected_review_queue.csv` lists the 18 selections. `review_queue/packs/` opens in the existing annotation GUI. Independent acquisition measurements are in each volume's `acquisition_qc_separate.json` and do not enter the queue priority.", "",
            "![Unreviewed automatic review candidates](review_queue/review_examples.png)", ""]
    parts += [
        "## Saved checkpoints and safety of the scientific inputs", "",
        f"- Selected existing model: `{eight_ck}`.",
        "- Four-head experiment: `four_head_seed20260908/best.pt`, with a complete 9,600-step history and exact checkpoint reload check.",
        "- Independent fold training: `cv_seven_animals/ensemble_00.pt`, checkpointed each epoch, with a fixed protocol and resume identity guard.",
        "- All implementation modules from this task live outside `code/stage_a/`. Original model/data code and frozen baseline predictions are preserved.",
        "- Source volumes, manual labels, frozen targets, and final-test partitions are read-only throughout this work.",
        "- Verified unchanged: 68 permitted corrected label files, 110 frozen target files, 110 image caches, 38 original baseline predictions, and the v4 checkpoint. The original Stage A resume code guard currently passes; the temporary concurrent-work mismatch described in the historical audit is resolved.", ""]
    parts += ["- All 31 checks passed: manual-reference eligibility, exact graph-cut solutions, independent model losses/gradients, resume fold isolation, entropy withholding, and real GUI pack loading. Original core Stage A code remains unchanged.",
        "- The exact CV source used for training is preserved in `source_used/cv_training_source.py`. A subsequent resume-only fix rejects changed fold grouping or broadcast tensor copies and verifies completed runs without rewriting exported models. It does not alter this run's trained weights.", ""]
    report_text = "\n".join(parts)
    (root / "RUN_REPORT.md").write_text(report_text, encoding="utf-8")
    sections = (("PHASE_1_COMPLETE.md", "Phase 1 — completed experiments", "## Phase 1c", "## Phase 2:"),
                ("PHASE_2_REPORT.md", "Phase 2 — constrained decoders", "## Phase 2:", "## Phase 3:"),
                ("PHASE_3_REPORT.md", "Phase 3 — calibration and review queue", "## Phase 3:", "## Saved checkpoints"))
    for filename, title, begin, end in sections:
        body = report_text[report_text.index(begin):report_text.index(end)]
        (root / filename).write_text(f"# {title}\n\nManual annotations are the only segmentation ground truth. Final-test animals remain locked. See [the complete report](RUN_REPORT.md) for shared provenance and verification.\n\n{body}", encoding="utf-8")
    completed = calibrated and hybrid_path.exists() and (root / "outer_free_hybrid_validation/metrics.csv").exists()
    write_json(root / "execution_checkpoint.json", dict(status="complete" if completed else "running", user_requested_continue=True,
        model_decision="keep_existing_eight_heads_report_four", four_head_experiment="failed_no_regression",
        decoder_acceptance="failed_strict_no_regression; experimental_review_only",
        classical_control="failed_strict_no_regression; original_priors_preserved",
        outer_free_hybrid="failed_strict_no_regression; not_adopted" if hybrid_path.exists() else "running",
        cv_epoch=epoch, cv_target_epochs=124, calibration_complete=calibrated,
        no_user_approval_pending=True, final_test_used=False, production_promoted=False))
    print(root / "RUN_REPORT.md")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    run(p.parse_args())
