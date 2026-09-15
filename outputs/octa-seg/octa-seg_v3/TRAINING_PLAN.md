# octa-seg_v3 — CNV boundary training and independent review plan

Agreed direction: September 14, 2026. This folder contains the new annotation
workflow and the plan for subsequent training. The current release does not
train a new network or establish validated measurement performance.

## Objective

Preserve the current model's useful segmentation in readable tissue and improve
its boundary positions and uncertainty decisions around CNV and the ONH. Produce
three distinct display/reporting outcomes at each boundary and native A-line:

1. A supported working boundary, with a measurable position when validated.
2. An uncertain but plausible boundary candidate, retained as a separate estimate.
3. No defensible trace, with the reason preserved.

Within the third outcome, distinguish insufficient image visibility from an
explicit anatomical-absence/interruption judgment. If a reviewer cannot decide
whether the tissue is absent or merely obscured, anatomical status remains
unknown. Do not require a curve in an anatomically absent or untraceable region.
An uncertain position must not silently become an ordinary thickness measurement.

The current eight boundaries are ILM, RNFL/GCL, GCL/IPL, IPL/INL, INL/OPL,
OPL/photoreceptor composite, photoreceptor/RPE, and the outer RPE edge. The
photoreceptor composite includes ONL and photoreceptor structures; there is no
independent ONL or BM output in this model. All eight boundaries remain in review.
Published anatomy can inform the labeling convention, but it is not positional
ground truth and must not force CNV tissue toward normal thicknesses.

## Workload and sampling

Start with **120 distinct B-scans**, not 120 volumes. Review in short rounds and
expand the lead's total toward 150–200 only if the results justify more work.

| Reviewer | B-scan reviews | Assignment |
|---|---:|---|
| Lead reviewer | 120 | 90 development + 30 reserved assessment |
| Main collaborator | 60 | 30 shared development + the 30 assessment cases |
| Each additional collaborator | 30 | The same shared development set |

With the lead and three colleagues this is 240 reviews of 120 unique B-scans.
The shared cases are already included in the lead's 90 development cases.
Counts are a practical starting budget, not a power calculation or guarantee of
sufficient evidence for every boundary and state.

Suggested development allocation: 50 CNV, 15 ONH, 10 shadow/low-signal/artifact,
and 15 clearly readable examples. These four categories are sampling tags, not
boundary-quality labels, and the GUI permits overlap. Track the actual mix;
do not add overlapping category counts as though they were distinct cases.

Manually browse and flag failures, but deliberately include correct-looking and
clearly readable regions. Sample CNV centers, margins, and transitions into
readable tissue across distinct lesions, animals, eyes and visits. Use true
days-post-laser where available. Avoid spending most of the budget on consecutive
slices through one lesion. Neighboring slices provide visual context without
requiring their annotation or treating them as independent subjects.

The shared development set should contain about **20 especially ambiguous cases
and 10 moderate/clear cases**. The “Especially ambiguous” bookmark identifies the
hard subset; “For review” selects cases for export to colleagues. These flags
are independent so clear controls can also be shared.

## Review procedure

1. Agree on anatomical conventions using 5–6 practice examples. Review the GCL
   dark-band convention, the two RPE-complex endpoints, CNV disruption and ONH
   termination. Practice is excluded from agreement estimates.
2. The lead corrects/approves development cases and records local state marks.
   A B-scan category or a completion checkbox does not approve its boundaries.
3. Every collaborator uses a distinct reviewer ID. Independently annotate shared
   cases before discussing them, without seeing the lead's corrections or other
   reviewers' traces. Keep the same frozen automatic starting provider.
4. Most work may correct the existing curves. For 8–10 shared cases, trace selected
   regions without automatic overlays. The GUI export selects up to five flagged
   ambiguous cases and five other shared cases to start with overlays hidden;
   the actual number is displayed and saved. If the set has insufficient controls,
   add them rather than assuming the blind subset is balanced.
5. Assessment reference traces should be drawn independently with automatic
   overlays hidden. Record any later reveal. Neighboring raw B-scans remain
   available, while model-derived thickness is hidden in this mode.
6. Discuss disagreements afterward. Save original independent annotations; future
   adjudication must use a separate reviewer ID and retain those originals.

Corrections preserve the original editor's direct click/drag behavior and
30-A-line software joins. Exact stroke columns, joined columns, ordering
displacements, explicit approvals and untouched model values are separate.
Joined or displaced segments must not become manual position targets.

Mark uncertainty on the specific boundary and interval. A readable ILM does not
become untraceable merely because the outer RPE is disrupted. Broad image
exclusion is appropriate only when the whole column is unusable. A local
visibility or reliability denial has no effect on neighboring boundaries.

