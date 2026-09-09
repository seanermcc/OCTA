# Inner-retina Tier 1 — baseline and prerequisite audit

Historical baseline-audit checkpoint. The user subsequently clarified that checkpoints must not stop execution. Work continued using the seven permitted development animals, with final-test animals still locked. See RUN_REPORT.md for current results. The execution-status and compatibility sections below describe the earlier checkpoint only.

Only manually drawn boundaries are ground truth. No published thickness value was used to fit, score, accept, or reject a surface. Automatic results appear only as predictors. The segmentation skill is disregarded, following the user's correction.

## Phase 1a: frozen v4 inner-retina baseline

The existing epoch-124 eight-head checkpoint's saved validation predictions are read unchanged. The four boundaries and RNFL/GCL/IPL retain the original frozen eligible masks and metric definitions. INNER_RETINA = IPL_INL − ILM requires eligible manual evidence at both endpoints. All masks and uncertainty outputs remain unchanged, including saved crossing flags involving an outer boundary.

Complete cohort: 38 validation decisions, 14 eligible B-scans, two animals (TS169 and TS325). Every table pairs the complete result with the sensitivity excluding only `TS325_OD_2026-05-26_6mo_s01_112940_b0510`. Exclusion is a sensitivity, not the headline. Gross means absolute error >25 µm and is descriptive, not a deployment criterion.

| Surface / band | Median with / without (µm) | p95 with / without (µm) | Gross with / without | Eligible with / without |
|---|---:|---:|---:|---:|
| ILM | 1.57 / 1.44 | 33.88 / 5.84 | 0.0572 / 0.0085 | 3517 / 3164 |
| RNFL_GCL | 2.59 / 2.41 | 36.14 / 9.93 | 0.0566 / 0.0185 | 4580 / 4212 |
| GCL_IPL | 2.07 / 1.96 | 14.76 / 7.09 | 0.0437 / 0.0109 | 4580 / 4212 |
| IPL_INL | 2.74 / 2.46 | 85.26 / 21.04 | 0.1020 / 0.0406 | 4580 / 4212 |
| RNFL | 2.80 / 2.63 | 45.49 / 13.69 | 0.0694 / 0.0278 | 3517 / 3164 |
| GCL | 2.66 / 2.49 | 23.90 / 10.22 | 0.0493 / 0.0171 | 4580 / 4212 |
| IPL | 3.60 / 3.35 | 113.42 / 23.55 | 0.1094 / 0.0472 | 4580 / 4212 |
| INNER_RETINA | 3.25 / 2.81 | 140.23 / 26.68 | 0.1319 / 0.0547 | 3517 / 3164 |

### TS169

| Surface / band | Median with / without (µm) | p95 with / without (µm) | Gross with / without | Eligible with / without |
|---|---:|---:|---:|---:|
| ILM | 1.57 / 1.57 | 3.83 / 3.83 | 0.0029 / 0.0029 | 340 / 340 |
| RNFL_GCL | 2.11 / 2.11 | 9.35 / 9.35 | 0.0137 / 0.0137 | 1024 / 1024 |
| GCL_IPL | 1.84 / 1.84 | 6.30 / 6.30 | 0.0107 / 0.0107 | 1024 / 1024 |
| IPL_INL | 3.12 / 3.12 | 9.85 / 9.85 | 0.0234 / 0.0234 | 1024 / 1024 |
| RNFL | 2.94 / 2.94 | 9.95 / 9.95 | 0.0206 / 0.0206 | 340 / 340 |
| GCL | 2.34 / 2.34 | 9.96 / 9.96 | 0.0137 / 0.0137 | 1024 / 1024 |
| IPL | 3.45 / 3.45 | 12.12 / 12.12 | 0.0264 / 0.0264 | 1024 / 1024 |
| INNER_RETINA | 4.17 / 4.17 | 10.66 / 10.66 | 0.0147 / 0.0147 | 340 / 340 |

### TS325

