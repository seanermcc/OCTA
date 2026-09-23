# CNV v9 Model 3

**Correction queue (September 22):** open **OPEN_MODEL3_CORRECTION.cmd** for the
57 flagged samples remaining after excluding the 10 also confirmed for Model 2.
The latest desktop editor loads Model 3 outlines and preserves the original
review notes. See [correction instructions](correction/START_HERE.md).

Open **OPEN_GALLERY.cmd** to compare the original Model 2 and Model 3 at http://127.0.0.1:8803 once the run completes. The original v9 gallery on port 8799 remains separate.

Model 3 uses exactly the user-selected inventory: **73 confirmed positive scans, 28 confirmed no-CNV scans, 156 kept lesion observations**. These are 101 unique acquisitions, not 156 unique biological lesions. Uncertain-only, deferred and unconfirmed fields are excluded. Unknown regions inside a confirmed positive field remain masked.

- **Manual confirmed CNVs** toggles the frozen human-confirmed training footprints on both model panels and in the linked B-scan band. It includes hand-corrected and explicitly approved model outlines. A missing manual overlay is not a negative label; the reference status says whether absence was confirmed.
- **Confirm Model 2/3 CNVs** approves that model's adjusted result for the entire field. It does not approve recovered hidden candidates.
- **no CNVs present** explicitly confirms absence across the entire assessable field and clears both model confirmations. It is independent of whether a model predicted candidates.
- **Review Model 3** marks a scan for later correction and clears Model 3 approval.
- Decisions save to this release's `manual_review/decisions` and immutable revision history. Wait for **Saved to disk** before closing. Earlier reviews and training targets are never rewritten.

The full 324-image gallery includes training fields, marked as such. Predictions are proposals for review, and the full-cohort display is not an independent accuracy test. Manual references stay frozen to the training snapshot even when a new review disagrees.

Model 3 retains Model 2's 30-channel U-Net, loss, sampling, 100-epoch/3200-step schedule and thresholds. It is retrained from fresh initialization on the expanded dataset. A new candidate scorer is fitted using three animal-excluded networks. Those folds provide scorer training examples, not a claimed independent evaluation of the final adjusted model.

One requested negative scan has a historical vessel-context exclusion; the current explicit 101-scan training request takes precedence for its CNV label. The excluded vessel/ONH annotations are withheld as missing channels. Both historically excluded context scans are included in the requested full-cohort inference, with the exclusion notes visible.

Use **RUN_OR_RESUME.cmd** to resume interrupted computation. Source hashes, frozen targets, training contracts, epoch checkpoints and all raw probabilities are retained here. See `DELIVERY_COMPLETE.json` for completed counts and `FINAL_VERIFIED.json` for final verification.
