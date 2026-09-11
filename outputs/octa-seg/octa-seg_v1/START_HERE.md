# octa-seg_v1 — START HERE

**Experimental review release. The learned reporting states FAILED validation. Do not treat these outputs as validated research measurements.**

Double-click [OPEN_OCTA_SEG_V1.cmd](OPEN_OCTA_SEG_V1.cmd) from Windows to activate `octa` and open the 30-example queue in `code/cnv_review_v1`. Codex's offscreen preview verifies rendering only; it does not establish that a launched window is visible on your desktop.

The queue contains **26 contextual-estimate examples**, 0 withheld regions lacking sufficient context, and four controls. Use the queue bar at the top. All four volumes are complete (512 B-scans each); arbitrary native rows remain available.

![Four-volume overview](reports/review_overview.png)

## What to review

Solid lines are experimental reported segments. Amber dashes are optional uncertain candidates. A not-traceable boundary has a gap, with no candidate continuation. Choose a boundary and A-line to see its probabilities, state and reason. Blue footprints are lateral vessel context, never vessel depth.

Draw to correct the selected range. A new correction remains uncertain until **Approve selected estimate for future position training** is clicked. You can instead keep it uncertain or mark it not traceable. Generic Accept does not approve estimates. Approval of an unchanged automatic candidate is stored as explicit estimate approval, never claimed as a manual stroke. New labels go through the provenance-aware GUI writer to `reviewer/surface_labels`; separate decisions go to `reviewer/estimate_feedback`. They are for v2, not self-training v1. Existing boundary labels and CNV region classifications load with priority and remain intact in their original folders.

## Audit and supervision

The final snapshot has 199 records from 11 animals: {'rejected': 63, 'corrected': 135, 'accepted': 1}. It includes the two latest linked-GUI saves after checking the source, crop, and freshly detected native orientation. 11 records with negative state evidence have no eligible positions and are retained for state learning.

Saved field counts (boundary × A-line units): **13,854 not traceable; 26,388 unreliable; 52,826 explicit visible; 852 explicit reliable**. Unknown visibility: 748,424; unknown reliability: 787,864. Image exclusions: 13,852 A-lines; local automatic joins: 6,025; local ordering displacement: 7,307 boundary locations. These categories can overlap and must not be added as mutually exclusive classes.

Exact-stroke positional supervision contains **37,298 eligible boundary locations**. A direct correction does **not** create a positive reliability label: reliability remains masked unless explicitly judged. Positive state marks within an image exclusion are also masked; explicit negatives survive. [saved_state_counts.json](data/saved_state_counts.json) separates raw saved judgments from final training masks. All 160 legacy format-2 records are excluded from position supervision because their stroke extents cannot be recovered; explicit negative whole-boundary decisions remain useful. Rejected reviews supply no position targets. Automatic curves, reviewed-but-undrawn automatic lines, tapers, displacements, shadowed positions and excluded columns do not become position targets. Missing/default state flags stay masked.

Current code and both available historical Git revisions agree: Shift+right-drag means not visible; Alt+right-drag unreliable; Ctrl+right-drag clears image exclusion. No available evidence supports remapping Ctrl+right-drag to unreliable. Nothing was relabeled based on gesture memory. “Not visible” means not traceable in this image, not anatomical absence. [Gesture history](data/gesture_history.json), [per-record audit](data/label_audit.csv), and [saved-state examples](data/saved_state_counts.json).

| boundary | position_columns | position_records | not_traceable | unreliable | explicit_reliable |
|---|---|---|---|---|---|
| ILM | 292 | 13 | 881 | 58 | 3 |
| RNFL_GCL | 4465 | 31 | 703 | 3786 | 100 |
| GCL_IPL | 5024 | 32 | 1771 | 4271 | 131 |
| IPL_INL | 5357 | 31 | 2257 | 3777 | 123 |
| INL_OPL | 5288 | 31 | 2289 | 7583 | 30 |
| OPL_ONL | 5847 | 31 | 3019 | 4292 | 176 |
| PR_RPE | 5515 | 31 | 1435 | 1329 | 38 |
| RPE | 5510 | 32 | 1499 | 1292 | 251 |

