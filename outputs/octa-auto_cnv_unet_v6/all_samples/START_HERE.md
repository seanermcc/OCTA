# CNV U-Net v6 · all processed acquisitions

**Batch complete: 324 acquisitions, 1,944 individual predictions, 11 animals.** The current counts are in [status.json](status.json) and every acquisition is accounted for in [scan_status.csv](scan_status.csv). The original pilot, all six trained B/C models and existing human annotations remain separate.

Open **[OPEN_CNV_REVIEW.cmd](OPEN_CNV_REVIEW.cmd)** for the updated original-prediction reviewer in **[../review/START_HERE.md](../review/START_HERE.md)**. The previous dedicated GUI and review information are preserved in `../old_review/20260914_231418/`. Original pilot files remain intact.

The [comparison index](comparison/index.html) provides read-only six-model overlays. Footprint editing and human decisions happen in the dedicated CNV GUI.

The current inventory is **324 distinct processed acquisitions from 332 files**, including eight byte-identical copies. This adds ten acquisitions to the historical 314. Eleven indexed acquisitions still lack a processed volume and are listed separately. Five July 28 TS336 scans retain their indexed D56 identifier although their current folder says D77; actual days after laser are unknown. See [metadata discrepancies](verification/metadata_discrepancies.json).

## Reviewing

The current GUI records independent B/C acceptable or unacceptable ratings per acquisition and seed. Manual annotations are optional read-only overlays, off by default. Delete false suggestions, explicitly confirm missed CNVs for the displayed model or both matching seeds, and optionally confirm gross outline corrections. Original predictions remain visible and unchanged after editing.

Save partial work freely. Finishing creates no whole-field background labels and does not require ratings, draft resolution, or reconfirmation of manual annotations. Active records, timing, logs and verification outputs now live in `../review/`. The next two filtered acquisitions are prefetched in memory.

See **[the new review guide](../review/START_HERE.md)**, **[human review status](../review/HUMAN_REVIEW_STATUS.md)**, and **[verification results](../review/VERIFICATION.md)**. `SUMMARIZE_REVIEW.cmd` updates the new status. Historical saved decisions are retained without converting them into model ratings.

## Outputs and reproducibility

- [models.json](models.json): exact checkpoint hashes, saved validation thresholds, channel order and training normalization. No retraining, normalization fitting or threshold tuning occurs.
- `predictions/B_267` through `predictions/C_269`: native float32 score maps, thresholded masks and component-label maps. `predictions/provenance/<scan_id>.json` retains each model's complete provenance and individual footprint runs under its B/C-and-seed key. No lesion-count, shape or size filter is applied. Scores are not calibrated clinical probabilities.
- `inputs`: native structural/OCTA projections plus provenance. The same frozen v6 automatic thickness policy is reconstructed from hashed raw upstream arrays; NaNs stay NaN until the established model-tensor neutral fill, paired with availability masks. Large immutable source arrays are referenced instead of duplicated because drive space is limited.
- `upstream_automatic`: frozen-model automatic inputs regenerated where human vessel/ONH influence was present, and inputs for newly processed acquisitions that lack prior exports. No manual correction or contextual estimate enters the model tensors.
- `records/<scan_id>.json` includes the complete annotation audit, evaluation and availability measurements. Preview media is packed losslessly into one `comparison/assets/<scan_id>.js` file per acquisition and loaded by the offline comparison index. This avoids the drive's 256 KB minimum allocation for every tiny image or metadata file.
- Frozen evaluation details use zero-based prediction indices; add one to find the corresponding native candidate-label ID or footprint-run ID. Reference indices address the nonempty exported positive instances after ignored-region handling.
- `references.zip` contains the byte-identical native reference arrays for each scan as `<scan_id>.npz`. The GUI and comparison tools read the archive directly. The original annotation files remain untouched at their provenance paths.
- [comparison/REPORT.md](comparison/REPORT.md), per-scan/stratified tables, spatial disagreement maps and individual seed-inconsistent suggestions. Existing annotation comparisons use the frozen v6 protocol, ignored regions and one-to-one matching. Legacy references without whole-field completion support positive-only comparisons.
- [verification](verification): source/grid/orientation checks, duplicate-file hashes, checkpoint identities, preservation checks and isolated GUI tests. [FINAL_VERIFIED.json](FINAL_VERIFIED.json) records successful native-output, model, provenance, preservation and GUI checks.
- [Runtime provenance](verification/environment.json) records the activated environment and numerical libraries. [Frozen implementation checks](verification/frozen_implementation_contract.json) verify the original numerical code and upstream dependencies.
- [unprocessed_acquisitions.csv](unprocessed_acquisitions.csv): acquisitions lacking processed volumes. No `.RAW` reconstruction is attempted.
- `failures`: specific failure traces and resume instructions. [RUN_ALL.cmd](RUN_ALL.cmd) resumes inference; [BUILD_COMPARISON.cmd](BUILD_COMPARISON.cmd) refreshes comparisons.

Orientation comes from `detect_orientation` and canonical images from `prepare_bscan`. Existing exports are reused only after source fingerprints, full derived-file hashes, checkpoint identities, all 512 raw neural records and the upstream native-grid audit pass. The original pilot, an additional representative acquisition per animal, affected human-mask exports, and newly processed scans receive fresh source reconstruction checks. The input sidecars distinguish these fresh rechecks from verified upstream reuse; no legacy sample orientation flag is trusted. OCTA always reads the actual source OCTA channel with the frozen mean-dB retinal-crop projection.

## Interpretation limits

This remains a pilot for human-reviewed suggestions. Predicting new animals does not establish generalization. The original train, validation and development-holdout scans are distinguished from newly processed scans, and exposure to both CNV and upstream layer models is recorded. Seeds, repeats and visits are not independent animals. Missing annotations are not negative labels.

Seed variability includes the original differences in validation-selected thresholds: B uses 0.7, 0.1 and 0.8; C uses 0.5 for all three seeds. Per-scan exposure distinguishes actual supervised CNV training inputs from unannotated scans merely allocated to a training visit. One-way report strata overlap and should not be added together.

The original normalization used the same annotated training acquisitions as supervised fitting. Unannotated training-visit scans were excluded from both. The inventory records normalization exposure explicitly; this batch only reads the original saved normalization.

Estimated additions, removals and outline corrections in comparison tables are **comparison-derived proxies**, not observed reviewer actions. Actual GUI interactions and human review findings remain separate. Thickness availability is the experimental v6 policy, not validated reliability.

Mean en-face projections discard axial position and layer relationships. Inspect linked native B-scans for persistent misses, artifacts, low support and field edges before proposing a larger or depth-aware architecture. Model disagreement alone does not establish the cause of an error.
