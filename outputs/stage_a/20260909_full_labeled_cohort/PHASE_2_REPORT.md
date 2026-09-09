# Phase 2 — complete, strict acceptance failed

The three-way comparison of the original soft decoder, ordered DP, and true joint graph cut was completed in the historical Tier 1 run. The inexpensive DP control was carried forward for nine-animal development cross-validation. Constraints are fitted from manual training-animal evidence, excluding the evaluated and calibration animals.

| Surface / band | Animal-excluded soft: median | Animal-excluded ordered DP: median | Animal-excluded soft: p95 with / without b0510 | Animal-excluded ordered DP: p95 with / without b0510 |
|---|---:|---:|---:|---:|
| ILM | 1.89 | 1.94 | 11.92 / 10.46 | 9.49 / 9.51 |
| RNFL_GCL | 2.57 | 2.47 | 22.80 / 20.31 | 12.67 / 12.75 |
| GCL_IPL | 2.37 | 2.35 | 17.54 / 15.53 | 11.82 / 11.93 |
| IPL_INL | 2.74 | 2.69 | 22.07 / 18.71 | 12.24 / 12.27 |
| RNFL | 3.58 | 3.36 | 33.42 / 28.98 | 20.93 / 21.21 |
| GCL | 2.83 | 2.84 | 20.85 / 19.33 | 11.72 / 11.76 |
| IPL | 3.51 | 3.46 | 30.89 / 26.84 | 18.15 / 18.30 |
| INNER_RETINA | 3.34 | 3.34 | 31.33 / 26.08 | 18.55 / 18.75 |

All values are µm. Every pooled p95 includes its with/without-b0510 sensitivity. Crossings fell from 7,751/52,224 to 0/52,224, but 95 pooled/per-animal metric cells worsened across both sensitivities. The strict no-regression criterion failed; there is no production promotion.

[All errors, coverage, and movement summaries](<G:/OCT_TreeShrew/octa/outputs/stage_a/20260909_full_labeled_cohort/held_animal_comparison>) · [Historical joint graph-cut comparison](<G:/OCT_TreeShrew/octa/outputs/stage_a/20260909_inner_retina_tier1/PHASE_2_REPORT.md>)
