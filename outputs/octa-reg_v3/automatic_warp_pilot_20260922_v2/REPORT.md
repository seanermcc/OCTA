# Automatic residual-warp pilot: eight pairs

Completed on 2026-09-22. **Two provisional improvements; six unchanged.** This is one pair from each of the first eight completed eye montages, not a full-montage replacement. Original saved placements, labels and arrays are untouched. No proposed correction has human approval.

Open index.html for the side-by-side and blink comparisons. The baseline source is the earlier BigWarp preparation, verified against the still-current manual review hashes before and after fitting.

| Eye | Outcome | Reserved-point median error (px) | Audit points |
| --- | --- | ---: | ---: |
| TS165_OD | baseline / needs_manual_landmarks | 48.66 → 48.66 | 2 |
| TS165_OS | baseline / needs_manual_landmarks | 47.56 → 47.56 | 4 |
| TS169_OD | baseline / audit_failed | 3.31 → 3.31 | 20 |
| TS169_OS | baseline / needs_manual_landmarks | 2.53 → 2.53 | 3 |
| TS241_OD | affine / provisional_improvement | 17.10 → 2.97 | 8 |
| TS241_OS | baseline / needs_manual_landmarks | 18.76 → 18.76 | 1 |
| TS247_OD | tps_0.02 / provisional_improvement | 26.37 → 1.00 | 21 |
| TS247_OS | baseline / needs_manual_landmarks | 5.86 → 5.86 | 4 |

## What to review

**Start with TS241 OS in Fiji.** Only five reciprocal feature matches survived; they cannot support a reliable deformation. Verify which branches correspond before drawing a warp. TS165 OD and OS are the next priorities: apparent offsets are large and too few spatially separated check points survived. TS169 OS and TS247 OS also need additional distributed landmarks. TS169 OD looked better on model-selection points but failed the separate audit; keep its original pose until inspected.

**Also inspect the two proposed improvements in the browser.** TS241 OD uses an affine correction (maximum target-to-source displacement 59.29 px). TS247 OD uses affine plus a regularized TPS residual (maximum 49.35 px). These are substantial enough to need visual confirmation. In the TS247 OD inverse sampling map the Jacobian ranges from 0.661 to 0.973 and minimum local stretch is 0.700: no fold was detected, but the implied forward expansion is material. This is not a validated physical change in retinal tissue.

Each eye folder contains OPEN_PAIR_IN_FIJI.ijm. Open it in Fiji and press Run; it opens the saved manually aligned moving image and target and brings up Big Warp selection. Choose Moving_<eye> and Target_<eye>. Optional automatic_landmarks_inactive.csv contains **inactive automatic suggestions**, not human labels: inspect each correspondence before enabling it. Yellow training, green model-selection and magenta audit points are shown in matches.png; gray points were excluded as spatial buffers. Save manual work to a new trial directory, not over the source review files.

Installed Fiji found at D:/ImageJ/Fiji.app with BigWarp 9.3.1. The downloaded source is a separate 9.4.1-SNAPSHOT checkout. No Fiji update or installation change was made. The helper macros were generated but not executed in the Fiji GUI during this task.

## Method and checks

Local contrast-normalized structural patches near the selected vessel masks were matched within 56 px of the manual placement. Matches required distinctive correlation peaks and reciprocal agreement within 2 px. Frozen v3 copies of v9 CNV/ignored masks, dilated by 8 px, were withheld from feature placement; these frozen masks are exclusions only and do not drive the warp. Source validity masks remain enforced.

Deterministic 96-px spatial blocks assign training, model selection and audit sets. Training patches within 40 px of a reserved point are discarded. An affine RANSAC rejects training outliers only. At least 10 training, five model-selection and five audit points are required, with eight distributed training inliers. Rigid, similarity, affine and two regularized TPS models are compared. Global linear components are not faded; only the nonlinear residual fades beyond its training hull and near invalid data.

A more complex model must lower median model-selection error by at least 0.5 px without worsening the 90th percentile by over 0.5 px. A separate audit must confirm the median gain. Models with folds, maximum displacement above 60 px or local singular values outside 0.65–1.5 are withheld. These are exploratory engineering gates, not biologically calibrated acceptance limits. Audit points are automatically matched, so their agreement is not independent anatomical ground truth.

The initial attempt faded the entire correction at image boundaries and produced artificial strain. That attempt is retained in automatic_warp_pilot_20260922; this v2 run corrects the formulation, broadens the feature search and uses a 60-px rather than 40-px exploratory cap. Both runs are development on the same examples. The reported audit is held out from fitting/model selection within this run, but is not an untouched external test across development.

35 tests passed: four new synthetic tests (known scale and sampling direction, smooth local displacement on unseen points, reciprocal patch direction/unrelated texture, fold detection), plus existing registration, cohort, v3 search and persistence tests. Original source hashes were rechecked. Source copies and machine-readable metrics are included here.

## Limits and next step

Only eight pairwise trials were fitted. No per-field transform was propagated to the full montage, so neighboring overlaps, full-eye ONH consistency and across-date behavior have not been validated. That is required before integrating these warps into a montage. No segmentation was changed. Keep vessel caliber and CNV area in native calibrated images.

TIFF/PNG previews use the previously prepared display-normalized, cropped and rigid-resampled images. They are for review, not quantitative measurements. The final production renderer should compose the saved rigid placement and approved residual and sample the original full-field image once. residual_inverse_map.npz stores target-output to manually-aligned-moving displacement in pixels, with x in component 0 and y in component 1. The pair transform in result.json documents the additional native-coordinate composition.

Selected outputs are saved as proposed_moving.tif and proposed_valid.tif; target.tif and manual_moving.tif are included for Fiji. A baseline-retained case exports the unchanged moving image. All outputs remain unconfirmed drafts.
