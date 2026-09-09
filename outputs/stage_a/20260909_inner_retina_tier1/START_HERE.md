# Inner-retina checkpoint — completed

The work continued through all three requested phases. No cohort choice or approval is pending. Seven permitted development animals were used; final-test animals stayed locked. Only manually drawn boundaries supplied segmentation ground truth. The layer-segmentation skill was not used.

The method helps, but the results do not support unattended thickness measurements yet. Keep the existing eight-head model and report the four inner boundaries. The four-head retraining and the classical replacement did not win. Ordered decoding removes crossings and substantially improves the worst example, while slightly worsening some median errors. It is available as an experimental review aid.

## See the image evidence

In each row below, the manual reference is on the left, the held-animal neural prediction is in the middle, and ordered decoding is on the right. Solid lines are automatic predictions; dotted lines show eligible manual evidence.

The bottom example improves from 29.7 to 2.2 µm median boundary error. The WT example at the top changes from 6.3 to 6.9 µm despite having no crossings after decoding. These examples illustrate both the benefit and the remaining limitation. They are not an average-performance estimate.

![Manual evidence, held-animal model, and ordered decoding](examples_held_animal/comparison_examples.png)

[Original v4 model comparison](examples_decoders/comparison_examples.png) · [Four-head retraining comparison](examples_retraining/comparison_examples.png)

## What calibration established

Seven independent models were evaluated on animals excluded from their training. Each uncertainty threshold came from another, separate calibration animal. Performance varied substantially between animals, so no universal threshold or reliable-coverage percentage was adopted.

For RNFL thickness with ordered decoding, the 90th calibration percentile yielded 38.8–96.2% retained coverage and a retained p95 error range of 6.00–25.51 µm across animals. Without the preidentified b0510 case, coverage spans 38.8–98.4% and the error range is unchanged. A per-volume percentile can allocate review effort; it does not guarantee accuracy.

[Boundary calibration plots](calibration_dp/coverage_error_boundaries.png) · [Thickness calibration plots](calibration_dp/coverage_error_thickness.png)

## Review material is ready

Two full volumes were processed: 1,024 B-scans. The saved packs contain 18 new candidates, including priority cases and controls, and load in the existing annotation GUI. They are undecided automatic proposals. No human label was created or modified.

[Review candidate preview](review_queue/review_examples.png) · [Review packs](review_queue/packs/) · [Selected cases](review_queue/selected_review_queue.csv)

The next scientific step is manual review of these candidates in the existing GUI. Those corrections can supply additional ground truth. Shadowed thickness stays missing; unsupported outer layers are explicitly marked unreliable.

## Detailed checkpoint

[Complete report](RUN_REPORT.md) · [Reproduction instructions](REPRODUCE.md) · [Phase 1](PHASE_1_COMPLETE.md) · [Phase 2](PHASE_2_REPORT.md) · [Phase 3](PHASE_3_REPORT.md)

All 31 implementation checks passed. The original v4 checkpoint, original Stage A code identity, 68 permitted corrected labels, 110 frozen targets, 110 caches, and 38 baseline prediction files were verified unchanged. Experimental models and their training protocols are saved; nothing was promoted to a validated measurement pipeline.
