"""Render the Tier 1 baseline and prerequisite measurements as reviewable tables."""
import argparse
import csv
import json
from pathlib import Path

from stage_a.common import output_dir
from stage_a_inner_retina import BANDS, SURFACES


def csv_rows(path):
    with Path(path).open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def fmt(value, digits=2):
    return "unavailable" if value in (None, "") else f"{float(value):.{digits}f}"


def paired_table(rows, group, predictor=None, cohort=None):
    selected = [r for r in rows if r["mode"] == "raw" and r["group"] == group
                and r["axis"] == ("pooled" if group == "all" else "animal")
                and (predictor is None or r["predictor"] == predictor)
                and (cohort is None or r["cohort"] == cohort)]
    indexed = {(r["kind"], r["name"], r["sensitivity"]): r for r in selected}
    lines = ["| Surface / band | Median with / without (µm) | p95 with / without (µm) | Gross with / without | Eligible with / without |",
             "|---|---:|---:|---:|---:|"]
    for kind, names in (("boundary", SURFACES), ("thickness", BANDS)):
        for name in names:
            a, b = (indexed[kind, name, s] for s in ("with_b0510", "without_b0510"))
            pair = lambda field, digits=2: f"{fmt(a[field], digits)} / {fmt(b[field], digits)}"
            lines.append(f"| {name} | {pair('median_abs_um')} | {pair('p95_abs_um')} | "
                         f"{pair('gross_error_fraction_of_eligible', 4)} | {pair('n_eligible', 0)} |")
    return "\n".join(lines)