| Surface / band | Median with / without (µm) | p95 with / without (µm) | Gross with / without | Eligible with / without |
|---|---:|---:|---:|---:|
| ILM | 1.57 / 1.43 | 42.01 / 6.07 | 0.0630 / 0.0092 | 3177 / 2824 |
| RNFL_GCL | 2.70 / 2.47 | 51.89 / 10.09 | 0.0689 / 0.0201 | 3556 / 3188 |
| GCL_IPL | 2.15 / 2.01 | 28.54 / 7.42 | 0.0531 / 0.0110 | 3556 / 3188 |
| IPL_INL | 2.61 / 2.29 | 120.78 / 24.02 | 0.1246 / 0.0461 | 3556 / 3188 |
| RNFL | 2.78 / 2.58 | 48.21 / 14.11 | 0.0746 / 0.0287 | 3177 / 2824 |
| GCL | 2.76 / 2.54 | 36.86 / 10.38 | 0.0596 / 0.0182 | 3556 / 3188 |
| IPL | 3.66 / 3.31 | 147.01 / 26.36 | 0.1333 / 0.0540 | 3556 / 3188 |
| INNER_RETINA | 3.11 / 2.66 | 151.06 / 28.25 | 0.1445 / 0.0595 | 3177 / 2824 |

Machine-readable raw and retained tables, per-animal and animal-macro rows, per-B-scan rows, and input fingerprints are in `baseline/`. Missing or withheld predictions remain in eligible denominators as failures. Conditional error is unavailable when no predictions exist; it is never interpreted as zero. No new thickness map was generated or interpolated.

## Classical comparison coverage

Stored auto covers all 14 eligible B-scans. Stored classical v2 covers 11/14 and has no TS169 predictions. `comparison/` contains complete-cohort and shared-available results separately, each with b0510 sensitivity. The three-way shared comparison is TS325-only. Missing TS169 predictions count as failures in the complete cohort.

### Shared-available TS325: v4

| Surface / band | Median with / without (µm) | p95 with / without (µm) | Gross with / without | Eligible with / without |
|---|---:|---:|---:|---:|
| ILM | 1.57 / 1.43 | 42.01 / 6.07 | 0.0630 / 0.0092 | 3177 / 2824 |
| RNFL_GCL | 2.70 / 2.47 | 51.89 / 10.09 | 0.0689 / 0.0201 | 3556 / 3188 |
| GCL_IPL | 2.15 / 2.01 | 28.54 / 7.42 | 0.0531 / 0.0110 | 3556 / 3188 |
| IPL_INL | 2.61 / 2.29 | 120.78 / 24.02 | 0.1246 / 0.0461 | 3556 / 3188 |
| RNFL | 2.78 / 2.58 | 48.21 / 14.11 | 0.0746 / 0.0287 | 3177 / 2824 |
| GCL | 2.76 / 2.54 | 36.86 / 10.38 | 0.0596 / 0.0182 | 3556 / 3188 |
| IPL | 3.66 / 3.31 | 147.01 / 26.36 | 0.1333 / 0.0540 | 3556 / 3188 |
| INNER_RETINA | 3.11 / 2.66 | 151.06 / 28.25 | 0.1445 / 0.0595 | 3177 / 2824 |

### Shared-available TS325: stored auto

| Surface / band | Median with / without (µm) | p95 with / without (µm) | Gross with / without | Eligible with / without |
|---|---:|---:|---:|---:|
| ILM | 0.00 / 0.00 | 45.95 / 53.40 | 0.0790 / 0.0889 | 3177 / 2824 |
| RNFL_GCL | 19.17 / 23.08 | 79.63 / 81.51 | 0.4154 / 0.4633 | 3556 / 3188 |
| GCL_IPL | 24.56 / 27.43 | 85.57 / 91.82 | 0.4935 / 0.5505 | 3556 / 3188 |
| IPL_INL | 2.42 / 2.22 | 107.75 / 113.60 | 0.1237 / 0.1380 | 3556 / 3188 |
| RNFL | 19.79 / 23.70 | 81.88 / 83.47 | 0.4221 / 0.4749 | 3177 / 2824 |
| GCL | 3.64 / 3.85 | 13.18 / 13.69 | 0.0048 / 0.0053 | 3556 / 3188 |
| IPL | 22.62 / 24.54 | 44.38 / 44.81 | 0.4384 / 0.4890 | 3556 / 3188 |
| INNER_RETINA | 2.77 / 2.73 | 114.92 / 116.35 | 0.2059 / 0.2316 | 3177 / 2824 |

