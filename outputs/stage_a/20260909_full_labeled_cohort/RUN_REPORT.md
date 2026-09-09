# Full labeled-cohort run

**Status: completed.** No cohort choice or approval is pending.

The user explicitly authorized any/all labeled animals. A new dataset contains 102 corrected B-scans from nine animals and 27 volumes; 59 rejected decisions supply no position targets. The historical 101-label/27-volume/9-animal cohort is present exactly, plus one new annotation. Original datasets, labels, and checkpoints remain unchanged.

Only manual segmentation is ground truth. Exact recorded stroke columns are used for the new annotation; legacy labels use the documented edited-surface approximation. Untouched automatic surfaces, software displacement, invisibility, unreliability, image exclusions, out-of-image positions, and shadows are excluded. The segmentation skill and published layer thicknesses were not used as truth.

All manually supported regions are now available, irrespective of footprint status. The original Stage A remote/control mask is retained for a separate sensitivity analysis. Only eight labeled B-scans intersect footprint columns; this does not support a lesion-core reliability claim.

## What releasing the cohort means

Former test animals TS247 and TS283 now contribute manual evidence. The rejected-only TS328 contributes none. There is no untouched final-test set in this new experiment. The nine evaluation models each exclude their evaluated animal and a distinct calibration animal, training on the other seven. The separate all-label model trains on all nine and supplies experimental inference only. Its fit errors are never an independent accuracy estimate.

Training checkpoint: animal-excluded models 124/124 epochs; all-label model 124/124 epochs. Each epoch has 48 updates with uniform animal sampling, then uniform eligible B-scan sampling and optional lateral flipping. Eight boundary heads, base width 8, learning rate 0.0003, and region weight 0.1 are retained.

BF16 convolutions use less GPU memory; the objective and optimizer remain FP32. Faster GPU kernels are permitted, so a seed alone does not guarantee bitwise reproducibility. The source, data identities, sampling states, optimizer states, and every completed epoch are checkpointed. Two brief deterministic scheduling probes were discarded; the delivered run starts from its own fixed random initialization. `source_used/cv_training_source.py` is the exact source used.

The architecture decision comes from the earlier completed equal-budget [four-versus-eight-head experiment](../20260909_inner_retina_tier1/PHASE_1_COMPLETE.md): four heads lost. It was not repeated as an architecture sweep on the expanded cohort. The earlier [three-way decoder comparison](../20260909_inner_retina_tier1/PHASE_2_REPORT.md) also found little accuracy benefit from the much more expensive joint graph cut. This continuation evaluates the selected cheap DP control on all manual evidence. Those linked reports describe their historical cohort restrictions; the user's subsequent release applies to this new run.

## Manual-cohort audit

The exact historical 101-label subset has matched-manual prior residual half-widths 36.53→26.17 pixels for RNFL_GCL and 33.61→22.24 for GCL_IPL when the anchor changes from PR_RPE to IPL_INL. This confirms the direction of the conditioning improvement, but not the originally quoted 41.8/30.1 and 40.1/25.8 values. Masks and the median-of-B-scan-fractions estimator are documented in `prerequisites/`.

The scalar-offset residual figures also do not reproduce under the explicit median-offset convention. `oracle_offsets.csv` preserves the measurements and missing-prediction denominators; no number was adjusted to match the prompt. The current 102-label footprint audit counts 235 footprint A-lines, with only 96 supported at all four inner boundaries. These are descriptive counts, not lesion accuracy evidence.

## Original model on the expanded cohort

The unchanged v4 model is a descriptive comparator. Five animals contributed its training and two its validation/checkpoint selection; its pooled full-cohort performance is not independent. Historical test animals are tabulated separately, and b0510 sensitivity accompanies all pooled p95 values. Every value below is in micrometres.

### TS247 and TS283: absent from original model development

