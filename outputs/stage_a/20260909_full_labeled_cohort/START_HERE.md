# Completed full labeled-cohort run

All three stages are complete. No cohort decision or approval is pending. A checkpoint means saved reports and artifacts while the run continues; this run has now finished its planned calculations.

The run used all 102 corrected B-scans from nine animals and 27 volumes. Manual segmentation is the only ground truth. The 59 rejected decisions supplied no position targets. Unedited automatic, displaced, invisible, unreliable, excluded, and shadowed positions were excluded according to recorded provenance; older labels retain their documented surface-level provenance limitation.

## What worked, and what did not

The ordered decoder removed all 7,751 crossing columns in the 102 manually supported B-scans and reduced every pooled large-error tail. Median thickness errors measured on excluded animals were 3.36 µm for RNFL, 2.84 µm for GCL, and 3.46 µm for IPL. These are development cross-validation results; some per-animal errors worsened, so the strict no-regression requirement failed. The output remains experimental.

The earlier four-head retraining experiment lost, so the eight-head network is retained with four inner boundaries reported. Classical inner-band fractions improved some errors but failed the same no-regression requirement. Replacing the learned middle boundaries with classical costs also lost. Neither classical change was adopted.

The separate inference model trains on all nine animals. Its own training-set fit is not independent accuracy. No untouched final-test set remains after the explicitly authorized cohort release. Uncertainty transfer varied widely between animals; the queue uses a per-volume workload rule, without a universal reliability promise or a lesion-core claim.

## See the result

Left: manual reference. Middle: prediction from a model that excluded this animal. Right: the same model with the ordered decoder. Solid lines are predictions; dotted lines are eligible manual reference. These selected examples illustrate behavior; the complete tables include every animal and the failures.

![Manual and animal-excluded predictions](<G:/OCT_TreeShrew/octa/outputs/stage_a/20260909_full_labeled_cohort/examples_held_animal/comparison_examples.png>)

[Additional exact-stroke annotation: old, animal-excluded, and all-label predictions](<G:/OCT_TreeShrew/octa/outputs/stage_a/20260909_full_labeled_cohort/examples_new_manual_strokes/comparison_examples.png>)

[All-label model fit examples (in-sample only)](<G:/OCT_TreeShrew/octa/outputs/stage_a/20260909_full_labeled_cohort/examples_all_label_fit/comparison_examples.png>)

## Review files and model

Four entire volumes were processed: 2,048 B-scans. Each pack contains eight priority candidates and one control, for 36 unreviewed automatic proposals. All four packs passed the actual GUI-reader check with label writing disabled. Existing manual labels were unchanged. Shadowed thickness remains NaN, and unsupported outer layers are explicitly unreliable.

| Volume | Complete B-scans | New candidates | Review file |
|---|---:|---:|---|
| TS165_OS_2025-04-29_WT_s02_121711 | 512 | 9 | [Open pack in labeling GUI](<G:/OCT_TreeShrew/octa/outputs/stage_a/20260909_full_labeled_cohort/review_queue/packs/TS165_OS_2025-04-29_WT_s02_121711_pack.npz>) |
| TS247_OD_2024-11-06_D21_s03_104157 | 512 | 9 | [Open pack in labeling GUI](<G:/OCT_TreeShrew/octa/outputs/stage_a/20260909_full_labeled_cohort/review_queue/packs/TS247_OD_2024-11-06_D21_s03_104157_pack.npz>) |
| TS283_OD_2025-01-29_D7_s02_123712 | 512 | 9 | [Open pack in labeling GUI](<G:/OCT_TreeShrew/octa/outputs/stage_a/20260909_full_labeled_cohort/review_queue/packs/TS283_OD_2025-01-29_D7_s02_123712_pack.npz>) |
| TS325_OD_2026-05-26_6mo_s01_112940 | 512 | 9 | [Open pack in labeling GUI](<G:/OCT_TreeShrew/octa/outputs/stage_a/20260909_full_labeled_cohort/review_queue/packs/TS325_OD_2026-05-26_6mo_s01_112940_pack.npz>) |

[Review-candidate image sheet](<G:/OCT_TreeShrew/octa/outputs/stage_a/20260909_full_labeled_cohort/review_queue/review_examples.png>)

[All-label inference model](<G:/OCT_TreeShrew/octa/outputs/stage_a/20260909_full_labeled_cohort/cv_full_cohort/ALL_LABELLED/last.pt>) · [Manual-derived decoder constraints](<G:/OCT_TreeShrew/octa/outputs/stage_a/20260909_full_labeled_cohort/all_label_constraints/constraints.json>)

Each volume subfolder under `review_queue` contains its experimental measurement arrays. These outputs cover the four listed volumes; the 314-scan acquisition batch is outside this completed run. The model and candidate lines remain proposals for review, not accepted manual labels.

## Reports and verification

[Complete report, all animals, sensitivities, and calibration plots](<G:/OCT_TreeShrew/octa/outputs/stage_a/20260909_full_labeled_cohort/RUN_REPORT.md>)

[Phase 1: scope and model comparison](<G:/OCT_TreeShrew/octa/outputs/stage_a/20260909_full_labeled_cohort/PHASE_1_REPORT.md>) · [Phase 2: ordered decoder](<G:/OCT_TreeShrew/octa/outputs/stage_a/20260909_full_labeled_cohort/PHASE_2_REPORT.md>) · [Phase 3: calibration and review queue](<G:/OCT_TreeShrew/octa/outputs/stage_a/20260909_full_labeled_cohort/PHASE_3_REPORT.md>)

[Reproduction instructions](<G:/OCT_TreeShrew/octa/outputs/stage_a/20260909_full_labeled_cohort/REPRODUCE.md>) · [Verification results](<G:/OCT_TreeShrew/octa/outputs/stage_a/20260909_full_labeled_cohort/verification_complete.json>) · [Checkpoint manifest](<G:/OCT_TreeShrew/octa/outputs/stage_a/20260909_full_labeled_cohort/checkpoint_manifest.json>)

All 33 implementation checks passed. Input identities, excluded-animal roles, checkpoint reloads, and GUI compatibility were also verified. These checks establish implementation integrity, not deployment accuracy.
