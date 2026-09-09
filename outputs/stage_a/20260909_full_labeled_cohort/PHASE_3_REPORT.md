# Phase 3 — complete

Nine separate evaluation networks each exclude an evaluated animal and a distinct calibration animal, training on the remaining seven. The separate all-label model is never used in the calibration accuracy estimate. At the 90th calibration percentile, the held-animal retained coverage and conditional p95 ranges below show the spread, including b0510 sensitivity.

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

This is small-cohort development cross-validation, not untouched final-test or lesion-core evidence. No universal 90% retained-coverage guarantee is supported. The review queue therefore uses an experimental per-volume entropy quantile to prioritize workload. Its longest flagged run is an uncertainty/crossing proxy, not a measured gross-error run. Acquisition QC remains separate.

| Volume | Complete B-scans | New candidates | Review file |
|---|---:|---:|---|
| TS165_OS_2025-04-29_WT_s02_121711 | 512 | 9 | [Open pack in labeling GUI](<G:/OCT_TreeShrew/octa/outputs/stage_a/20260909_full_labeled_cohort/review_queue/packs/TS165_OS_2025-04-29_WT_s02_121711_pack.npz>) |
| TS247_OD_2024-11-06_D21_s03_104157 | 512 | 9 | [Open pack in labeling GUI](<G:/OCT_TreeShrew/octa/outputs/stage_a/20260909_full_labeled_cohort/review_queue/packs/TS247_OD_2024-11-06_D21_s03_104157_pack.npz>) |
| TS283_OD_2025-01-29_D7_s02_123712 | 512 | 9 | [Open pack in labeling GUI](<G:/OCT_TreeShrew/octa/outputs/stage_a/20260909_full_labeled_cohort/review_queue/packs/TS283_OD_2025-01-29_D7_s02_123712_pack.npz>) |
| TS325_OD_2026-05-26_6mo_s01_112940 | 512 | 9 | [Open pack in labeling GUI](<G:/OCT_TreeShrew/octa/outputs/stage_a/20260909_full_labeled_cohort/review_queue/packs/TS325_OD_2026-05-26_6mo_s01_112940_pack.npz>) |

The four volumes supply 2,048 full B-scans and 36 unreviewed candidates. The actual GUI reader loaded all four packs; no label writer was allowed during verification. Shadowed thickness is NaN. Unsupported outer layers are explicitly unreliable. These files complete the automated workflow; no automatic acceptance or further manual annotation was performed.

[Boundary coverage/error curves](<G:/OCT_TreeShrew/octa/outputs/stage_a/20260909_full_labeled_cohort/calibration_dp/coverage_error_boundaries.png>) · [Thickness coverage/error curves](<G:/OCT_TreeShrew/octa/outputs/stage_a/20260909_full_labeled_cohort/calibration_dp/coverage_error_thickness.png>) · [Review examples](<G:/OCT_TreeShrew/octa/outputs/stage_a/20260909_full_labeled_cohort/review_queue/review_examples.png>)