| Surface / band | Original soft: median | Original + ordered DP: median | Original soft: p95 with / without b0510 | Original + ordered DP: p95 with / without b0510 |
|---|---:|---:|---:|---:|
| ILM | 2.48 | 2.24 | 20.47 / 20.47 | 17.90 / 17.90 |
| RNFL_GCL | 2.75 | 2.69 | 45.58 / 45.58 | 12.89 / 12.89 |
| GCL_IPL | 2.24 | 2.25 | 40.05 / 40.05 | 15.85 / 15.85 |
| IPL_INL | 2.90 | 2.86 | 81.97 / 81.97 | 26.62 / 26.62 |
| RNFL | 4.58 | 4.02 | 51.33 / 51.33 | 26.50 / 26.50 |
| GCL | 3.11 | 3.06 | 31.34 / 31.34 | 11.53 / 11.53 |
| IPL | 3.97 | 3.88 | 62.38 / 62.38 | 27.23 / 27.23 |
| INNER_RETINA | 4.11 | 4.11 | 83.42 / 83.42 | 33.10 / 33.10 |

![Expanded manual cohort compared with unchanged v4](examples_expanded_cohort/comparison_examples.png)

## Classical inner-prior comparison

The two fractions are fitted excluding the evaluated animal. Both arms share the original v2 ILM/IPL_INL endpoint provider; its inherited global fitting history prevents a whole-pipeline independence claim. N=3 averaging and attraction 0.05 are unchanged. IPL_INL is not refit.

| Surface / band | Original priors: median | Inner fractions: median | Original priors: p95 with / without b0510 | Inner fractions: p95 with / without b0510 |
|---|---:|---:|---:|---:|
| ILM | 0.00 | 0.00 | 89.45 / 90.34 | 89.45 / 90.34 |
| RNFL_GCL | 12.99 | 9.53 | 57.52 / 57.75 | 60.56 / 60.66 |
| GCL_IPL | 13.40 | 8.68 | 53.81 / 53.94 | 54.66 / 54.82 |
| IPL_INL | 4.48 | 4.48 | 37.43 / 37.75 | 37.43 / 37.75 |
| RNFL | 14.39 | 11.07 | 76.05 / 76.25 | 77.52 / 78.04 |
| GCL | 4.06 | 4.06 | 12.13 / 12.17 | 11.98 / 12.02 |
| IPL | 9.94 | 5.99 | 37.79 / 38.07 | 34.42 / 34.59 |
| INNER_RETINA | 6.55 | 6.55 | 108.05 / 108.81 | 108.05 / 108.81 |

The inner-boundary medians improve, while GCL thickness median changes from 4.056 to 4.065 µm. This is not a strict no-regression pass. A zero classical ILM median must also be read in light of the shared legacy labeling/endpoint history; it is not an independent validation claim. No production prior was changed.

## Animal-excluded decoder comparison

These are raw errors from models that never trained on the evaluated animal, against all manually supported columns. Retained errors and coverage are separate; unlabelled image regions cannot establish accuracy.

| Surface / band | Held-animal soft: median | Held-animal DP: median | Held-animal soft: p95 with / without b0510 | Held-animal DP: p95 with / without b0510 |
|---|---:|---:|---:|---:|
| ILM | 1.89 | 1.94 | 11.92 / 10.46 | 9.49 / 9.51 |
| RNFL_GCL | 2.57 | 2.47 | 22.80 / 20.31 | 12.67 / 12.75 |
| GCL_IPL | 2.37 | 2.35 | 17.54 / 15.53 | 11.82 / 11.93 |
| IPL_INL | 2.74 | 2.69 | 22.07 / 18.71 | 12.24 / 12.27 |
| RNFL | 3.58 | 3.36 | 33.42 / 28.98 | 20.93 / 21.21 |
| GCL | 2.83 | 2.84 | 20.85 / 19.33 | 11.72 / 11.76 |
| IPL | 3.51 | 3.46 | 30.89 / 26.84 | 18.15 / 18.30 |
| INNER_RETINA | 3.34 | 3.34 | 31.33 / 26.08 | 18.55 / 18.75 |

soft: 7,751 crossing A-lines / 52,224 across all 102 manually supported B-scans.
dp_project: 0 crossing A-lines / 52,224 across all 102 manually supported B-scans.

