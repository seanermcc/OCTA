# Inner-retina Tier 1 — current execution report

Checkpoints are outputs, not approval gates. The user's clarification supersedes the attached prompt's cohort-mismatch stopping instruction. Work uses the seven permitted development animals; final-test animals stay locked.

Only manual annotations supply segmentation ground truth. The layer-segmentation skill and published thickness tables were not used for fitting, scoring, or acceptance. Legacy labels identify edited surfaces but not individual strokes; eligible surface-wide columns remain an imperfect approximation of what was drawn.

## Decisions reached

- Reporting now uses ILM, RNFL_GCL, GCL_IPL, IPL_INL, RNFL, GCL, IPL, and INNER_RETINA.
- Keep the existing eight-head v4 model. The single-seed, equal-budget four-head experiment failed the no-regression criterion.
- The two classical inner fractions improved their target-boundary errors under a matched-endpoint LOAO comparison, but GCL thickness worsened on the matched validation cohort. No production prior was changed.
- The constrained decoder eliminates crossings and markedly improves the worst example, but fails the strict no-regression rule. The cheaper ordered DP is available for experimental human review.
- Held-animal calibration measures large variation in retained coverage. The saved review queue uses per-volume quantiles for triage, without a universal accuracy guarantee.

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

## Phase 2: decoder comparison

### dp_project

| Surface / band | Existing 8: median | dp_project: median | Existing 8: p95 with / without b0510 | dp_project: p95 with / without b0510 |
|---|---:|---:|---:|---:|
| ILM | 1.57 | 1.16 | 33.88 / 5.84 | 5.22 / 4.65 |
| RNFL_GCL | 2.59 | 2.48 | 36.14 / 9.93 | 8.89 / 9.02 |
| GCL_IPL | 2.07 | 2.04 | 14.76 / 7.09 | 7.03 / 6.52 |
| IPL_INL | 2.74 | 2.43 | 85.26 / 21.04 | 8.97 / 8.53 |
| RNFL | 2.80 | 2.71 | 45.49 / 13.69 | 10.10 / 10.04 |
| GCL | 2.66 | 2.58 | 23.90 / 10.22 | 8.91 / 9.21 |
| IPL | 3.60 | 3.28 | 113.42 / 23.55 | 11.15 / 10.40 |
| INNER_RETINA | 3.25 | 2.70 | 140.23 / 26.68 | 12.01 / 11.38 |

#### TS169

| Surface / band | Existing 8: median | dp_project: median | Existing 8: p95 with / without b0510 | dp_project: p95 with / without b0510 |
|---|---:|---:|---:|---:|
| ILM | 1.57 | 1.12 | 3.83 / 3.83 | 3.36 / 3.36 |
| RNFL_GCL | 2.11 | 2.14 | 9.35 / 9.35 | 9.09 / 9.09 |
| GCL_IPL | 1.84 | 1.79 | 6.30 / 6.30 | 5.79 / 5.79 |
| IPL_INL | 3.12 | 2.94 | 9.85 / 9.85 | 8.48 / 8.48 |
| RNFL | 2.94 | 2.91 | 9.95 / 9.95 | 9.73 / 9.73 |
| GCL | 2.34 | 2.38 | 9.96 / 9.96 | 9.87 / 9.87 |
| IPL | 3.45 | 3.42 | 12.12 / 12.12 | 9.58 / 9.58 |
| INNER_RETINA | 4.17 | 4.40 | 10.66 / 10.66 | 10.61 / 10.61 |

#### TS325

| Surface / band | Existing 8: median | dp_project: median | Existing 8: p95 with / without b0510 | dp_project: p95 with / without b0510 |
|---|---:|---:|---:|---:|
| ILM | 1.57 | 1.18 | 42.01 / 6.07 | 5.54 / 4.83 |
| RNFL_GCL | 2.70 | 2.56 | 51.89 / 10.09 | 8.57 / 8.86 |
| GCL_IPL | 2.15 | 2.12 | 28.54 / 7.42 | 7.37 / 6.72 |
| IPL_INL | 2.61 | 2.30 | 120.78 / 24.02 | 9.15 / 8.56 |
| RNFL | 2.78 | 2.69 | 48.21 / 14.11 | 10.13 / 10.08 |
| GCL | 2.76 | 2.61 | 36.86 / 10.38 | 8.46 / 8.73 |
| IPL | 3.66 | 3.24 | 147.01 / 26.36 | 11.42 / 10.62 |
| INNER_RETINA | 3.11 | 2.60 | 151.06 / 28.25 | 12.69 / 11.64 |

### graph_cut