### Shared-available TS325: classical v2

| Surface / band | Median with / without (µm) | p95 with / without (µm) | Gross with / without | Eligible with / without |
|---|---:|---:|---:|---:|
| ILM | 0.00 / 0.00 | 45.95 / 53.40 | 0.0790 / 0.0889 | 3177 / 2824 |
| RNFL_GCL | 15.32 / 11.20 | 38.29 / 34.96 | 0.2989 / 0.2180 | 3556 / 3188 |
| GCL_IPL | 14.99 / 12.89 | 40.40 / 37.54 | 0.3029 / 0.2224 | 3556 / 3188 |
| IPL_INL | 5.83 / 4.89 | 25.21 / 23.45 | 0.0523 / 0.0295 | 3556 / 3188 |
| RNFL | 18.77 / 15.70 | 51.51 / 54.35 | 0.3875 / 0.3109 | 3177 / 2824 |
| GCL | 4.14 / 4.20 | 11.44 / 11.48 | 0.0031 / 0.0035 | 3556 / 3188 |
| IPL | 9.68 / 8.58 | 25.73 / 25.77 | 0.0602 / 0.0602 | 3556 / 3188 |
| INNER_RETINA | 7.97 / 6.43 | 48.92 / 55.01 | 0.1287 / 0.1151 | 3177 / 2824 |

## Prerequisite cohort and manual-evidence policy

The permitted cohort contains **68 corrected B-scans, 17 volumes and 7 animals**, compared with 101/27/9 in the prompt. Final-test animal files were not opened. The final-test partition is unchanged.

| Animal | Corrected B-scans |
|---|---:|
| TS165 | 3 |
| TS169 | 3 |
| TS241 | 7 |
| TS250 | 4 |
| TS267 | 37 |
| TS305 | 3 |
| TS325 | 11 |

All 68 permitted corrected labels use legacy surface flags; none records local stroke provenance. The audit uses the existing `surface_flag` policy: edited, visible, reliable, non-excluded, non-displaced evidence, requiring independent manual evidence for both anchors and the predicted surface. An untouched automatic anchor is not promoted to manual ground truth. The surface-wide edit approximation still cannot establish which individual columns were drawn; that uncertainty remains unquantified. The descriptive manual audit does not add automatic-shadow or Stage A remote-footprint masks. The model baseline uses its original, stricter frozen Stage A masks; these are different denominators.

### Prior spread

Estimate: median of per-B-scan median positional fractions, then pooled p95 absolute positional residual; at least 20 usable columns per B-scan and anchor span >40 pixels. Both anchoring methods are also scored on identical eligible manual-anchor columns; the table below uses that matched cohort. The larger anchor-specific cohorts are saved separately in the CSV. These descriptive fractions were not installed as priors.

| Surface | Anchor | Manual B-scans / columns | Measured fraction | Residual p95 (px) | Prompt p95 (px) |
|---|---|---:|---:|---:|---:|
| RNFL_GCL | PR_RPE | 42 / 16601 | 0.3582 | 37.64 | 41.8 |
| RNFL_GCL | IPL_INL | 42 / 16601 | 0.5475 | 27.25 | 30.1 |
| GCL_IPL | PR_RPE | 37 / 14932 | 0.4153 | 35.03 | 40.1 |
| GCL_IPL | IPL_INL | 37 / 14932 | 0.6357 | 22.73 | 25.8 |

The spread reduction is similar in direction and relative size to the prompt, but it is a development-cohort measurement, not reproduction of the stated 101-label cohort.

### Scalar offset residuals

Subtract the median automatic-minus-manual offset within each B-scan or volume, then pool absolute residuals. This offset minimises absolute loss; it is not an asserted p95-optimal oracle. Both stored-auto and stored-v2 comparators are explicitly identified because they differ. The prompt supplies no original calculation script or fully specified oracle estimator. The quoted residuals do not reproduce under this documented calculation.