Strict no-regression result: FAILED for median error, p95 error, gross-error fraction, and finite-prediction coverage across pooled and per-animal rows, with both b0510 sensitivities. There are 95 worsened metric cells, listed without rounding away differences in `strict_regressions.csv` (numerical tolerance 0.000001). Numerical comparison alone is not a deployment validation.

### Original Stage A remote/control scope only

| Surface / band | Held-animal soft: median | Held-animal DP: median | Held-animal soft: p95 with / without b0510 | Held-animal DP: p95 with / without b0510 |
|---|---:|---:|---:|---:|
| ILM | 1.83 | 1.79 | 14.18 / 11.33 | 10.08 / 10.14 |
| RNFL_GCL | 2.60 | 2.50 | 22.75 / 19.82 | 11.37 / 11.43 |
| GCL_IPL | 2.42 | 2.39 | 18.06 / 15.26 | 10.81 / 10.92 |
| IPL_INL | 2.66 | 2.60 | 26.26 / 20.98 | 12.15 / 12.18 |
| RNFL | 3.57 | 3.33 | 31.64 / 26.12 | 17.53 / 17.86 |
| GCL | 2.89 | 2.89 | 20.04 / 17.64 | 12.17 / 12.27 |
| IPL | 3.54 | 3.47 | 30.45 / 25.55 | 15.97 / 16.16 |
| INNER_RETINA | 3.35 | 3.32 | 36.26 / 27.29 | 18.30 / 18.53 |

### TS165

| Surface / band | Held-animal soft: median | Held-animal DP: median | Held-animal soft: p95 with / without b0510 | Held-animal DP: p95 with / without b0510 |
|---|---:|---:|---:|---:|
| ILM | 3.00 | 2.69 | 10.07 / 10.07 | 8.96 / 8.96 |
| RNFL_GCL | 4.30 | 4.06 | 38.63 / 38.63 | 18.31 / 18.31 |
| GCL_IPL | 3.83 | 3.98 | 14.54 / 14.54 | 14.60 / 14.60 |
| IPL_INL | 6.10 | 4.89 | 34.62 / 34.62 | 22.99 / 22.99 |
| RNFL | 8.01 | 6.16 | 41.83 / 41.83 | 17.01 / 17.01 |
| GCL | 3.62 | 3.52 | 29.65 / 29.65 | 17.05 / 17.05 |
| IPL | 11.01 | 6.88 | 42.72 / 42.72 | 26.26 / 26.26 |
| INNER_RETINA | 7.98 | 5.37 | 38.77 / 38.77 | 23.63 / 23.63 |

### TS169

| Surface / band | Held-animal soft: median | Held-animal DP: median | Held-animal soft: p95 with / without b0510 | Held-animal DP: p95 with / without b0510 |
|---|---:|---:|---:|---:|
| ILM | 1.36 | 1.12 | 3.53 / 3.53 | 3.36 / 3.36 |
| RNFL_GCL | 2.34 | 2.32 | 7.91 / 7.91 | 7.49 / 7.49 |
| GCL_IPL | 1.44 | 1.57 | 5.27 / 5.27 | 5.28 / 5.28 |
| IPL_INL | 2.77 | 2.78 | 7.15 / 7.15 | 6.88 / 6.88 |
| RNFL | 2.98 | 3.09 | 7.94 / 7.94 | 7.72 / 7.72 |
| GCL | 2.48 | 2.57 | 8.38 / 8.38 | 8.46 / 8.46 |
| IPL | 2.87 | 2.94 | 7.56 / 7.56 | 7.54 / 7.54 |
| INNER_RETINA | 3.80 | 3.47 | 10.81 / 10.81 | 10.61 / 10.61 |

### TS241