def run(args):
    root = output_dir(args.out)
    baseline = csv_rows(root / "baseline/metrics.csv")
    comparison = csv_rows(root / "comparison/comparison.csv")
    audit = root / "prerequisites_final"
    gate = json.loads((audit / "prerequisite_gate.json").read_text())
    spreads = csv_rows(audit / "prior_spread.csv")
    offsets = csv_rows(audit / "oracle_offsets.csv")
    lesions = csv_rows(audit / "lesion_support.csv")
    text = ["# Inner-retina Tier 1 — baseline and prerequisite audit", "",
        "Historical baseline-audit checkpoint. The user subsequently clarified that checkpoints "
        "must not stop execution. Work continued using the seven permitted development animals, "
        "with final-test animals still locked. See RUN_REPORT.md for current results. "
        "The execution-status and compatibility sections below describe the earlier checkpoint only.", "",
        "Only manually drawn boundaries are ground truth. No published thickness value was used to fit, "
        "score, accept, or reject a surface. Automatic results appear only as predictors. "
        "The segmentation skill is disregarded, following the user's correction.", "",
        "## Phase 1a: frozen v4 inner-retina baseline", "",
        "The existing epoch-124 eight-head checkpoint's saved validation predictions are read unchanged. "
        "The four boundaries and RNFL/GCL/IPL retain the original frozen eligible masks and metric definitions. "
        "INNER_RETINA = IPL_INL − ILM requires eligible manual evidence at both endpoints. "
        "All masks and uncertainty outputs remain unchanged, including saved crossing flags involving an outer boundary.", "",
        "Complete cohort: 38 validation decisions, 14 eligible B-scans, two animals (TS169 and TS325). "
        "Every table pairs the complete result with the sensitivity excluding only "
        "`TS325_OD_2026-05-26_6mo_s01_112940_b0510`. Exclusion is a sensitivity, not the headline. "
        "Gross means absolute error >25 µm and is descriptive, not a deployment criterion.", "",
        paired_table(baseline, "all"), "",
        "### TS169", "", paired_table(baseline, "TS169"), "",
        "### TS325", "", paired_table(baseline, "TS325"), "",
        "Machine-readable raw and retained tables, per-animal and animal-macro rows, per-B-scan rows, "
        "and input fingerprints are in `baseline/`. Missing or withheld predictions remain in eligible "
        "denominators as failures. Conditional error is unavailable when no predictions exist; "
        "it is never interpreted as zero. No new thickness map was generated or interpolated.", "",
        "## Classical comparison coverage", "",
        "Stored auto covers all 14 eligible B-scans. Stored classical v2 covers 11/14 and has no TS169 "
        "predictions. `comparison/` contains complete-cohort and shared-available results separately, "
        "each with b0510 sensitivity. The three-way shared comparison is TS325-only. "
        "Missing TS169 predictions count as failures in the complete cohort.", "",
        "### Shared-available TS325: v4", "",
        paired_table(comparison, "all", "unet_v4", "shared_available"), "",
        "### Shared-available TS325: stored auto", "",
        paired_table(comparison, "all", "stored_auto", "shared_available"), "",
        "### Shared-available TS325: classical v2", "",
        paired_table(comparison, "all", "v2", "shared_available"), "",
        "## Prerequisite cohort and manual-evidence policy", "",
        f"The permitted cohort contains **{gate['actual']['corrected_bscans']} corrected B-scans, "
        f"{gate['actual']['volumes']} volumes and {gate['actual']['animals']} animals**, compared with "
        "101/27/9 in the prompt. Final-test animal files were not opened. The final-test partition is unchanged.", "",
        "| Animal | Corrected B-scans |", "|---|---:|"]
    text.extend(f"| {a} | {n} |" for a, n in gate["corrected_bscans_by_animal"].items())
    text += ["", "All 68 permitted corrected labels use legacy surface flags; none records local stroke provenance. "
        "The audit uses the existing `surface_flag` policy: edited, visible, reliable, non-excluded, "
        "non-displaced evidence, requiring independent manual evidence for both anchors and the predicted surface. "
        "An untouched automatic anchor is not promoted to manual ground truth. The surface-wide edit approximation "
        "still cannot establish which individual columns were drawn; that uncertainty remains unquantified. "
        "The descriptive manual audit does not add automatic-shadow or Stage A remote-footprint masks. "
        "The model baseline uses its original, stricter frozen Stage A masks; these are different denominators.", "",
        "### Prior spread", "",
        "Estimate: median of per-B-scan median positional fractions, then pooled p95 absolute positional "
        "residual; at least 20 usable columns per B-scan and anchor span >40 pixels. Both anchoring methods "
        "are also scored on identical eligible manual-anchor columns; the table below uses that matched cohort. "
        "The larger anchor-specific cohorts are saved separately in the CSV. These descriptive fractions "
        "were not installed as priors.", "",
        "| Surface | Anchor | Manual B-scans / columns | Measured fraction | Residual p95 (px) | Prompt p95 (px) |",
        "|---|---|---:|---:|---:|---:|"]
    text.extend(f"| {r['surface']} | {r['outer_anchor']} | {r['n_bscans']} / {r['n_columns']} | "
                f"{fmt(r['fraction'], 4)} | {fmt(r['residual_p95_px'])} | {r['expected_p95_px']} |"
                for r in spreads if r["cohort"] == "matched_manual_anchors")
    text += ["", "The spread reduction is similar in direction and relative size to the prompt, "
        "but it is a development-cohort measurement, not reproduction of the stated 101-label cohort.", "",
        "### Scalar offset residuals", "",
        "Subtract the median automatic-minus-manual offset within each B-scan or volume, then pool "
        "absolute residuals. This offset minimises absolute loss; it is not an asserted p95-optimal oracle. "
        "Both stored-auto and stored-v2 comparators are explicitly identified because they differ. "
        "The prompt supplies no original calculation script or fully specified oracle estimator. "
        "The quoted residuals do not reproduce under this documented calculation.", "",
        "| Comparator | Surface | Offset unit | Compared / eligible columns | Residual p95 (px) | Prompt p95 (px) |",
        "|---|---|---|---:|---:|---:|"]
    text.extend(f"| {r['predictor']} | {r['surface']} | {r['offset_group']} | {r['n_columns']} / "
                f"{r['n_eligible']} | {fmt(r['residual_p95_px'])} | {r['expected_p95_px']} |" for r in offsets)
    supported = sum(int(r["manual_any_surface_columns"]) for r in lesions)
    all_inner = sum(int(r["manual_all_inner_columns"]) for r in lesions)
    text += ["", "### Lesion support", "",
        f"Six permitted corrected B-scans intersect a drawn footprint: 199 footprint columns, "
        f"{supported} non-excluded columns with at least one manually supported surface, "
        f"and {all_inner} columns with all four inner surfaces supported. "
        "Footprint intersection is read from the frozen manual-footprint-derived signed-distance arrays; "
        "it is not a segmentation-derived lesion. No within-lesion performance claim is made. "
        "These counts cannot reproduce the prompt's seven B-scans from nine animals while test animals remain locked.", "",
        "## Historical execution status at the initial audit", "",
        "| Item | Status |", "|---|---|",
        "| 1a: four-surface reporting and unchanged-checkpoint baseline | Implemented; measured |",
        "| Three prerequisite measurements on the exact 101-label cohort | Not reproduced under the test lock; permitted-subset audit saved |",
        "| 1b: classical prior refit and real-pipeline LOAO | Not run; no priors adopted |",
        "| 1c: four-head training comparison | Not run; no win/loss conclusion is possible |",
        "| Phase 2: constrained decoder comparison | Not started |",
        "| Phase 3: calibration and review queue | Not started; no coverage guarantee or threshold may be quoted |", "",
        "The attached prompt's cohort-mismatch stopping condition was superseded by the user's "
        "instruction to checkpoint and continue on the permitted development cohort. "
        "A seven-animal calibration would require model training that excludes each held-out animal; "
        "merely thresholding predictions from a model trained on that animal would not be valid LOAO.", "",
        "## Verification and checkpoint compatibility", "",
        "The new tests cover unchanged original metrics, INNER_RETINA endpoint eligibility, missing "
        "predictions, shadow withholding, four-head readout, per-B-scan run separation, exact sensitivity "
        "selection, legacy displacement exclusion and rejection of a test-split request before file access. "
        "Numerical and input-fingerprint verification is recorded in `verification.json`.", "",
        "No file inside `code/stage_a/` was added or changed by this work. The tracked package matches "
        "both Git HEAD and the v4 checkpoint's recorded code identity. Additional untracked modules created "
        "in that directory during concurrent workspace work change the full directory hash, so the current "
        "checkout does not pass the existing training-resume guard. Those files were left untouched. "
        "`checkpoint_compatibility.json` records the observed hashes and additional filenames. "
        "This baseline analysis does not resume training or change the checkpoint.", "",
        "## Reproduce", "", "Activate `octa`, set `PYTHONPATH` to the repository's `code` directory, "
        "and use new empty output directories:", "", "```powershell",
        "python code/stage_a_inner_retina_audit.py --out outputs/stage_a/<new-run>/prerequisites_final",
        "python code/stage_a_inner_retina.py --eval outputs/stage_a/20260908_v4_longtrain/dev_seed20260908/eval_validation --out outputs/stage_a/<new-run>/baseline",
        "python code/stage_a_compare.py --scope inner-retina --evals unet_v4=outputs/stage_a/20260908_v4_longtrain/dev_seed20260908/eval_validation stored_auto=outputs/stage_a/20260908_v4_longtrain/baseline_validation v2=outputs/stage_a/20260908_v4_longtrain/v2_validation --out outputs/stage_a/<new-run>/comparison",
        "python code/stage_a_inner_retina_report.py --out outputs/stage_a/<new-run>",
        "python -m unittest -v test_stage_a_inner_retina", "```", ""]
    (root / "PHASE_1_REPORT.md").write_text("\n".join(text), encoding="utf-8")
    print(root / "PHASE_1_REPORT.md")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    run(parser.parse_args())