| Surface / band | Existing 8: median | graph_cut: median | Existing 8: p95 with / without b0510 | graph_cut: p95 with / without b0510 |
|---|---:|---:|---:|---:|
| ILM | 1.57 | 1.16 | 33.88 / 5.84 | 5.22 / 4.65 |
| RNFL_GCL | 2.59 | 2.48 | 36.14 / 9.93 | 8.89 / 9.02 |
| GCL_IPL | 2.07 | 2.03 | 14.76 / 7.09 | 7.04 / 6.52 |
| IPL_INL | 2.74 | 2.42 | 85.26 / 21.04 | 8.96 / 8.38 |
| RNFL | 2.80 | 2.71 | 45.49 / 13.69 | 10.10 / 10.04 |
| GCL | 2.66 | 2.58 | 23.90 / 10.22 | 8.95 / 9.22 |
| IPL | 3.60 | 3.28 | 113.42 / 23.55 | 11.08 / 10.32 |
| INNER_RETINA | 3.25 | 2.70 | 140.23 / 26.68 | 11.86 / 11.33 |

#### TS169

| Surface / band | Existing 8: median | graph_cut: median | Existing 8: p95 with / without b0510 | graph_cut: p95 with / without b0510 |
|---|---:|---:|---:|---:|
| ILM | 1.57 | 1.12 | 3.83 / 3.83 | 3.36 / 3.36 |
| RNFL_GCL | 2.11 | 2.14 | 9.35 / 9.35 | 9.09 / 9.09 |
| GCL_IPL | 1.84 | 1.78 | 6.30 / 6.30 | 5.79 / 5.79 |
| IPL_INL | 3.12 | 2.89 | 9.85 / 9.85 | 8.38 / 8.38 |
| RNFL | 2.94 | 2.91 | 9.95 / 9.95 | 9.73 / 9.73 |
| GCL | 2.34 | 2.38 | 9.96 / 9.96 | 9.87 / 9.87 |
| IPL | 3.45 | 3.43 | 12.12 / 12.12 | 9.28 / 9.28 |
| INNER_RETINA | 4.17 | 4.40 | 10.66 / 10.66 | 10.61 / 10.61 |

#### TS325

| Surface / band | Existing 8: median | graph_cut: median | Existing 8: p95 with / without b0510 | graph_cut: p95 with / without b0510 |
|---|---:|---:|---:|---:|
| ILM | 1.57 | 1.18 | 42.01 / 6.07 | 5.54 / 4.83 |
| RNFL_GCL | 2.70 | 2.56 | 51.89 / 10.09 | 8.57 / 8.86 |
| GCL_IPL | 2.15 | 2.12 | 28.54 / 7.42 | 7.41 / 6.72 |
| IPL_INL | 2.61 | 2.29 | 120.78 / 24.02 | 9.11 / 8.50 |
| RNFL | 2.78 | 2.69 | 48.21 / 14.11 | 10.13 / 10.08 |
| GCL | 2.76 | 2.61 | 36.86 / 10.38 | 8.50 / 8.73 |
| IPL | 3.66 | 3.24 | 147.01 / 26.36 | 11.42 / 10.61 |
| INNER_RETINA | 3.11 | 2.60 | 151.06 / 28.25 | 12.56 / 11.56 |

Across every one of the 14 manually supported validation B-scans, crossing A-line counts are {'soft': 1384, 'dp_project': 0, 'graph_cut': 0}. The denominator is 7,168 distinct A-lines. The other 24 validation decisions have no eligible manual targets and are not part of this accuracy comparison. This denominator also differs from the old boundary-column denominator.

**Strict phase-2 no-regression criterion: failed.** Both constrained estimators improve the pooled medians and tails including b0510, but RNFL_GCL median error for TS169 rises from 2.106 to 2.143 µm and the pooled sensitivity without b0510 rises from 2.408 to 2.443 µm. TS169 INNER_RETINA median also rises from 4.165 to 4.398 µm. These small tradeoffs are reported, not rounded into a pass.

**Experimental workflow choice: ordered DP plus minimum-gap projection.** The graph cut gives very similar manual-reference errors and substantially greater computational cost. It has not earned adoption over the cheaper control. The original soft estimator remains the scientific baseline; constrained candidates and measurements remain experimental.

![Manual reference and decoder comparison](examples_decoders/comparison_examples.png)

Large movements (>5 pixels) affect 7.8% of eligible ILM columns, 8.7% RNFL_GCL, 5.9% GCL_IPL, and 15.2% IPL_INL. Their mean entropy is higher than the other columns for all four boundaries (approximately 0.45–0.55 versus 0.35). This supports an uncertainty association; it does not calibrate entropy as a quality score. Full >0.5, >2, and >5 pixel results are in `decoder_diagnostics_checkpoint/`.

Manual-reference consistency check: 18/4,580 GCL pairs lie outside the training-derived interval; RNFL and IPL pairs all lie within their intervals. Between 0.13% and 1.27% of eligible adjacent-column manual boundary steps exceed two pixels. The hard constraints therefore cannot represent every manual coordinate exactly. Validation did not tune the bounds.

