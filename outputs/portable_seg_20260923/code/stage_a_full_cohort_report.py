"""Write full-cohort checkpoint reports while dependent jobs continue."""
import argparse
import csv
import json
from pathlib import Path

from stage_a.common import write_json, write_csv
from stage_a_inner_progress_report import compare_table, calibration_table
from stage_a_inner_retina import SURFACES, BANDS


def read_rows(path):
    if not path.exists(): return []
    with path.open(newline="", encoding="utf-8") as f: return list(csv.DictReader(f))


def filtered(rows, field, value, scope=None):
    return [r for r in rows if r[field] == value and (scope is None or r["evidence_scope"] == scope)]


def regression_rows(rows):
    base = {(r["axis"], r["group"], r["name"], r["sensitivity"]): r for r in rows
            if r["decoder"] == "soft" and r["mode"] == "raw" and r["evidence_scope"] == "full_manual_cohort"
            and r["axis"] in ("pooled", "animal")}
    failures = []
    for r in rows:
        key = r["axis"], r["group"], r["name"], r["sensitivity"]
        if (r["decoder"] != "dp_project" or r["mode"] != "raw"
                or r["evidence_scope"] != "full_manual_cohort" or key not in base): continue
        for metric in ("median_abs_um", "p95_abs_um", "gross_error_fraction_of_predictions", "coverage"):
            delta = float(r[metric]) - float(base[key][metric]) if r[metric] and base[key][metric] else None
            worse = delta is not None and (delta < -1e-6 if metric == "coverage" else delta > 1e-6)
            if worse:
                failures.append(dict(axis=r["axis"], group=r["group"], name=r["name"], sensitivity=r["sensitivity"],
                    metric=metric, soft_value=float(base[key][metric]), dp_value=float(r[metric]), delta=delta,
                    unit="fraction" if metric in ("coverage", "gross_error_fraction_of_predictions") else "um"))
    return failures


