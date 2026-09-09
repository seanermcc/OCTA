# Separate supporting investigation: withholding

Authorized to run by the user on 2026-09-08. This replaces the queued timing
and shared-branch instructions for this investigation only. No training run.

1. Read frozen train/development-validation predictions and feature arrays;
   count distinct crossing A-lines, flagged surfaces, overlap with existing
   exclusions, and additional human-supported surface-columns lost. Repeat
   crossing counts on the existing TS165 WT volume (not a general volume rate).
2. Characterize classical-shadow misses and false exclusions, including overlap
   with the existing train-derived entropy-plus-signal score at q0.94/q0.96.
   The 7,447 number is an overlap, not the number partially protected.
3. Simulate whole-column, high-crossing-count, and nonadjacent crossing-span
   rules on the SAME frozen predictions. Current crossings are adjacent pairs;
   an intervening-surface variant must explicitly inspect nonadjacent pairs.
4. Compare leakage and retained errors at matched HUMAN-POSITIVE surface-column
   coverage, including shadowed but human-supported boundaries. Report legacy
   valid-only coverage separately. Thresholds for operational examples come
   from training only. Coverage matching on validation is descriptive only,
   never calibration or selection of a deployment threshold. Include coverage
   mismatch from discrete scores. Report absolute costs, per animal and QC.
5. Inspect representative overlays, including useful tissue lost and remaining
   failures. Write a decision before any stage_a package changes. A negative
   result is a completed investigation: no speculative production fix required.
6. Only if justified, implement separately and compare with fixed predictions.
   Do not combine with longer training. Any candidate must be retested after
   longer training because crossing and uncertainty distributions can change.

Outputs and analysis code stay in this folder. Preserve v2/v3, human labels,
checkpoints, partitions, footprints, and the training package. Read no final-test
animal arrays or repeatability data. Metadata may be read for isolation checks.
Use read-only provenance checks; the standard report and test entry points write
into v2, so run tests via a wrapper with temporary metadata fixtures here.

Two corrected development-validation animals only; the WT volume belongs to
training. Unknown is not readable. Classical masks are comparators, not truth.
No calibrated threshold, acceptance criterion, or production-readiness claim.
