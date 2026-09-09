# Phase 1 — completed experiments

Manual annotations are the only segmentation ground truth. Final-test animals remain locked. See [the complete report](RUN_REPORT.md) for shared provenance and verification.

## Phase 1c: equal-budget retraining

Both runs use the frozen five training animals and two eligible validation animals, 200 epochs × 48 updates, base width 8, AdamW learning rate 0.0003, region weight 0.1, and seed 20260908. Four heads select epoch 49 using four-boundary validation loss; eight heads use the delivered epoch 124 selected using the original eight-boundary loss. These are their respective validation-selected models, not a multi-seed architecture conclusion.

All values below are micrometres. Medians include b0510; every p95 is paired with its sensitivity excluding that one preidentified B-scan. Raw errors use the same frozen manual-reference columns; retained errors, coverage, gross errors, and missing-value denominators are also preserved in the machine-readable results.

| Surface / band | Existing 8: median | Four heads: median | Existing 8: p95 with / without b0510 | Four heads: p95 with / without b0510 |
|---|---:|---:|---:|---:|
| ILM | 1.57 | 1.60 | 33.88 / 5.84 | 151.86 / 21.12 |
| RNFL_GCL | 2.59 | 2.60 | 36.14 / 9.93 | 36.56 / 11.19 |
| GCL_IPL | 2.07 | 2.22 | 14.76 / 7.09 | 21.62 / 8.29 |
| IPL_INL | 2.74 | 2.44 | 85.26 / 21.04 | 119.54 / 14.71 |
| RNFL | 2.80 | 3.38 | 45.49 / 13.69 | 116.00 / 33.98 |
| GCL | 2.66 | 2.82 | 23.90 / 10.22 | 24.45 / 10.38 |
| IPL | 3.60 | 3.41 | 113.42 / 23.55 | 107.03 / 22.30 |
| INNER_RETINA | 3.25 | 2.97 | 140.23 / 26.68 | 142.51 / 42.70 |

### TS169

| Surface / band | Existing 8: median | Four heads: median | Existing 8: p95 with / without b0510 | Four heads: p95 with / without b0510 |
|---|---:|---:|---:|---:|
| ILM | 1.57 | 1.23 | 3.83 / 3.83 | 4.06 / 4.06 |
| RNFL_GCL | 2.11 | 2.31 | 9.35 / 9.35 | 11.14 / 11.14 |
| GCL_IPL | 1.84 | 1.65 | 6.30 / 6.30 | 13.94 / 13.94 |
| IPL_INL | 3.12 | 2.63 | 9.85 / 9.85 | 9.05 / 9.05 |
| RNFL | 2.94 | 3.76 | 9.95 / 9.95 | 26.14 / 26.14 |
| GCL | 2.34 | 2.14 | 9.96 / 9.96 | 11.55 / 11.55 |
| IPL | 3.45 | 3.00 | 12.12 / 12.12 | 15.59 / 15.59 |
| INNER_RETINA | 4.17 | 3.49 | 10.66 / 10.66 | 10.07 / 10.07 |

### TS325

| Surface / band | Existing 8: median | Four heads: median | Existing 8: p95 with / without b0510 | Four heads: p95 with / without b0510 |
|---|---:|---:|---:|---:|
| ILM | 1.57 | 1.65 | 42.01 / 6.07 | 158.87 / 26.61 |
| RNFL_GCL | 2.70 | 2.65 | 51.89 / 10.09 | 43.55 / 11.19 |
| GCL_IPL | 2.15 | 2.40 | 28.54 / 7.42 | 34.45 / 7.65 |
| IPL_INL | 2.61 | 2.41 | 120.78 / 24.02 | 160.79 / 15.65 |
| RNFL | 2.78 | 3.32 | 48.21 / 14.11 | 128.41 / 34.30 |
| GCL | 2.76 | 2.98 | 36.86 / 10.38 | 32.64 / 9.86 |
| IPL | 3.66 | 3.50 | 147.01 / 26.36 | 145.97 / 24.82 |
| INNER_RETINA | 3.11 | 2.87 | 151.06 / 28.25 | 147.86 / 54.72 |

The ILM/RNFL large-error tails worsened materially, including when b0510 is excluded. Improvements in IPL_INL and some IPL summaries do not establish an overall win. Eight heads are retained, with four reported.

![Manual reference and model comparison](examples_retraining/comparison_examples.png)

## Phase 1b: measured classical control

Each evaluation animal's two fractions are fitted using only the other permitted animals' manually supported ILM, inner boundary, and IPL_INL coordinates. The 17-volume calculation uses N=3 B-scan averaging and five-scan refinement with attraction 0.05. ILM and IPL_INL endpoint arrays are exactly unchanged between the two arms; IPL_INL is not refit.

