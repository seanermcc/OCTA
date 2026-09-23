# CNV v9 comparison release

Supervision: 29 confirmed acquisitions, 21 positive, 8 negative, 44 kept human regions across 10 animals. The deferred TS247 D7 acquisition is excluded from every fit, normalization, calibration and score.

Open **OPEN_GALLERY.cmd**. Both models have completed inference on the same 50 acquisitions selected before inference. No winner was selected and no correction queue was started.

## Models and actual training

Both use the original compact U-Net widths 16/32/64/128/256, fresh initialization, seed 267, 100 epochs × 32 optimizer steps, effective batch 4 processed together (measured batching amendment; same per-tile mean loss), AdamW lr 0.001 and weight decay 0.0001. Both use v8 Model 1 background-weighted BCE plus 0.5 positive-tile Dice. Checkpoints include optimizer, scaler and all RNG states for epoch-boundary resume.

Model 1 retains the original 19 channels. Model 2 appends 11 native context channels; the complete order is in data/protocol.json. Its L2-regularized candidate scorer uses 12 features and changes ranking/display only. Scores are uncalibrated. All raw probabilities and unfiltered threshold candidates remain in predictions/*.npz and gallery candidate JSON.

Training normalization uses only each fit’s training acquisitions. Missing sampling pools retain uniform animal selection and fall back deterministically; each fit records the pool inventory and actual fallback counts. Entirely unavailable measurements remain masked under the original input recipe.

## Independent CNV development evaluation

Three outer animal folds; each outer m2 scorer is fitted using two inner animal-excluded models with no access to its evaluation animals. Four m1 fits and ten m2 fits total, including final all-label deployment. Thresholds, matching and regularization were frozen before predictions. The final deployment scorer uses pooled outer out-of-sample candidates and is never used to report independent development metrics.

| View | Lesion recall | Precision | FP / acquisition | Mean Dice | Mean IoU | Total area MAE µm² |
|---|---:|---:|---:|---:|---:|---:|
| m1_raw | 0.864 | 0.427 | 1.759 | 0.543 | 0.445 | 11944.198 |
| m2_raw | 0.818 | 0.400 | 1.862 | 0.505 | 0.407 | 8955.765 |
| m2_adjusted | 0.500 | 0.815 | 0.172 | 0.520 | 0.461 | 10058.553 |

Per-animal, negative-field, context-source and per-target-review results, training-derived size strata, matching failures, and matched-region area errors are in development/metrics.json and development/candidates/. Region correspondence is computational, not confirmed biological identity.

## Context provenance and limits

Exact export training coverage: {'saved_manual': 8, 'frozen_v1': 21}. Measured against these corrected CNV targets: 924 vessel-overlap pixels and 0 ONH-overlap pixels out of 58707 positive pixels. See reports/context_audit.json for per-acquisition measurements.

- Frozen v1 is classical vessel processing with parameters initially evaluated on WT vessel labels, not learned v2 predictions.
- Frozen v1 can subtract pre-existing human ONH masks; this is manually assisted wherever a dependency exists.
- Saved manual context includes drafts and untouched automatic pixels. Per-target review and uncertainty/brush maps are explicit channels.
- No CNV mask is consumed by the vessel feature builder, but label-informed human vessel/ONH editing cannot be ruled out.
- The shared automatic layer inputs use frozen all-labelled layer weights. Animal grouping applies to newly trained CNV networks/scorers, not independent validation of the whole upstream pipeline.

The cohort is small and selected for correction. These folds do not establish unseen-animal or new-image accuracy for the full pipeline. Candidate confidence learned from out-of-sample fold networks may transfer imperfectly to the all-label network. Small, irregular, uncertain and overlapping footprints were never geometrically filtered from human targets.

## Inspection and reuse

The gallery shows structural OCT and actual OCTA with synchronized zoom/pan, native linked B-scans at rows 0–511, independent overlays, raw/adjusted m2 views, all down-ranked candidates, provisional areas and score contributions. Reviewer preferences use browser storage and a separate JSON export, never annotation files.

Deployable bundles: bundles/v9_m1/ and bundles/v9_m2/. Dual model choices and cached native candidates: correction_handoff.json. Human review is still required before any footprint becomes a CNV label.

Verification: 1912 consumed upstream files rehashed unchanged. Synthetic/real-data verification and browser screenshots are recorded in verification/. All 50 selected scans have both inference statuses complete.

Approximate area calibration: (1460/512)² µm² per native pixel. No lesion volume, unique biological-lesion count across repeat scans, or vascular-density measurement is claimed.

Additional audit details are in **IMPLEMENTATION_NOTES.md**, **reports/context_coverage.json**, **reports/context_history_audit.json**, and **reports/scorer_feature_support.json**. ONH context comprises four outlined fields, four reviewed-absence fields and 21 unassessed empty fields. Frozen v6 predictions locate hard reviewed-background patches only; historical upstream model exposure limits end-to-end independence.

The fixed Model 2 adjustment reduced development false positives per acquisition from 1.86 to 0.17, while recall fell from 81.8% to 50.0%. This tradeoff is retained for review; thresholds were not retuned. The final scorer used 74 unambiguous out-of-sample candidates and excluded 16 ambiguous candidates. Scorer fitting requires one-to-one IoU at least 0.25; development detection uses the separately frozen one-to-one IoU threshold of 0.10. Scores are uncalibrated.

Selection metadata: 50/50 acquisitions have unavailable actual post-laser intervals and are explicitly displayed using nominal days. All available current scan-index intervals were blank at audit. 50/50 selected acquisitions belong to animals represented in final v9 training; these are new acquisitions, not an unseen-animal test.
