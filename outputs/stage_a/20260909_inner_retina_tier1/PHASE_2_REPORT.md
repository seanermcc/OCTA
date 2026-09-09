# Phase 2 — constrained decoders

Manual annotations are the only segmentation ground truth. Final-test animals remain locked. See [the complete report](RUN_REPORT.md) for shared provenance and verification.

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

