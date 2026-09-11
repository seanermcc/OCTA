# Manual review: annotator intent, audit, and proposed next steps

Recorded 2026-09-09 from the annotator's clarification in the review conversation.

## Annotator intent — preserve when interpreting these labels

The annotator states: "when i labeled things as unreliable, i still tried to do my best to make a segmentation". These are intentional best-effort estimates, especially around suspected CNV and difficult image regions. They are not accidental edits or assertions of high-confidence boundary location. The annotator wants to investigate whether repeated inspection and semi-automated correction can help compared with fully manual or fully automated segmentation.

Preserve both the trace and its uncertainty flags. Do not silently promote unreliable or unidentifiable traces to trusted position targets or accuracy references. Potential uses are a separate uncertain-annotation dataset, repeated-review agreement, and a future explicitly evaluated weak-supervision experiment. Current position-target exclusions remain in force. No human labels have been edited by this audit.

The conversation's earlier explanations of visibility versus reliability overlapped. This round should therefore be treated as an initial annotation pilot, not perfectly calibrated classes. In the current GUI, drawing sets local visibility to yes over the stroke but does not clear local unreliability. Subsequent invisibility marks can coexist with drawing history. These combinations are not automatically errors.

## Saved-label audit

At inspection: **35 of 36 candidate files saved: 31 corrected, four rejected.** No label for `TS325_OD_2026-05-26_6mo_s01_112940_b0377` was found in the review destination or elsewhere under outputs. It may still need an explicit save/verdict in the GUI; absence does not establish that the user did not inspect it.

There are 1,830 recorded strokes. Of 54,893 boundary-column positions with drawing history, 10,042 also carry unreliability and 6,036 carry unidentifiability; these categories overlap. Another 975 drawn positions were subsequently displaced by ordering. Those stored displaced rows are not direct evidence of the original human location. The audit identifies 34,591 candidate position columns after verdict, provenance, flags, exclusion, shadow, finite-value and image-bound checks. This is evidence availability, not an independent accuracy score.

All 35 label SHA-256 fingerprints were unchanged during the audit. Details: [summary](audit/summary.json), [per-image counts](audit/label_audit.csv). These labels are model-assisted corrections; they are not a blinded fully manual reference. A rejected verdict alone does not identify which local boundaries were unidentifiable.

## Four initial visual checks

The figures show image only, all saved curves, and direct strokes. Dashed direct strokes have visibility or reliability denied. The final panel excludes ordering-displaced strokes and whole-column exclusions. Solid strokes mean no denial, not an independent claim of correctness.

1. **TS165 WT b0080:** marked structural discontinuities, clipped upper contour, and weak central signal. Broad central and right exclusions are recorded. This demonstrates appropriate refusal to force an entire stack through poor evidence, but review whether each excluded interval truly lacks every usable boundary. It is a WT-labeled volume: this appearance must not be called CNV from the image alone. [View](audit/TS165_OS_2025-04-29_WT_s02_121711_b0080.png)
2. **TS247 D21 b0131:** many saved curves remain automatic; local manual strokes and uncertainty marks occupy only selected intervals. That is acceptable. Untouched curves must not become human position targets simply because this B-scan is corrected. [View](audit/TS247_OD_2024-11-06_D21_s03_104157_b0131.png)
3. **TS283 D7 b0089:** a steeply sloping retina and repeated vertical low-signal interruptions; the RNFL/GCL trace contains local upward excursions with uncertainty marked over portions of them. Review the intended anatomical edge at those excursions, using adjacent B-scans if necessary. This is a review question, not a finding that the annotator is wrong. [View](audit/TS283_OD_2025-01-29_D7_s02_123712_b0089.png)
4. **TS325 6mo b0106:** central/right inner and outer traces include dashed uncertainty intervals while other direct traces remain. This is the intended local distinction: keep the attempted geometry and mark its limitations. Confirm disputed stretches on a clean image and neighboring slices before treating their location as reference. [View](audit/TS325_OD_2026-05-26_6mo_s01_112940_b0106.png)

These four selected images establish recorded annotation behavior, not biological ground truth or whole-cohort segmentation accuracy.

## Proposed plan — no model training launched

1. Save/resolve b0377, then freeze an audited manifest of this review round while preserving original files.
2. Review the four examples together: check intended edge, whole-column versus boundary-local exclusion, and ordering-displaced strokes. Record disagreements as questions; only the user changes labels through the GUI.
3. Create separate derived evidence groups: confident direct positions, uncertain best-effort traces, explicit visibility/reliability decisions, and unknown/unreviewed positions. Do not train an invisible-position target. Keep all eight boundary outputs; report evidence sufficiency separately for every boundary/layer.
4. Add provisional descriptive strata for interpretation and sampling. Use two separate axes: (a) readability/artifact, recorded locally per boundary; (b) apparent structural pattern — layering largely preserved, predominantly outer-retinal disruption, disruption extending through multiple layers, or indeterminate. These are proposed descriptive labels, not confirmed CNV types. No sample has been assigned a new biological class. Check adjacent B-scans, lesion footprint/context and paired OCT-A when available before attributing the appearance to CNV; indeterminate stays indeterminate. This deliberately difficult queue cannot estimate how common each pattern is in the study.
5. Run a small repeat-review pilot on clear, uncertain and severely disrupted intervals. Have the same reviewer repeat a clean-image trace without the old overlay after an interval; obtain a second reviewer if feasible. Compare fully automatic output, model-assisted corrections, and blinded manual repeatability, with review time and measurement coverage. The existing model-assisted traces alone cannot establish a fully manual-versus-semi-automated accuracy comparison.
6. First test current U-Net + ordered decoding with per-boundary reliability decisions using the trustworthy local evidence. Preserve animal-disjoint training/calibration/evaluation. These four animals have already contributed to the all-label model, so its fit to these images is not independent validation; use models that excluded the evaluated animal or retrain the corresponding folds. There is no untouched final test set in the released cohort.
7. Only then consider an uncertain-trace training arm, separately weighted and clearly identified as exploratory. Compare it with confident-only training on the same independent confident reference and at matched retained coverage. If it harms trustworthy positions or merely hides more tissue, do not adopt it. Never use uncertain traces as the reference proving that this arm works.

The next immediate action is joint review of the examples and the missing-save check, not an unattended retraining run or a biological reclassification.