| Surface / band | Held-animal soft: median | Held-animal DP: median | Held-animal soft: p95 with / without b0510 | Held-animal DP: p95 with / without b0510 |
|---|---:|---:|---:|---:|
| ILM | 2.28 | 2.24 | 7.73 / 7.73 | 8.33 / 8.33 |
| RNFL_GCL | 3.03 | 3.02 | 17.04 / 17.04 | 14.32 / 14.32 |
| GCL_IPL | 2.14 | 2.20 | 10.28 / 10.28 | 8.76 / 8.76 |
| IPL_INL | 3.20 | 3.20 | 12.02 / 12.02 | 10.57 / 10.57 |
| RNFL | 4.30 | 4.28 | 20.69 / 20.69 | 18.77 / 18.77 |
| GCL | 3.41 | 3.47 | 13.21 / 13.21 | 11.70 / 11.70 |
| IPL | 3.48 | 3.48 | 15.13 / 15.13 | 13.03 / 13.03 |
| INNER_RETINA | 3.72 | 3.60 | 13.39 / 13.39 | 13.34 / 13.34 |

### TS247

| Surface / band | Held-animal soft: median | Held-animal DP: median | Held-animal soft: p95 with / without b0510 | Held-animal DP: p95 with / without b0510 |
|---|---:|---:|---:|---:|
| ILM | 2.58 | 2.24 | 14.41 / 14.41 | 18.91 / 18.91 |
| RNFL_GCL | 2.36 | 2.25 | 23.51 / 23.51 | 13.15 / 13.15 |
| GCL_IPL | 2.35 | 2.31 | 33.23 / 33.23 | 14.34 / 14.34 |
| IPL_INL | 2.51 | 2.45 | 57.70 / 57.70 | 21.42 / 21.42 |
| RNFL | 4.10 | 3.90 | 30.08 / 30.08 | 27.12 / 27.12 |
| GCL | 2.79 | 2.77 | 24.56 / 24.56 | 13.29 / 13.29 |
| IPL | 3.84 | 3.67 | 32.59 / 32.59 | 19.77 / 19.77 |
| INNER_RETINA | 3.53 | 3.68 | 68.22 / 68.22 | 29.94 / 29.94 |

### TS250

| Surface / band | Held-animal soft: median | Held-animal DP: median | Held-animal soft: p95 with / without b0510 | Held-animal DP: p95 with / without b0510 |
|---|---:|---:|---:|---:|
| ILM | 1.14 | 1.12 | 5.24 / 5.24 | 5.48 / 5.48 |
| RNFL_GCL | 3.84 | 3.86 | 18.93 / 18.93 | 25.31 / 25.31 |
| GCL_IPL | 2.48 | 2.53 | 21.50 / 21.50 | 18.25 / 18.25 |
| IPL_INL | 1.88 | 1.99 | 8.92 / 8.92 | 9.08 / 9.08 |
| RNFL | 4.60 | 3.95 | 14.70 / 14.70 | 14.82 / 14.82 |
| GCL | 3.75 | 3.74 | 14.76 / 14.76 | 12.59 / 12.59 |
| IPL | 4.33 | 4.34 | 16.37 / 16.37 | 15.77 / 15.77 |
| INNER_RETINA | 2.49 | 2.24 | 6.11 / 6.11 | 6.33 / 6.33 |

### TS267

| Surface / band | Held-animal soft: median | Held-animal DP: median | Held-animal soft: p95 with / without b0510 | Held-animal DP: p95 with / without b0510 |
|---|---:|---:|---:|---:|
| ILM | 1.87 | 1.90 | 9.37 / 9.37 | 7.56 / 7.56 |
| RNFL_GCL | 2.58 | 2.55 | 26.81 / 26.81 | 14.82 / 14.82 |
| GCL_IPL | 2.47 | 2.52 | 13.47 / 13.47 | 13.20 / 13.20 |
| IPL_INL | 2.77 | 2.70 | 13.20 / 13.20 | 10.81 / 10.81 |
| RNFL | 3.51 | 3.51 | 44.71 / 44.71 | 30.53 / 30.53 |
| GCL | 2.90 | 3.00 | 19.37 / 19.37 | 10.98 / 10.98 |
| IPL | 3.12 | 3.20 | 28.17 / 28.17 | 23.58 / 23.58 |
| INNER_RETINA | 3.34 | 3.36 | 19.60 / 19.60 | 15.43 / 15.43 |