An explicit reliable judgment is valuable even if no position needed correction.
Missing marks remain unknown. The drawing mode records an explicit judgment:
**Draw as unreliable ON** records an uncertain best guess; **OFF** records a
reliable correction. This applies only to exact stroke columns, never software
joins. Older strokes without a mode keep their original unknown reliability.
A manually drawn guess and its ambiguity are retained during training.
An unchanged approved automatic curve remains
explicitly approved, never described as a manual stroke.

## Independent assessment and leakage prevention

Reserve 30 assessment cases before selecting by model error, with systematic or
random sampling across the intended contexts. Human reference collection is
separate from development fitting and operating-threshold calibration. The v3 GUI
retains the previous v2 queue's reserved assessment roles; it does **not** silently
claim that a new 30-case assessment set has already been collected. Assign and
freeze the remaining assessment cases before the first v3 training round.

Use animal-level partitions for animal-excluded claims. All eyes, visits, nearby
slices, crops and augmentations of one animal must remain in that animal's role.
Starting weights must also exclude the evaluation animal. The current all-label
checkpoint has already seen much of this cohort; holding out newly annotated
slices from a new fine-tuning run establishes only development assessment.

If assessment results repeatedly guide model changes, call them development
validation. An untouched final test needs a separate, genuinely excluded animal
set or future acquisitions from new animals, with checkpoint ancestry audited.
Confidence intervals and summaries must account for clustering by animal/lesion;
thousands of neighboring A-lines are not thousands of independent examples.

## Training in rounds

Collect approximately 40–50 development cases first. Check time spent, annotation
consistency, and positive/negative support by boundary and animal before training.
Use the remaining development budget to address persistent failures.

1. Freeze a versioned snapshot of explicit GUI evidence and data roles. Preserve
   reviewer identity, native coordinates, source/model identity, visibility,
   reliability, anatomical status, stroke provenance and independent traces.
2. Update reliability/traceability with the position branch frozen first. Keep
   anatomical absence distinct from image traceability in supervision; do not
   infer absence from historical “not visible” marks.
3. Fine-tune positions only where human evidence supports the target. Maintain
   separate reliable-manual, ambiguous-manual and explicitly-approved-position
   pools. Do not train guesses as exact reliable positions. Compare manual-only
   versus approved-position sensitivity results.
4. Use ambiguous independent traces to characterize disagreement. Similar traces
   can support a central estimate plus empirical spread; incompatible anatomical
   interpretations require adjudication or multiple hypotheses, not blind averaging.
   With a small shared set, empirical spread is not a calibrated confidence interval.
5. Balance by animal, case, boundary and affirmative/negative evidence. A broad
   unreliable strip must not overwhelm sparse clear examples through its pixel count.
6. Compare against the frozen current model and the frozen-position alternative.
   Retain good-tissue examples in training and assessment to detect regression.
7. Export an immutable new round. Never train after each click or reuse generated
   candidates as independent human evidence.

The v3 release deliberately stops at annotation, sharing, and tested target
interpretation. Model training, new absence prediction, adjudication analysis and
calibration are subsequent stages once sufficient real labels exist.

## What improvement must demonstrate

Report results separately by boundary and CNV interior, margin, ONH, readable
tissue and obscuration context. Report missing context as unknown.

* Position error in micrometers on eligible visible reference segments, including
  median, upper-tail error and the length of spatial failure runs.
* False-solid reporting in explicitly ambiguous, untraceable or absent regions.
* Retention of explicitly reliable boundaries. Withholding everything is not success.
* Candidate usefulness: how often reviewers retain/correct/reject uncertain proposals,
  and how far they move them.
* Between-reviewer disagreement on position, traceability, reliability and anatomy.
  Agreement after shared discussion is different from independent agreement.
* Review time, split by correction/approval/state marking. Pilot the first ten
  cases; do not assume that a fast completion click is genuine review.

Stop expanding the annotation effort when new batches no longer yield useful
improvements relative to their labeling cost, or when remaining errors reflect
irreducible ambiguity. Report unreliable layers explicitly rather than dropping them.

## Methodological references

* [AI collaborative annotation and independent quality checking](https://www.frontiersin.org/journals/radiology/articles/10.3389/fradi.2023.1202412/pdf).
* [Probabilistic U-Net: retaining multiple plausible segmentations](https://arxiv.org/abs/1806.05034).
* [ValUES: validate uncertainty for its intended task](https://proceedings.iclr.cc/paper_files/paper/2024/hash/1548d98b62d3a4382a31ba77d89186cd-Abstract-Conference.html).

These motivate the study design; they do not establish a sample-size requirement
or performance claim for this tree-shrew dataset.