| Comparator | Surface | Offset unit | Compared / eligible columns | Residual p95 (px) | Prompt p95 (px) |
|---|---|---|---:|---:|---:|
| stored_auto | RNFL_GCL | bscan | 25223 / 25223 | 46.45 | 17.8 |
| stored_auto | RNFL_GCL | volume | 25223 / 25223 | 64.08 | 24.5 |
| stored_auto | GCL_IPL | bscan | 22754 / 22754 | 46.38 | 15.2 |
| stored_auto | GCL_IPL | volume | 22754 / 22754 | 61.40 | 22.6 |
| stored_v2 | RNFL_GCL | bscan | 14749 / 25223 | 57.04 | 17.8 |
| stored_v2 | RNFL_GCL | volume | 14749 / 25223 | 60.65 | 24.5 |
| stored_v2 | GCL_IPL | bscan | 13290 / 22754 | 51.38 | 15.2 |
| stored_v2 | GCL_IPL | volume | 13290 / 22754 | 57.69 | 22.6 |

### Lesion support

Six permitted corrected B-scans intersect a drawn footprint: 199 footprint columns, 139 non-excluded columns with at least one manually supported surface, and 96 columns with all four inner surfaces supported. Footprint intersection is read from the frozen manual-footprint-derived signed-distance arrays; it is not a segmentation-derived lesion. No within-lesion performance claim is made. These counts cannot reproduce the prompt's seven B-scans from nine animals while test animals remain locked.

## Historical execution status at the initial audit

| Item | Status |
|---|---|
| 1a: four-surface reporting and unchanged-checkpoint baseline | Implemented; measured |
| Three prerequisite measurements on the exact 101-label cohort | Not reproduced under the test lock; permitted-subset audit saved |
| 1b: classical prior refit and real-pipeline LOAO | Not run; no priors adopted |
| 1c: four-head training comparison | Not run; no win/loss conclusion is possible |
| Phase 2: constrained decoder comparison | Not started |
| Phase 3: calibration and review queue | Not started; no coverage guarantee or threshold may be quoted |

The attached prompt's cohort-mismatch stopping condition was superseded by the user's instruction to checkpoint and continue on the permitted development cohort. A seven-animal calibration would require model training that excludes each held-out animal; merely thresholding predictions from a model trained on that animal would not be valid LOAO.

## Verification and checkpoint compatibility

The new tests cover unchanged original metrics, INNER_RETINA endpoint eligibility, missing predictions, shadow withholding, four-head readout, per-B-scan run separation, exact sensitivity selection, legacy displacement exclusion and rejection of a test-split request before file access. Numerical and input-fingerprint verification is recorded in `verification.json`.

No file inside `code/stage_a/` was added or changed by this work. The tracked package matches both Git HEAD and the v4 checkpoint's recorded code identity. Additional untracked modules created in that directory during concurrent workspace work change the full directory hash, so the current checkout does not pass the existing training-resume guard. Those files were left untouched. `checkpoint_compatibility.json` records the observed hashes and additional filenames. This baseline analysis does not resume training or change the checkpoint.

## Reproduce

Activate `octa`, set `PYTHONPATH` to the repository's `code` directory, and use new empty output directories:

```powershell
python code/stage_a_inner_retina_audit.py --out outputs/stage_a/<new-run>/prerequisites_final
python code/stage_a_inner_retina.py --eval outputs/stage_a/20260908_v4_longtrain/dev_seed20260908/eval_validation --out outputs/stage_a/<new-run>/baseline
python code/stage_a_compare.py --scope inner-retina --evals unet_v4=outputs/stage_a/20260908_v4_longtrain/dev_seed20260908/eval_validation stored_auto=outputs/stage_a/20260908_v4_longtrain/baseline_validation v2=outputs/stage_a/20260908_v4_longtrain/v2_validation --out outputs/stage_a/<new-run>/comparison
python code/stage_a_inner_retina_report.py --out outputs/stage_a/<new-run>
python -m unittest -v test_stage_a_inner_retina
```