### TS283

| Surface / band | Held-animal soft: median | Held-animal DP: median | Held-animal soft: p95 with / without b0510 | Held-animal DP: p95 with / without b0510 |
|---|---:|---:|---:|---:|
| ILM | 1.73 | 1.77 | 9.76 / 9.76 | 8.30 / 8.30 |
| RNFL_GCL | 2.69 | 2.47 | 18.66 / 18.66 | 12.28 / 12.28 |
| GCL_IPL | 2.40 | 2.24 | 21.63 / 21.63 | 15.66 / 15.66 |
| IPL_INL | 3.45 | 3.72 | 16.54 / 16.54 | 14.48 / 14.48 |
| RNFL | 2.93 | 2.60 | 24.44 / 24.44 | 13.86 / 13.86 |
| GCL | 2.53 | 2.34 | 26.50 / 26.50 | 11.65 / 11.65 |
| IPL | 3.46 | 3.85 | 23.85 / 23.85 | 24.70 / 24.70 |
| INNER_RETINA | 3.41 | 3.41 | 21.82 / 21.82 | 18.62 / 18.62 |

### TS305

| Surface / band | Held-animal soft: median | Held-animal DP: median | Held-animal soft: p95 with / without b0510 | Held-animal DP: p95 with / without b0510 |
|---|---:|---:|---:|---:|
| ILM | 2.00 | 1.12 | 16.02 / 16.02 | 4.48 / 4.48 |
| RNFL_GCL | 2.25 | 2.08 | 7.31 / 7.31 | 6.78 / 6.78 |
| GCL_IPL | 3.07 | 2.86 | 9.41 / 9.41 | 8.22 / 8.22 |
| IPL_INL | 2.11 | 2.24 | 10.26 / 10.26 | 5.60 / 5.60 |
| RNFL | 2.14 | 2.76 | 14.52 / 14.52 | 7.84 / 7.84 |
| GCL | 2.46 | 2.45 | 7.71 / 7.71 | 7.16 / 7.16 |
| IPL | 3.99 | 3.64 | 14.97 / 14.97 | 8.64 / 8.64 |
| INNER_RETINA | 3.52 | 2.24 | 41.64 / 41.64 | 6.72 / 6.72 |

### TS325

| Surface / band | Held-animal soft: median | Held-animal DP: median | Held-animal soft: p95 with / without b0510 | Held-animal DP: p95 with / without b0510 |
|---|---:|---:|---:|---:|
| ILM | 1.21 | 1.12 | 70.75 / 6.49 | 4.80 / 4.48 |
| RNFL_GCL | 2.42 | 2.10 | 26.43 / 10.07 | 7.61 / 7.75 |
| GCL_IPL | 2.12 | 2.08 | 24.85 / 8.51 | 7.28 / 7.58 |
| IPL_INL | 2.37 | 2.24 | 74.50 / 9.08 | 10.12 / 9.72 |
| RNFL | 2.94 | 2.47 | 55.92 / 13.00 | 8.87 / 8.61 |
| GCL | 2.62 | 2.44 | 30.15 / 17.70 | 8.59 / 9.15 |
| IPL | 2.94 | 2.90 | 77.57 / 17.78 | 11.90 / 11.72 |
| INNER_RETINA | 2.52 | 2.32 | 77.78 / 16.93 | 11.39 / 10.96 |

## Transfer of uncertainty thresholds between animals

Each cutoff is set using another calibration animal and then evaluated on the held animal. The tables show per-animal ranges at the 90th calibration percentile, not a promise of 90% retained coverage. All curves, denominators, zero-coverage cases, and both b0510 sensitivities remain in the CSV files. Error summaries are conditional on retaining a prediction.

### Ordered DP

