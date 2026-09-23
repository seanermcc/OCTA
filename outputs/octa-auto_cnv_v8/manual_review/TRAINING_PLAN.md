# Next CNV model after manual correction

The immediate deliverable is corrected, explicitly confirmed footprint supervision for these 30 scans. Model training does not run from this editor. Complete or explicitly defer every scan; inspect outside Model 1's footprint to recover small or unusual lesions suppressed by its conservative policy. Retain useful no-CNV fields and rejected false-positive locations.

## Freeze the reviewed dataset

Refresh quantification and audit every current confirmation, source identity, image quality flag and uncertain area. Resolve accidental region overlaps, merged biological lesions and fragmented outlines. Record genuinely clipped/uncertain lesions as partial size observations. Freeze the report, label hashes/revisions, proposal provenance and derived-target manifest together before training.

Use the latest explicitly confirmed correction as the source for an acquisition. A new draft/deferred correction blocks fallback to an older label for that acquisition until reconciled. Other validated historical acquisitions can be retained once source precedence is audited. Never union contradictory historical sources or use model proposals as targets. Positive footprints, reviewed background and ignored tissue remain distinct; the loss must be masked over ignored pixels. Human-corrected small footprints are retained regardless of the model's old 64-pixel filter.

## Use size distribution to improve sampling

Review `lesions.csv` and both size distributions. Use complete, nonoverlapping, connected, nontruncated confirmed lesions to estimate full-size strata; keep visible-area measurements of incomplete lesions separately. Preserve all confirmed pixels for masked segmentation supervision, even when the full lesion size is unknown.

For each training fold, derive small/medium/large strata from the training animals only (for example training-area tertiles on a log-area scale); freeze cut points before evaluating the excluded animals. Do not derive bins from the entire dataset before splitting. Inspect the sample count per size group; with very few lesions use fewer strata instead of unstable bins.

Start sampling by animal, then acquisition, then lesion/size group to prevent repeated scans and large lesions dominating. Increase representation of the underrepresented small-lesion group without discarding common sizes. Include ordinary confirmed background, confirmed no-CNV fields and false-positive regions rejected by the reviewer as difficult background. Preserve the full corrected footprint in the target. Do not force predictions to resemble the observed size histogram or reject unusual shapes merely because they are uncommon.

Candidate changes to compare: baseline Model 1 recipe using the expanded corrections; the same recipe with balanced lesion-size sampling; then a separately controlled loss or postprocessing change only if needed. Compare raw probability/threshold outputs and any filtered display output separately so a filter cannot hide missed small lesions. Check sensitivity to the approximate physical calibration; native pixel-area ordering is unaffected by a common scale factor.

## Evaluation and model selection

Group splits by animal, retaining all eyes, visits and repeat acquisitions of an animal in the same split. These 30 scans contain ten training/reference cases and twenty newly labeled acquisitions, but every animal has already been exposed to v8 training. They cannot establish generalization of the existing v8 checkpoint to unseen animals. For animal-excluded evaluation, fit fresh models and normalization using only each fold's training animals; do not initialize from the all-animal v8 checkpoint. A later untouched-animal test remains desirable.

Select thresholds and any component filtering on a separate calibration subset within the allowed training animals. Report lesion detection recall and precision, false positives per acquisition, footprint Dice/IoU, and area error on an adjudicated lesion matching scheme; inspect split/merge cases explicitly. Report results by lesion-size stratum, animal, acquisition quality and field truncation. Pixel Dice alone is insufficient for a conservative detector that can miss small lesions.

Report acquisition-level total-area error alongside per-lesion area error. Keep repeated observations grouped by animal/eye/visit; do not count repeated acquisitions as independent lesions. Confidence intervals, when supportable, should resample at the animal level. The reviewed 30 are a selected correction set, so their size distribution is a training-sampling aid and a description of this set, not population prevalence.

After review, the next concrete decision is whether the confirmed size groups contain enough examples for this comparison or whether another targeted correction round is needed. Record that decision and training/calibration/evaluation manifests before fitting the next version.