All eight outputs are implemented. Evidence amount differs substantially, especially ILM; **none earns a validated reliability claim**. See [boundary support](data/boundary_support.csv) and calibration files for per-fold missing positives/negatives.

## Model and validation

The position branch retains the updated eight-head, base-8 U-Net architecture. Four evaluation models start from random weights and train for 1,800 steps on exact manual evidence, using native-depth 128-A-line crops. The separate all-label branch starts from the requested updated checkpoint and fine-tunes for 600 steps. Its inherited upstream weights were trained with the earlier legacy edited-surface approximation; v1 introduces no such position targets. This inherited all-label model is a fit/review provider, never the evaluation model.

Two separate sigmoid heads learn traceability and reliability from the predicted depth distribution, 17 local axial intensity samples, uncertainty and lateral context. The state branch is trained after freezing the position branch: negative-only records cannot move position targets. Its convolutions span 43 lateral columns. Nine hundred state steps are fixed in advance. Head scores are retained as probabilities, but they are **not proven probability-calibrated**; empirical operating thresholds are calibrated separately.

Animal roles rotate: evaluate TS165/calibrate TS247; evaluate TS247/calibrate TS283; evaluate TS283/calibrate TS325; evaluate TS325/calibrate TS165. Each pair is excluded from that fold's entire training set, including neighboring slices. The remaining animals supply only the evidence actually available. No evaluation network inherits an all-label checkpoint. These are development cross-validation results, not an untouched final test. [Protocol](models/protocol.json), [manifest](data/manifest.json).

Thresholds minimize false positive state decisions subject to at least 70% affirmative-state retention on the calibration animal. Specificity cannot be established when a calibration class is absent. Fewer than 20 affirmative calibration marks disable reporting for that boundary/fold; the CSV exposes these gaps rather than treating withholding as validation success. Thresholds are never set by withholding a fixed fraction of each volume. The all-label workflow transfers median calibration thresholds from supported excluded models, with a documented distribution-shift limitation. No validated reporting claim is made.

Held-animal results below apply **before** human overrides. A zero false-report rate after applying human denials would merely test the override rule, not learned performance. The joint reporting decision also requires a finite in-image noncrossing position; therefore joint retention can be lower than the per-head calibration constraint.

| boundary | not_traceable_false_report_pct | reliable_retention_pct | unreliable_report_pct |
|---|---|---|---|
| ILM | 0.000 | 0.000 | 0.000 |
| RNFL_GCL | 0.000 | 0.000 | 13.958 |
| GCL_IPL | 11.801 | 21.374 | 14.075 |
| IPL_INL | 1.163 | 20.536 | 4.991 |
| INL_OPL | 3.517 | 0.000 | 2.629 |
| OPL_ONL | 2.000 | 16.547 | 4.743 |
| PR_RPE | 0.000 | 0.000 | 0.000 |
| RPE | 4.803 | 9.129 | 44.892 |

False-report rates must be read with retention: zero reporting caused by missing calibration evidence is an abstention failure, not success. [State counts and strata](evaluation/state_summary.csv), [position and thickness errors including p95/max/>20 µm](evaluation/position_thickness_pooled.csv), [failure run lengths](evaluation/spatial_failures.csv). Tables include animal, boundary, vessel presence and available CNV-outline strata. CNV outlines are inspection context, not boundary measurability truth; outside a saved outline does not establish absence of CNV.

The paired vessel ablation omits both the vessel feature and vessel-derived defaults, with the same position branch, state architecture, initialization, sampling and training budget. Manual saved masks (including empty reviewed masks/drafts) take priority over automatic proposals. Source hashes/origins and native footprints are saved in the manifest. Vessel defaults only supervise unknown reliability at lower within-class weight (0.2); no vessel creates a not-traceable target or a positive target outside vessels. At inference, ILM still needs image evidence, RNFL/GCL and every deeper boundary default to unreliable under a footprint unless a manual per-boundary reliable judgment overrides that default. These are working rules, not human boundary annotations. The paired tables report both reductions in false reporting and losses of retention; no blanket benefit is claimed.

## Contextual candidates and measurements

