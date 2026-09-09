# Phase 3 — calibration and review queue

Manual annotations are the only segmentation ground truth. Final-test animals remain locked. See [the complete report](RUN_REPORT.md) for shared provenance and verification.

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