| Surface / band | Coverage range with / without b0510 (%) | Retained p95 range with / without b0510 (µm) |
|---|---:|---:|
| ILM | 70.4–99.0 / 70.4–99.0 | 3.36–9.84 / 3.36–9.84 |
| RNFL_GCL | 73.0–97.5 / 73.0–98.0 | 6.65–12.31 / 6.65–12.31 |
| GCL_IPL | 74.9–96.7 / 74.9–96.8 | 4.97–13.17 / 4.97–13.17 |
| IPL_INL | 45.4–97.4 / 45.4–97.4 | 5.60–11.18 / 5.60–11.18 |
| RNFL | 54.2–98.5 / 54.2–98.5 | 7.44–19.61 / 7.44–19.61 |
| GCL | 64.8–96.3 / 64.8–96.8 | 7.06–16.23 / 7.06–16.23 |
| IPL | 40.8–93.2 / 40.8–94.3 | 7.46–17.46 / 7.46–17.46 |
| INNER_RETINA | 26.3–98.5 / 26.3–98.5 | 5.60–17.15 / 5.60–17.15 |

![Ordered DP: boundary coverage and error](calibration_dp/coverage_error_boundaries.png)

![Ordered DP: thickness coverage and error](calibration_dp/coverage_error_thickness.png)

### Original soft estimator

| Surface / band | Coverage range with / without b0510 (%) | Retained p95 range with / without b0510 (µm) |
|---|---:|---:|
| ILM | 70.4–99.0 / 70.4–99.0 | 3.34–26.68 / 3.34–10.02 |
| RNFL_GCL | 72.5–95.8 / 72.5–96.5 | 6.46–12.67 / 6.46–12.67 |
| GCL_IPL | 74.9–95.5 / 74.9–95.7 | 4.71–12.37 / 4.71–12.37 |
| IPL_INL | 41.2–97.4 / 41.2–97.4 | 5.62–10.23 / 5.62–10.23 |
| RNFL | 54.2–98.5 / 54.2–98.5 | 7.16–17.53 / 7.16–17.00 |
| GCL | 64.8–93.2 / 64.8–95.2 | 6.57–15.49 / 6.57–15.49 |
| IPL | 36.6–92.9 / 36.6–92.9 | 7.38–15.19 / 7.38–15.19 |
| INNER_RETINA | 25.1–98.5 / 25.1–98.5 | 5.86–12.26 / 5.86–12.26 |

![Original soft estimator: boundary coverage and error](calibration_soft/coverage_error_boundaries.png)

![Original soft estimator: thickness coverage and error](calibration_soft/coverage_error_thickness.png)

No universal deployment threshold is adopted from this small development cohort. The review workflow uses a per-volume entropy quantile as an experimental workload rule. It does not guarantee measurement accuracy or quantify human time saved.

## Inner solver with no outer-surface coordinate

Both arms share held-animal learned ILM/IPL_INL endpoints. The hybrid uses classical costs and two manual fractions fitted from the other eight animals; its endpoint network uses seven training animals. PR_RPE coordinates are not consumed, although the eight-head network retains outer auxiliary supervision. Missing or infeasible endpoints remain missing.

| Surface / band | Held-animal network: median | Same endpoints + classical costs: median | Held-animal network: p95 with / without b0510 | Same endpoints + classical costs: p95 with / without b0510 |
|---|---:|---:|---:|---:|
| ILM | 1.89 | 1.89 | 11.92 / 10.46 | 11.92 / 10.46 |
| RNFL_GCL | 2.57 | 7.05 | 22.80 / 20.31 | 38.68 / 38.74 |
| GCL_IPL | 2.37 | 6.62 | 17.54 / 15.53 | 35.58 / 35.58 |
| IPL_INL | 2.74 | 2.74 | 22.07 / 18.71 | 22.07 / 18.71 |
| RNFL | 3.58 | 8.58 | 33.42 / 28.98 | 39.87 / 39.98 |
| GCL | 2.83 | 3.98 | 20.85 / 19.33 | 11.88 / 11.90 |
| IPL | 3.51 | 7.73 | 30.89 / 26.84 | 34.42 / 34.40 |
| INNER_RETINA | 3.34 | 3.34 | 31.33 / 26.08 | 31.33 / 26.08 |

