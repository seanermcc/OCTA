# Checkpoint 1 — full manual cohort frozen; execution continues

The user authorized use of any/all labeled animals. This new dataset includes 102 corrected B-scans from nine animals, plus 59 rejected decisions retained only in the audit. The original 101-label cohort is present, with one newer annotation added. All corrected B-scans contain eligible manual evidence.

Ground truth uses exact drawn-column provenance for the new annotation and the documented edited-surface approximation for legacy labels. Untouched automatic surfaces, displaced positions, invisible or unreliable boundaries, excluded image regions, and shadows do not supply training targets. Manual geometry is retained irrespective of biological footprint status; original Stage A remote/control masks remain available for sensitivity analysis. No within-lesion reliability claim is being made.

The old dataset and its historical test allocation remain unchanged on disk. In this new development dataset, the former test animals have been released by the user and no untouched final-test estimate is claimed. Nine animal-excluded models train with seven other animals; a distinct animal calibrates each entropy cutoff. A separate model trained on all nine animals is for experimental inference and never contributes an independent accuracy estimate.

Training uses the fixed 124-epoch budget, eight boundary heads, and the previous architecture. BF16 convolutions reduce GPU memory use; the objective and optimizer remain FP32. Reduced-precision batched versus individual gradient directions had cosine similarity above 0.9997 in the check, with about 2.0–2.3% relative gradient differences from kernel rounding. Changing one model's input left another model's output exactly unchanged. This is numerically different from the previous FP32 run and is not described as a bitwise reproduction.

The initial ten-model simultaneous schedule was stopped before completing an epoch because it overfilled available GPU memory and slowed execution. No completed weights were used from that attempt. The nine cross-validation models now train together with cached CPU samples; the all-label model follows in its own group. Each completed epoch saves a resumable checkpoint.

The full-cohort classical comparison and prerequisite audit run alongside training. Reports, images, and review packs will be added as their computations finish. This checkpoint is an output, not an approval gate or a stopping point.
