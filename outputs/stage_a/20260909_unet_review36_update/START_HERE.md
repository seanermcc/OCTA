# Review-36 U-Net update

## Result

This is a bounded development update, not a deployment promotion.  The frozen
cohort was merged with the 36 saved review decisions by scan/B-scan identity:
134 corrected decisions and 63 rejected decisions are recorded.  The review
adds 32 corrected and four rejected decisions.  Only directly edited, visible,
reliable, non-displaced, non-excluded, finite, in-image, non-shadowed columns
entered the targets; rejected decisions provide no position targets.

The retained eight-head fixed-budget recipe produced two new checkpoints:
[all-label inference model](models/ALL_LABELLED/last.pt) and the
[TS247-excluded development model](models/TS247/last.pt).  The latter excludes
TS247 and its original distinct calibration animal TS250; it starts from a new
initialization, not either all-label model.

## TS247 development comparison

Both models were scored with identical eligibility masks and the same ordered
decoder, whose bounds were fitted only from TS165, TS169, TS241, TS267, TS283,
TS305, and TS325.  Full boundary and thickness rows, including median, p95,
gross-error fraction, finite/retained coverage, are in
[validation_metrics.csv](validation/validation_metrics.csv).

On the newly reviewed TS247 positions, the update substantially improves GCL
(median/p95 9.27/40.72 to 6.93/20.20 um) and inner-retina thickness
(4.75/7.51 to 1.39/3.28 um).  IPL median improves (17.17 to 6.38 um), but its
p95 worsens (31.77 to 77.42 um): this is a retained, reported regression, not
a silent promotion.  RNFL median improves (4.42 to 3.32 um) while the p95
improves (35.20 to 27.76 um).  All reported raw and retained coverage is 1.0
for these finite eligible columns.  This is single-animal development
validation, not an untouched final test.

## Four complete experimental volumes

Each listed volume has 512 processed B-scans, ordered-decoder crossings are
zero, and shadowed thickness values are NaN.  Unsupported INL, OPL,
PHOTORECEPTOR, RPE, and TOTAL remain explicitly unreliable.

| Volume | B-scans | Raw crossing columns | Ordered crossing columns |
|---|---:|---:|---:|
| TS165_OS_2025-04-29_WT_s02_121711 | 512 | 33,398 | 0 |
| TS247_OD_2024-11-06_D21_s03_104157 | 512 | 18,219 | 0 |
| TS283_OD_2025-01-29_D7_s02_123712 | 512 | 19,517 | 0 |
| TS325_OD_2026-05-26_6mo_s01_112940 | 512 | 44,368 | 0 |

[Complete per-volume arrays and GUI review packs](review_queue/) ·
[new model review image sheet](review_queue/review_examples.png) ·
[previous-model review image sheet](../20260909_full_labeled_cohort/review_queue/review_examples.png).
The image sheets are fit/triage illustrations, not animal-excluded validation;
the validation comparison above is the held-animal result.

Compact old-versus-updated inner-retina measurement images are saved for
[TS165](comparison_images/TS165_OS_2025-04-29_WT_s02_121711_old_vs_updated.png),
[TS247](comparison_images/TS247_OD_2024-11-06_D21_s03_104157_old_vs_updated.png),
[TS283](comparison_images/TS283_OD_2025-01-29_D7_s02_123712_old_vs_updated.png), and
[TS325](comparison_images/TS325_OD_2026-05-26_6mo_s01_112940_old_vs_updated.png).
They are all-label fit comparisons, not validation illustrations.

## Provenance and checks

[Dataset manifest](data/manifest.json) · [annotation audit](data/manual_evidence_audit.csv) ·
[review audit](annotation_audit/audit_provenance.json) · [all-label decoder bounds](all_label_constraints/constraints.json) ·
[held-animal decoder bounds](validation_constraints/constraints.json) ·
[validation protocol](validation/protocol.json) · [measured runtimes](runtimes.csv).

The importer re-read review-volume geometry, derived orientation from the image
instead of stored flags, and accepted a source pack only after exact pixel
alignment.  Original human labels and the previous outputs/checkpoints were not
modified.