| Surface / band | Original priors: median | Inner fractions: median | Original priors: p95 with / without b0510 | Inner fractions: p95 with / without b0510 |
|---|---:|---:|---:|---:|
| ILM | 0.00 | 0.00 | 34.62 / 35.54 | 34.62 / 35.54 |
| RNFL_GCL | 11.78 | 8.55 | 46.97 / 47.37 | 45.00 / 45.70 |
| GCL_IPL | 13.28 | 9.06 | 44.93 / 44.87 | 41.92 / 41.10 |
| IPL_INL | 4.75 | 4.75 | 28.41 / 28.17 | 28.41 / 28.17 |
| RNFL | 12.03 | 9.88 | 51.07 / 51.67 | 48.32 / 49.44 |
| GCL | 3.90 | 3.92 | 11.78 / 11.87 | 11.82 / 11.87 |
| IPL | 9.28 | 6.07 | 33.32 / 33.76 | 31.29 / 31.52 |
| INNER_RETINA | 5.72 | 5.72 | 51.52 / 52.96 | 51.52 / 52.96 |

This classical table covers the permitted corrected cohort (68 corrected B-scans; 62 Stage-A-eligible), whereas the neural architecture comparison covers 14 eligible validation B-scans. Do not compare the two pooled tables as if their cohorts were identical. `classical_validation/` provides the same validation cohort for direct comparisons.

The inner solver itself accepts only images, ILM/IPL_INL arrays, shadow, and two fractions. The unchanged old endpoint provider still depends on PR_RPE and carries prior fitting history, so the LOAO claim applies to the newly fitted fractions. The separate animal-excluded learned-endpoint control below tests an inference path that consumes no outer-surface coordinate.

On the same 14 eligible validation B-scans, GCL thickness median error rises from 3.868 to 4.376 µm; this is a negative result for the strict no-regression criterion despite the better RNFL_GCL/GCL_IPL boundary medians. All p95 values and the paired sensitivity are in `classical_validation/metrics.csv`.

## Prerequisite audit and baseline

The original prompt's 101/27/9 cohort is incompatible with keeping final-test animals locked. On 68 corrected B-scans from 17 volumes and seven permitted animals, matched-manual prior half-widths decrease from 37.64 to 27.25 px for RNFL_GCL and from 35.03 to 22.73 px for GCL_IPL. This reproduces the direction, not the original cohort counts.

The specified scalar-offset residuals did not reproduce under the documented median-offset calculation; the exact masks and offset convention were not specified in the prompt. Six permitted B-scans intersect a drawn lesion footprint (199 footprint columns; 139 with any manually supported inner surface; 96 with all four). No within-lesion claim is made.

See `PHASE_1_REPORT.md` for the historical full baseline and prerequisite audit, `baseline/` for frozen per-animal and sensitivity tables, and `comparison/` for stored classical comparators. Stored v2 predictions lack TS169 completely: their shared three-way comparison covers 11 of 14 eligible B-scans and is TS325-only.


### Additional control: learned endpoints without an outer coordinate

Seven animal-excluded networks supply only ILM and IPL_INL to the classical inner solver. Each network trains on five other animals. The two fractions use manual annotations from the other six animals, excluding the evaluated animal. The control is that same held-animal network's four inner predictions. Eight-head training still used outer auxiliary labels; no PR_RPE coordinate is consumed at inference. This is a hybrid, not an independently solved classical IPL_INL endpoint.

| Surface / band | Held-animal network: median | Same endpoints + classical inner costs: median | Held-animal network: p95 with / without b0510 | Same endpoints + classical inner costs: p95 with / without b0510 |
|---|---:|---:|---:|---:|
| ILM | 1.94 | 1.94 | 19.26 / 13.87 | 19.26 / 13.87 |
| RNFL_GCL | 2.75 | 6.46 | 20.77 / 17.31 | 36.67 / 36.34 |
| GCL_IPL | 2.65 | 6.30 | 18.92 / 13.88 | 35.44 / 34.66 |
| IPL_INL | 2.74 | 2.74 | 28.14 / 19.49 | 28.14 / 19.49 |
| RNFL | 3.64 | 7.79 | 35.74 / 28.25 | 41.57 / 41.99 |
| GCL | 3.09 | 3.82 | 18.74 / 16.23 | 12.49 / 12.56 |
| IPL | 3.61 | 6.84 | 38.98 / 27.10 | 32.41 / 31.85 |
| INNER_RETINA | 3.31 | 3.31 | 42.41 / 29.51 | 42.41 / 29.51 |

Both arms share exactly the same ILM/IPL_INL endpoint arrays. The classical costs retain N=3 averaging and attraction 0.05. Infeasible endpoint columns leave the two middle boundaries missing, and shadowed thickness remains missing. Pooled results cover the permitted corrected cohort; per-animal and raw/retained results are in `outer_free_hybrid_loao/metrics.csv`, with the identical 14-B-scan validation scope in `outer_free_hybrid_validation/`.

**Hybrid outcome: failed no-regression; not adopted.** RNFL_GCL median error rises from 2.745 to 6.464 µm and GCL_IPL from 2.653 to 6.303 µm. Only 95.45% and 95.47% of their eligible columns have finite hybrid predictions, respectively, versus 100% for the neural control. The hybrid's conditional errors must be read alongside those missing predictions. Some thickness tails improve, but they do not rescue the worse target-boundary errors and reduced coverage.