def run(args):
    root = args.out
    census = json.loads((root / "data/census.json").read_text())
    cv = root / "cv_full_cohort"
    history = read_rows(cv / "ensemble_00_history.csv")
    epoch = max((int(r["epoch"]) for r in history), default=0)
    all_history = read_rows(cv / "ensemble_09_history.csv")
    all_epoch = max((int(r["epoch"]) for r in all_history), default=0)
    calibrated = (root / "held_animal_comparison/evaluation_summary.json").exists()
    hybrid_done = (root / "outer_free_hybrid_loao/experiment.json").exists()
    queue_done = (root / "review_queue/queue_summary.json").exists()
    fit_done = (root / "all_label_fit_diagnostic/evaluation_summary.json").exists()
    verified = ((root / "verification_complete.json").exists()
                and json.loads((root / "verification_complete.json").read_text()).get("passed") is True)
    trained = (cv / "training_complete.json").exists() and epoch == 124 and all_epoch == 124
    complete = all((trained, calibrated, hybrid_done, queue_done, fit_done, verified))
    parts = ["# Full labeled-cohort run", "",
        "**Status: " + ("completed" if complete else "running; this report is a checkpoint and work continues") + ".** No cohort choice or approval is pending.", "",
        "The user explicitly authorized any/all labeled animals. A new dataset contains 102 corrected B-scans from nine animals and 27 volumes; 59 rejected decisions supply no position targets. The historical 101-label/27-volume/9-animal cohort is present exactly, plus one new annotation. Original datasets, labels, and checkpoints remain unchanged.", "",
        "Only manual segmentation is ground truth. Exact recorded stroke columns are used for the new annotation; legacy labels use the documented edited-surface approximation. Untouched automatic surfaces, software displacement, invisibility, unreliability, image exclusions, out-of-image positions, and shadows are excluded. The segmentation skill and published layer thicknesses were not used as truth.", "",
        "All manually supported regions are now available, irrespective of footprint status. The original Stage A remote/control mask is retained for a separate sensitivity analysis. Only eight labeled B-scans intersect footprint columns; this does not support a lesion-core reliability claim.", "",
        "## What releasing the cohort means", "",
        "Former test animals TS247 and TS283 now contribute manual evidence. The rejected-only TS328 contributes none. There is no untouched final-test set in this new experiment. The nine evaluation models each exclude their evaluated animal and a distinct calibration animal, training on the other seven. The separate all-label model trains on all nine and supplies experimental inference only. Its fit errors are never an independent accuracy estimate.", "",
        f"Training checkpoint: animal-excluded models {epoch}/124 epochs; all-label model {all_epoch}/124 epochs. Each epoch has 48 updates with uniform animal sampling, then uniform eligible B-scan sampling and optional lateral flipping. Eight boundary heads, base width 8, learning rate 0.0003, and region weight 0.1 are retained.", "",
        "BF16 convolutions use less GPU memory; the objective and optimizer remain FP32. Faster GPU kernels are permitted, so a seed alone does not guarantee bitwise reproducibility. The source, data identities, sampling states, optimizer states, and every completed epoch are checkpointed. Two brief deterministic scheduling probes were discarded; the delivered run starts from its own fixed random initialization. `source_used/cv_training_source.py` is the exact source used.", "",
        "The architecture decision comes from the earlier completed equal-budget [four-versus-eight-head experiment](../20260909_inner_retina_tier1/PHASE_1_COMPLETE.md): four heads lost. It was not repeated as an architecture sweep on the expanded cohort. The earlier [three-way decoder comparison](../20260909_inner_retina_tier1/PHASE_2_REPORT.md) also found little accuracy benefit from the much more expensive joint graph cut. This continuation evaluates the selected cheap DP control on all manual evidence. Those linked reports describe their historical cohort restrictions; the user's subsequent release applies to this new run.", "",
        "## Manual-cohort audit", "",
        "The exact historical 101-label subset has matched-manual prior residual half-widths 36.53→26.17 pixels for RNFL_GCL and 33.61→22.24 for GCL_IPL when the anchor changes from PR_RPE to IPL_INL. This confirms the direction of the conditioning improvement, but not the originally quoted 41.8/30.1 and 40.1/25.8 values. Masks and the median-of-B-scan-fractions estimator are documented in `prerequisites/`.", "",
        "The scalar-offset residual figures also do not reproduce under the explicit median-offset convention. `oracle_offsets.csv` preserves the measurements and missing-prediction denominators; no number was adjusted to match the prompt. The current 102-label footprint audit counts 235 footprint A-lines, with only 96 supported at all four inner boundaries. These are descriptive counts, not lesion accuracy evidence.", "",
        "## Original model on the expanded cohort", "",
        "The unchanged v4 model is a descriptive comparator. Five animals contributed its training and two its validation/checkpoint selection; its pooled full-cohort performance is not independent. Historical test animals are tabulated separately, and b0510 sensitivity accompanies all pooled p95 values. Every value below is in micrometres.", ""]
    old = read_rows(root / "original_v4_full_cohort/metrics.csv")
    if old:
        parts += ["### TS247 and TS283: absent from original model development", "",
            compare_table(filtered(old, "decoder", "soft", "historical_test_animals"),
                          filtered(old, "decoder", "dp_project", "historical_test_animals"),
                          left="Original soft", right="Original + ordered DP"), "",
            "![Expanded manual cohort compared with unchanged v4](examples_expanded_cohort/comparison_examples.png)", ""]
    classical = read_rows(root / "classical_loao/metrics.csv")
    if classical:
        parts += ["## Classical inner-prior comparison", "",
            "The two fractions are fitted excluding the evaluated animal. Both arms share the original v2 ILM/IPL_INL endpoint provider; its inherited global fitting history prevents a whole-pipeline independence claim. N=3 averaging and attraction 0.05 are unchanged. IPL_INL is not refit.", "",
            compare_table(filtered(classical, "predictor", "fixed_v2_endpoints_original_priors"),
                          filtered(classical, "predictor", "inner_band_two_priors"),
                          left="Original priors", right="Inner fractions"), "",
            "The inner-boundary medians improve, while GCL thickness median changes from 4.056 to 4.065 µm. This is not a strict no-regression pass. A zero classical ILM median must also be read in light of the shared legacy labeling/endpoint history; it is not an independent validation claim. No production prior was changed.", ""]
    failures = []
    if calibrated:
        rows = read_rows(root / "held_animal_comparison/metrics.csv")
        failures = regression_rows(rows)
        write_csv(root / "held_animal_comparison/strict_regressions.csv", failures)
        parts += ["## Animal-excluded decoder comparison", "",
            "These are raw errors from models that never trained on the evaluated animal, against all manually supported columns. Retained errors and coverage are separate; unlabelled image regions cannot establish accuracy.", "",
            compare_table(filtered(rows, "decoder", "soft", "full_manual_cohort"),
                          filtered(rows, "decoder", "dp_project", "full_manual_cohort"),
                          left="Held-animal soft", right="Held-animal DP"), ""]
        movement = read_rows(root / "held_animal_comparison/movement.csv")
        for method in ("soft", "dp_project"):
            chosen = [r for r in movement if r["decoder"] == method]
            parts.append(f"{method}: {sum(int(r['decoded_crossing_alines']) for r in chosen):,} crossing A-lines / {sum(int(r['alines']) for r in chosen):,} across all 102 manually supported B-scans.")
        parts += ["", f"Strict no-regression result: {'FAILED' if failures else 'no numerical regressions detected'} for median error, p95 error, gross-error fraction, and finite-prediction coverage across pooled and per-animal rows, with both b0510 sensitivities. There are {len(failures)} worsened metric cells, listed without rounding away differences in `strict_regressions.csv` (numerical tolerance 0.000001). Numerical comparison alone is not a deployment validation.", "",
            "### Original Stage A remote/control scope only", "",
            compare_table(filtered(rows, "decoder", "soft", "original_stage_a_remote_control_scope"),
                          filtered(rows, "decoder", "dp_project", "original_stage_a_remote_control_scope"),
                          left="Held-animal soft", right="Held-animal DP"), ""]
        for animal in sorted(census["eligible_by_animal"]):
            parts += [f"### {animal}", "",
                compare_table(filtered(rows, "decoder", "soft", "full_manual_cohort"),
                              filtered(rows, "decoder", "dp_project", "full_manual_cohort"), group=animal,
                              left="Held-animal soft", right="Held-animal DP"), ""]
        parts += ["## Transfer of uncertainty thresholds between animals", "",
            "Each cutoff is set using another calibration animal and then evaluated on the held animal. The tables show per-animal ranges at the 90th calibration percentile, not a promise of 90% retained coverage. All curves, denominators, zero-coverage cases, and both b0510 sensitivities remain in the CSV files. Error summaries are conditional on retaining a prediction.", ""]
        for folder, title in (("calibration_dp", "Ordered DP"), ("calibration_soft", "Original soft estimator")):
            parts += [f"### {title}", "", calibration_table(root / folder), "",
                f"![{title}: boundary coverage and error]({folder}/coverage_error_boundaries.png)", "",
                f"![{title}: thickness coverage and error]({folder}/coverage_error_thickness.png)", ""]
        parts += ["No universal deployment threshold is adopted from this small development cohort. The review workflow uses a per-volume entropy quantile as an experimental workload rule. It does not guarantee measurement accuracy or quantify human time saved.", ""]
    if hybrid_done:
        hybrid = read_rows(root / "outer_free_hybrid_loao/metrics.csv")
        normalized = [dict(r, evidence_scope="full_manual_cohort",
            decoder="soft" if r["predictor"] == "held_animal_unet_inner" else "dp_project") for r in hybrid]
        hybrid_failures = regression_rows(normalized)
        hybrid_export = [dict({k: v for k, v in r.items() if k not in ("soft_value", "dp_value")},
            network_value=r["soft_value"], hybrid_value=r["dp_value"]) for r in hybrid_failures]
        write_csv(root / "outer_free_hybrid_loao/strict_regressions.csv", hybrid_export)
        parts += ["## Inner solver with no outer-surface coordinate", "",
            "Both arms share held-animal learned ILM/IPL_INL endpoints. The hybrid uses classical costs and two manual fractions fitted from the other eight animals; its endpoint network uses seven training animals. PR_RPE coordinates are not consumed, although the eight-head network retains outer auxiliary supervision. Missing or infeasible endpoints remain missing.", "",
            compare_table(filtered(hybrid, "predictor", "held_animal_unet_inner"),
                          filtered(hybrid, "predictor", "held_animal_anchors_inner_classical"),
                          left="Held-animal network", right="Same endpoints + classical costs"), "",
            f"Strict no-regression result: {'FAILED' if hybrid_failures else 'no numerical regressions detected'}; {len(hybrid_failures)} worsened metric cells are recorded in `outer_free_hybrid_loao/strict_regressions.csv`. The hybrid is not adopted. The complete raw/retained per-animal tables and finite-prediction coverage are in `outer_free_hybrid_loao/metrics.csv`. This experimental control does not change the original classical endpoint provider or its IPL_INL prior.", ""]
    if fit_done:
        fit = read_rows(root / "all_label_fit_diagnostic/metrics.csv")
        parts += ["## All-label inference model: fit diagnostic only", "",
            "The separate ALL_LABELLED model uses every one of the nine manually supported animals. The following is an IN-SAMPLE fit check, not an independent error or deployment-coverage estimate. It is supplied to make the saved inference model reviewable.", "",
            compare_table(filtered(fit, "decoder", "soft", "full_manual_cohort"),
                          filtered(fit, "decoder", "dp_project", "full_manual_cohort"),
                          left="In-sample soft", right="In-sample DP"), ""]
    if queue_done:
        queue = json.loads((root / "review_queue/queue_summary.json").read_text())
        parts += ["## Completed full-volume outputs and human-review packs", "",
            "| Volume | B-scans | Raw crossings | Ordered crossings | New review candidates |", "|---|---:|---:|---:|---:|"]
        for v in queue["volumes"]:
            parts.append(f"| {v['scan_id']} | {v['n_bscans']} | {v['raw_crossing_alines']:,} | {v['crossing_alines']} | {len(v['selected_bscans'])} |")
        parts += ["", "Every candidate is an unreviewed automatic proposal. The queue retains the original Stage A remote/control volume mask, keeps acquisition QC separate, and excludes existing reviewed B-scans. The longest flagged run is an uncertainty/crossing proxy; a true gross-error run is unknowable without manual reference.", "",
            "Shadowed thickness is NaN. Unsupported INL, OPL, PHOTORECEPTOR, RPE, and full-retina TOTAL are explicitly unreliable/NaN rather than silently dropped. The experimental measurements cover four complete volumes, not the full 314-scan acquisition inventory.", "",
            "![New review candidates from the all-label model](review_queue/review_examples.png)", ""]
    for folder, title in (("examples_held_animal", "Held-animal predictions"), ("examples_all_label_fit", "All-label model fit; not independent validation"), ("examples_new_manual_strokes", "The additional annotation with exact stroke provenance")):
        if (root / folder / "comparison_examples.png").exists():
            parts += [f"## {title}", "", f"![{title}]({folder}/comparison_examples.png)", ""]
    parts += ["## Saved outputs and verification", "",
        "- Frozen labels and derived image/target identities: `data/`.",
        "- Nine animal-excluded models and the separate all-label inference model: `cv_full_cohort/`.",
        "- Accuracy measured on excluded animals: `held_animal_comparison/` and `calibration_dp/`, with the original soft control in `calibration_soft/`.",
        "- Experimental volume arrays and GUI-compatible packs: `review_queue/`.",
        "- The previous Tier 1 report remains a historical seven-animal checkpoint. Its old locked-test description does not govern this explicitly authorized full-cohort run.", ""]
    if verified:
        parts += ["All final identity, animal-exclusion, numerical reload, and actual-GUI-reader checks passed. Manual label files and the original v4 checkpoint/code identity are unchanged. `verification_complete.json` records the checks and their limits.", ""]
    (root / "RUN_REPORT.md").write_text("\n".join(parts), encoding="utf-8")
    write_json(root / "execution_checkpoint.json", dict(status="complete" if complete else "running",
        manual_corrected_bscans=102, animals=9, former_test_animals_released=True,
        no_user_approval_pending=True, cv_epoch=epoch, all_labels_epoch=all_epoch,
        calibration_complete=calibrated, hybrid_complete=hybrid_done, queue_complete=queue_done,
        fit_diagnostic_complete=fit_done, verification_complete=verified,
        decoder_regressed_cells=len(failures) if calibrated else None,
        training_directory=str(cv), production_promoted=False))
    print(root / "RUN_REPORT.md")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    run(p.parse_args())