The estimator requires finite reliable lateral anchors on both sides in the central slice and in both neighboring slices, and a gap no longer than 128 A-lines. Interior neighboring U-Net position proposals may themselves be uncertain: they supply context, not measurement truth. Adjacent canonical images are translation-registered in native coordinates; shifts exceeding 6 lateral or 12 axial pixels, image correlation below 0.65, local patch correlation below 0.45, neighbor disagreement above 12 px or central-model disagreement above 16 px stop estimation. Both neighboring shapes are endpoint-adjusted without smoothing their deformation. Not-traceable corridors, image exclusions, rejected images, missing context and crossings stop estimates. No generated candidate is reused as context for another estimate. These context thresholds are engineering settings, not tuned on evaluation targets. Agreement between neighboring proposals can reflect shared model error; it is not evidence of positional accuracy in true signal loss.

The held-animal hidden-position experiment recovered **8/128 deliberately hidden eligible columns** across 12 trials. This masks position output while leaving the image intact. It is **not** a simulation of biological signal loss and does not give real unreliable regions position ground truth. [Recovery table](evaluation/hidden_position_recovery.csv) reports abstentions as well as error where recovery was possible.

Each volume's `measurements.npz` stores full canonical `reported_positions`, separate `uncertain_estimates`, both state probabilities, decision and context reasons, raw diagnostic position outputs, native masks, and `primary_thickness_um`. The primary thickness array uses reported boundaries only and is NaN wherever either endpoint is withheld or a column is shadowed. No uncertain-estimate thickness is produced. Despite its primary-output role, this v1 thickness remains experimental. Raw position diagnostics must not be rendered as an estimated continuation in not-traceable regions. GUI compatibility packs put **only reported rows** in `surfaces`, so older consumers receive gaps safely.

| scan_id | n_bscans | reported_fraction | unreliable_fraction | not_traceable_fraction | estimate_gaps | estimate_columns |
|---|---|---|---|---|---|---|
| TS165_OS_2025-04-29_WT_s02_121711 | 512 | 0.516 | 0.341 | 0.143 | 151 | 2505 |
| TS247_OD_2024-11-06_D21_s03_104157 | 512 | 0.628 | 0.257 | 0.115 | 168 | 3585 |
| TS283_OD_2025-01-29_D7_s02_123712 | 512 | 0.600 | 0.289 | 0.111 | 513 | 9329 |
| TS325_OD_2026-05-26_6mo_s01_112940 | 512 | 0.584 | 0.312 | 0.104 | 624 | 5469 |

[Volume rankings](reports/volume_rankings.csv) use the fraction of all 8×512×512 locations in the uncertain state. [B-scan rankings](reports/bscan_rankings.csv) use uncertain fraction plus longest uncertain run/512. Withheld fraction includes both uncertain and not traceable and is reported separately. These are segmentation-review priorities; acquisition QC is saved separately and is never called scan quality here. Adjacent state disagreement is descriptive, since true CNV deformation and motion can both change states.

## Files and reproducibility

- [30-example queue](review_packs/queue.csv), full providers in `review_packs/automatic`, and selected image packs in `review_packs/selected`.
- [Launch configuration](launch_config.json); [runtime measurements](reports/runtimes.csv); [progress file](progress.json).
- Training weights and optimizer/RNG states are checkpointed every 100 steps. Native inference saves every completed B-scan. CPU volume exports and registration have separate completion markers.
- Original sources remain referenced with hashes; all new models, arrays, packs, reports and feedback stay inside this version folder. The 2-GB source array is never transposed; individual canonical images are prepared using detected orientation. Read input only from processedVolumes.mat.
- Existing human label bytes changed since the audit: none detected. Such external user changes, if any, are never folded silently into the frozen dataset.

From Command Prompt, `call D:\Anaconda\Scripts\activate.bat octa`, then `cd /d G:\OCT_TreeShrew\octa` and `set PYTHONPATH=G:\OCT_TreeShrew\octa\code`. Run `python -m octa_seg_v1.release` to resume missing stages under a single-process lock. A completed release verifies its saved artifacts and does not retrain or overwrite. Individual stage commands are documented in [implementation notes](IMPLEMENTATION.md). Use octa-seg_v2 for any new training or threshold decisions.