Bounds use only the five original training animals' manual adjacent-pair thicknesses: q01/q99 widened outward by 20% of each endpoint. Minimum/maximum gaps in pixels: RNFL 18/235, GCL 3/37, IPL 28/82. Adjacent-A-line step is at most 2 pixels. No published anatomical value set these bounds.

The graph construction uses minimum closed sets and hard implication arcs, with PyMaxflow providing the minimum cut. Small exhaustive searches verify its global energy against all feasible solutions. [Li, Wu, Chen and Sonka method](https://pmc.ncbi.nlm.nih.gov/articles/PMC2646122/); [PyMaxflow API](https://pmneila.github.io/PyMaxflow/maxflow.html).

PyMaxflow 1.3.2 is isolated in this output directory's `dependencies/` without changing conda packages. Environment imports, a NumPy dot product, and a matplotlib rendering passed after installation.

## Phase 3: animal-excluded calibration and review queue

Seven independent models: epoch 124/124 at this checkpoint. Each fold has five training animals, one separate calibration animal, and one held-out evaluation animal. Roles rotate deterministically. Weight selection uses the fixed 124-epoch budget, never calibration or held-animal losses. Vectorised batching was checked against separate model losses and gradients.

The 124-epoch budget comes from development-selected v4 training. This is development cross-validation of a fixed workflow, not an untouched final-test estimate or proof of deployment coverage.

The queue builder writes packs accepted by the actual eight-surface GUI reader. Previously reviewed B-scans are excluded. A longest flagged run is explicitly an uncertainty/crossing proxy: true gross-error runs cannot be known on unlabelled images. The priority heuristic is not yet a measurement of human time saved. Acquisition-QC axes are stored separately.

No deployment coverage number is justified. The held-animal curves measure development cross-validation, with per-animal spread and the b0510 sensitivity. A per-volume entropy quantile may be used for experimental review triage; it is not a promised error guarantee.

### Completed held-animal calibration

All seven folds completed 124 epochs × 48 updates. None selected a checkpoint or entropy cutoff using the evaluated animal. All 62 eligible development B-scans had nonempty manual region supervision (minimum 1,780 region pixels), so the empty-region optimizer edge case does not arise in this run.

The following ranges compare a cutoff placed at the 90th entropy percentile on a *different calibration animal*, then transferred to the held-out animal. This is not a pooled p95, and 90% is the calibration quantile, not a promised retained fraction. Each cell gives the range across seven held animals, first with b0510 and then without it. Boundary-specific and paired-boundary thickness coverage have different denominators.

#### Ordered DP

The seven calibration-animal cutoffs themselves range from 0.3917 to 0.5581.

| Surface / band | Coverage range with / without b0510 (%) | Retained p95 range with / without b0510 (µm) |
|---|---:|---:|
| ILM | 60.0–99.7 / 60.0–99.7 | 3.36–16.80 / 3.36–16.80 |
| RNFL_GCL | 69.9–96.6 / 69.9–97.3 | 4.39–14.36 / 4.39–14.36 |
| GCL_IPL | 74.0–94.7 / 74.0–96.7 | 5.74–13.16 / 5.74–13.16 |
| IPL_INL | 43.9–96.8 / 43.9–96.8 | 5.82–10.34 / 5.82–10.34 |
| RNFL | 38.8–96.2 / 38.8–98.4 | 6.00–25.51 / 6.00–25.51 |
| GCL | 59.1–94.0 / 59.1–96.0 | 7.45–14.26 / 7.45–14.26 |
| IPL | 34.7–92.7 / 34.7–93.2 | 6.58–18.91 / 6.58–18.91 |
| INNER_RETINA | 24.7–99.4 / 24.7–99.4 | 7.14–19.21 / 7.14–19.21 |

![Ordered DP: held-animal boundary coverage and error](calibration_dp/coverage_error_boundaries.png)

![Ordered DP: held-animal thickness coverage and error](calibration_dp/coverage_error_thickness.png)

#### Original soft estimator

The seven calibration-animal cutoffs themselves range from 0.3917 to 0.5581.

| Surface / band | Coverage range with / without b0510 (%) | Retained p95 range with / without b0510 (µm) |
|---|---:|---:|
| ILM | 59.1–99.7 / 59.1–99.7 | 3.59–26.25 / 3.59–16.98 |
| RNFL_GCL | 66.7–95.2 / 66.7–95.5 | 4.51–12.53 / 4.51–12.53 |
| GCL_IPL | 70.7–91.3 / 70.7–95.1 | 5.94–10.42 / 5.94–10.42 |
| IPL_INL | 43.3–94.8 / 43.3–94.8 | 6.45–11.51 / 6.45–9.68 |
| RNFL | 37.2–91.5 / 37.2–96.4 | 6.43–25.26 / 6.43–25.26 |
| GCL | 57.6–90.4 / 57.6–94.4 | 7.16–13.65 / 7.16–13.65 |
| IPL | 33.3–90.3 / 33.3–91.5 | 5.71–18.42 / 5.71–18.42 |
| INNER_RETINA | 24.4–99.4 / 24.4–99.4 | 7.73–20.21 / 7.73–19.72 |

![Original soft estimator: held-animal boundary coverage and error](calibration_soft/coverage_error_boundaries.png)

![Original soft estimator: held-animal thickness coverage and error](calibration_soft/coverage_error_thickness.png)

The full 50th–100th percentile transfer curves, fixed-threshold curves, eligible and retained counts, gross-error fractions, and per-animal sensitivities are saved alongside these plots. A universal threshold is not selected: the small, heterogeneous development cohort does not justify a deployment coverage/error guarantee. Per-volume quantiles remain an experimental way to allocate review, with high-priority cases and control cases both sampled.

For example, ordered-DP RNFL thickness coverage spans 38.8–96.2% across held animals at the 90th calibration percentile (38.8–98.4% without b0510), while the retained p95 error range is 6.00–25.51 µm in both sensitivities. TS165, the WT control animal, supplies the least favourable tail in this comparison. These results argue against quoting the earlier two-animal 90%-coverage figure as transferable reliability.

### What the held-animal results look like

These are independent fold models, so their numbers differ from the delivered v4 model's earlier gallery. The first row is the largest ordered-DP median error among the WT animal's three manually supported B-scans: median error changes from 6.3 to 6.9 µm despite crossings reaching zero. The second is the previously shown TS169 case; the third is the preidentified b0510 case, where median error falls from 29.7 to 2.2 µm. All errors use eligible manual columns only. The displayed raw curves extend into unlabelled areas; those areas are not accuracy evidence.

![Manual annotations versus animal-excluded predictions](examples_held_animal/comparison_examples.png)

### Completed full-volume review queue

Two complete volumes, 1,024 B-scans, and 18 new review candidates (eight priorities plus one control per volume) are saved. The actual GUI pack reader confirms that every candidate is undecided, has no edited flags, and preloads no existing label.

| Volume | Raw crossing A-lines | Ordered-DP crossings | Total A-lines | Experimental entropy cutoff |
|---|---:|---:|---:|---:|
| TS165_OS_2025-04-29_WT_s02_121711 | 90,821 | 0 | 262,144 | 0.6677 |
| TS325_OD_2026-05-26_6mo_s01_112940 | 131,293 | 0 | 262,144 | 0.6145 |

The per-volume 90th entropy percentile deliberately retains approximately 90% of available, in-scope, unshadowed boundary columns by construction. That percentage is not evidence of 90% accurate coverage. Shadowed thickness is NaN in both volumes. INL, OPL, PHOTORECEPTOR, RPE, and full-retina TOTAL remain explicitly unreliable/NaN in these inner-retina outputs.

`review_queue/review_queue.csv` ranks all B-scans; `selected_review_queue.csv` lists the 18 selections. `review_queue/packs/` opens in the existing annotation GUI. Independent acquisition measurements are in each volume's `acquisition_qc_separate.json` and do not enter the queue priority.

![Unreviewed automatic review candidates](review_queue/review_examples.png)

## Saved checkpoints and safety of the scientific inputs

- Selected existing model: `../20260908_v4_longtrain/dev_seed20260908/best.pt`.
- Four-head experiment: `four_head_seed20260908/best.pt`, with a complete 9,600-step history and exact checkpoint reload check.
- Independent fold training: `cv_seven_animals/ensemble_00.pt`, checkpointed each epoch, with a fixed protocol and resume identity guard.
- All implementation modules from this task live outside `code/stage_a/`. Original model/data code and frozen baseline predictions are preserved.
- Source volumes, manual labels, frozen targets, and final-test partitions are read-only throughout this work.
- Verified unchanged: 68 permitted corrected label files, 110 frozen target files, 110 image caches, 38 original baseline predictions, and the v4 checkpoint. The original Stage A resume code guard currently passes; the temporary concurrent-work mismatch described in the historical audit is resolved.

- All 31 checks passed: manual-reference eligibility, exact graph-cut solutions, independent model losses/gradients, resume fold isolation, entropy withholding, and real GUI pack loading. Original core Stage A code remains unchanged.
- The exact CV source used for training is preserved in `source_used/cv_training_source.py`. A subsequent resume-only fix rejects changed fold grouping or broadcast tensor copies and verifies completed runs without rewriting exported models. It does not alter this run's trained weights.