Strict no-regression result: FAILED; 306 worsened metric cells are recorded in `outer_free_hybrid_loao/strict_regressions.csv`. The hybrid is not adopted. The complete raw/retained per-animal tables and finite-prediction coverage are in `outer_free_hybrid_loao/metrics.csv`. This experimental control does not change the original classical endpoint provider or its IPL_INL prior.

## All-label inference model: fit diagnostic only

The separate ALL_LABELLED model uses every one of the nine manually supported animals. The following is an IN-SAMPLE fit check, not an independent error or deployment-coverage estimate. It is supplied to make the saved inference model reviewable.

| Surface / band | In-sample soft: median | In-sample DP: median | In-sample soft: p95 with / without b0510 | In-sample DP: p95 with / without b0510 |
|---|---:|---:|---:|---:|
| ILM | 1.44 | 1.16 | 6.86 / 6.35 | 6.14 / 6.15 |
| RNFL_GCL | 1.70 | 1.70 | 7.54 / 7.20 | 6.93 / 6.93 |
| GCL_IPL | 1.59 | 1.61 | 6.97 / 6.79 | 6.78 / 6.82 |
| IPL_INL | 1.78 | 1.81 | 7.76 / 7.30 | 7.40 / 7.34 |
| RNFL | 2.41 | 2.39 | 10.79 / 10.07 | 9.94 / 9.94 |
| GCL | 2.18 | 2.19 | 8.00 / 7.84 | 7.74 / 7.74 |
| IPL | 2.35 | 2.36 | 9.56 / 9.02 | 9.13 / 9.00 |
| INNER_RETINA | 2.32 | 2.30 | 10.33 / 9.68 | 9.53 / 9.54 |

## Completed full-volume outputs and human-review packs

| Volume | B-scans | Raw crossings | Ordered crossings | New review candidates |
|---|---:|---:|---:|---:|
| TS165_OS_2025-04-29_WT_s02_121711 | 512 | 52,409 | 0 | 9 |
| TS247_OD_2024-11-06_D21_s03_104157 | 512 | 34,824 | 0 | 9 |
| TS283_OD_2025-01-29_D7_s02_123712 | 512 | 52,812 | 0 | 9 |
| TS325_OD_2026-05-26_6mo_s01_112940 | 512 | 94,987 | 0 | 9 |

Every candidate is an unreviewed automatic proposal. The queue retains the original Stage A remote/control volume mask, keeps acquisition QC separate, and excludes existing reviewed B-scans. The longest flagged run is an uncertainty/crossing proxy; a true gross-error run is unknowable without manual reference.

Shadowed thickness is NaN. Unsupported INL, OPL, PHOTORECEPTOR, RPE, and full-retina TOTAL are explicitly unreliable/NaN rather than silently dropped. The experimental measurements cover four complete volumes, not the full 314-scan acquisition inventory.

![New review candidates from the all-label model](review_queue/review_examples.png)

## Held-animal predictions

![Held-animal predictions](examples_held_animal/comparison_examples.png)

## All-label model fit; not independent validation

![All-label model fit; not independent validation](examples_all_label_fit/comparison_examples.png)

## The additional annotation with exact stroke provenance

![The additional annotation with exact stroke provenance](examples_new_manual_strokes/comparison_examples.png)

## Saved outputs and verification

- Frozen labels and derived image/target identities: `data/`.
- Nine animal-excluded models and the separate all-label inference model: `cv_full_cohort/`.
- Accuracy measured on excluded animals: `held_animal_comparison/` and `calibration_dp/`, with the original soft control in `calibration_soft/`.
- Experimental volume arrays and GUI-compatible packs: `review_queue/`.
- The previous Tier 1 report remains a historical seven-animal checkpoint. Its old locked-test description does not govern this explicitly authorized full-cohort run.

All final identity, animal-exclusion, numerical reload, and actual-GUI-reader checks passed. Manual label files and the original v4 checkpoint/code identity are unchanged. `verification_complete.json` records the checks and their limits.
