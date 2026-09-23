# octa-reg_v3 · pooled retinal montage release

All 324 acquisitions are accounted for in 19 separate animal-eye groups: **112 supported, 209 flagged, 1 unlocalized and 2 source exclusions**. Reviewed eyes preserve the user's saved geometry, categories and individual confirmations; the other 17 eyes were re-registered. All dates are pooled. This is a revised classical rigid-registration pipeline, not a newly trained neural network.

## What changed

The run evaluated **3,644 scan pairs and 23,864 candidate poses**, plus 57 graph-priority trials. It includes full-field SIFT on locally equalized structure and fine detail, two descriptor ratios/random seeds per channel, old v2 alternatives, CNV-center starting proposals, and multi-start refinement combining large and small vessel distances. Fine ridges are extracted at 1–3 pixel scales outside a seven-pixel trunk-centerline band and selected CNVs. These are image-derived candidate features: they capture small branches but can also include trunk edges, RNFL texture and acquisition artifacts. They are not new validated vessel masks. Fine texture is evaluated separately from large-vessel agreement. Candidate metrics, strongest rejected alternatives and ambiguity margins are saved per pair. Example overlays are in `verification/features/large_and_small_vessels.png`.

CNV locations contributed to ranking for 1502 pair comparisons; small-vessel evidence was available for 3263. These are availability counts, not correct-registration counts. Confirmed/manual CNVs have greater weight than predictions. Across dates the location weight is lower and shapes are not forced to agree, because lesions change. CNV agreement cannot independently pass the vessel gates. Explicit no-CNV fields are preserved as absence; unchecked or empty predictions are not negatives.

Three graph fits prioritize balanced evidence, fine detail or large vessels. Internal loop agreement and ONH conflicts choose a trial. Fields moving more than 50 pixels in corner RMS from v2 are flagged for review (95 automatic fields); tentative connections do not certify dependent fields. The final safety pass refits only supported observations. No image is resized, stretched, flipped or reconstructed from RAW.

## Your TS165 corrections

The exact source reviews are TS165_OD revision 81 (whole montage confirmed: False); TS165_OS revision 61 (whole montage confirmed: False). 20 fields were individually confirmed; 7 fields remain flagged. Manual ONH origins are carried forward. Inherited confirmations are explicitly identified as inherited and are not fabricated new review actions. v2 originals and all CNV annotations remain unchanged.

The automatic search was also checked against supported, individually confirmed TS165 placements, after aligning each result's reference field to the same human frame. The table reports median per-field corner-coordinate RMS discrepancy in native pixels (including the fixed reference), before substituting the exact human poses for delivery.

| Eye | Supported reference fields | v2 discrepancy (px) | v3 discrepancy (px) |
|---|---:|---:|---:|
| TS165_OD | 7 | 233.4 | 17.8 |
| TS165_OS | 6 | 8.7 | 23.2 |

OD improves substantially in this development comparison; OS does not consistently improve. Large errors remain for some fields. This is not held-out accuracy, and internal scores or a larger montage do not establish anatomical correctness. The source images with enlarged vessels have not been scale-corrected: changing physical scale would need acquisition calibration, not a cosmetic fit.

## Selected CNV sources

The input snapshot uses the latest v9 Model3 gallery and its current correction records. Corrections supersede earlier targets, followed by explicit absence, frozen manual supervision and confirmed model choices. Draft corrections contribute only explicitly kept regions with reduced weight; unsure/excluded pixels are masked. Predictions requested for correction are withheld when no correction or confirmed alternative exists.

- manual_correction: 34 fields
- manual_training: 100 fields
- confirmed_absent: 77 fields
- manual_partial: 8 fields
- confirmed_m3: 78 fields
- confirmed_m2: 10 fields
- automatic_m3: 2 fields
- flagged_prediction_withheld: 15 fields

`SCAN_PROVENANCE.csv` gives the chosen source, confirmation state and registration category per scan. `inputs/manifest.json` records hashes and immutable review snapshots. `registration.json` preserves raw graph results; `review_registration.json` contains the final safety pass; `automatic_trial_graph.json` preserves automatic TS165 alternatives. `development/round1` preserves the first TS165 trial. No segmentation labels, learned weights or source images were changed.

## Reviewer and reproducibility

Open `OPEN_REVIEWER.cmd` or http://127.0.0.1:8774/. Pink CNV outlines, day filters, flagged toggles, move/rotate, Move ONH, notes and categories are available. See `REVIEW_GUIDE.md` for saving and the downstream analysis contract. Native x-right/y-down orientation is preserved; anatomical NSEW remains unconfirmed.

Activate the `octa` conda environment, set PYTHONPATH to the repository `code` directory, then run `python -m octa_reg_v3.run --output <fresh-folder> --workers 4`, `python -m octa_reg_v3.finalize --output <fresh-folder>`, `python -m octa_reg_v3.publish --output <fresh-folder>`, and `python -m octa_reg_v3.report --output <fresh-folder>`. Input or algorithm changes require a new folder. Released review baselines must not be rebuilt after human v3 edits without explicit reconciliation.

`verification.json` records complete inventory, animal/eye isolation, rigid transforms, source hashes and exclusion checks. `UI_VERIFIED.json` records browser tests on isolated copies. These implementation checks are not registration accuracy validation.
