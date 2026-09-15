# octa-seg_v3 — whole-B-scan review and training plan

## Status and objective

This is the revised contract for the replacement GUI in `review`. It becomes operational when the accompanying implementation specification is implemented and verified. The existing GUI's completion checkbox does not implement this contract. No new model is trained, no historical annotations are relabeled, and no completed review dataset is claimed by writing this plan.

Improve boundary positions and decisions about uncertainty around CNV centers, margins and transitions while retaining useful segmentation in readable tissue. Include ONH and low-signal/shadow cases. The reviewer edits one working segmentation initialized from automatic predictions, records exceptions and confirms the entire B-scan.

The current model has eight boundaries: ILM, RNFL/GCL, GCL/IPL, IPL/INL, INL/OPL, OPL/photoreceptor composite, photoreceptor/RPE, and the outer RPE edge. The photoreceptor composite includes ONL; there is no independent ONL or BM output. Review all eight. Published healthy thicknesses can inform anatomical conventions but are not positional truth and must not force CNV anatomy toward normal thicknesses.

## Central rule: confirmation approves the final segmentation

**An unchanged automatic curve that a reviewer explicitly confirms as part of the entire B-scan is approved positional training evidence; redrawing an already-correct curve is not required.**

**Confirmation includes inspected corrections, retained automatic positions, software-joined portions and neighbors moved to accommodate a correction. Their origins remain recorded. Explicit unreliable, not-traceable, anatomical-absence and image-exclusion judgments remain exceptions.**

This deliberately supersedes the older drawn-only convention for records created under this NEW explicit confirmation contract. It does not reinterpret historical generic Accept buttons, completion metadata, sampling flags, or partially reviewed ranges as full approval.

Confirmed means the review is complete. It does not mean all boundaries are reliable everywhere, the whole volume has been reviewed, or the automatic model has been validated.

## Reviewer workflow

1. Open a selected B-scan or resume it from **My saved reviews**. Inspect the whole width and every boundary; use neighboring slices and en-face context as needed.
2. Correct the automatic curves directly. The active drawing takes priority and conflicting neighbors move to preserve order. Inspect those moved neighbors and the joins as part of the final result.
3. Use the separate right-side **Unreliable** and **Not traceable** marking tools on the selected boundary and span. Draw an uncertain best guess only where such a position is defensible. Mark entire columns unusable only when that applies to every boundary.
4. Inspect the final all-boundary view and click **Confirm entire B-scan** once. No partial confirmation or separate candidate approval is required. The confirmation means: “I reviewed all boundaries across this B-scan. The remaining positions are acceptable except where I explicitly marked uncertainty, lack of traceability, or unusable image.”
5. Resume later from the saved-review list. Yellow navigator lines identify existing work: solid for confirmed and dashed for drafts/legacy unconfirmed reviews. Revisiting a case opens its saved segmentation rather than creating a duplicate.

Work autosaves as Draft before confirmation. Reviewers can pause at any time. A draft is not a whole-B-scan-approved training example; collection exports must identify and exclude drafts from that pool.

### Required record after confirmation

1. **Approve inspected unchanged automatic portions and corrected portions.** Default model uncertainty does not override an explicit reviewer approval of a defensible position.
2. **Preserve all explicit exceptions.** Unreliable, not-traceable, absent/interrupted and excluded portions do not become reliable positional targets, and no missing curve is invented.
3. **Approve inspected final neighbor and join positions.** Ordering displacement or taper alone is not human evidence; subsequent explicit whole-B-scan confirmation provides approval. Preserve software origin and human approval as separate facts.
4. **Resolve unexplained gaps and invalid geometry before completion.** The GUI must identify the affected boundary/region. An explicit uncertainty/no-trace/exclusion judgment is a legitimate resolved outcome. Hidden display elements and arbitrary numeric spans cannot silently narrow confirmation scope.
5. **Freeze the confirmed result.** Save the final positions and states, full-width/all-boundary scope, approved masks, reviewer, scan/native geometry, model/provider identity, annotation revision, data role and confirmation time. Retain original predictions and history behind the scenes.
6. **Require reconfirmation after substantive changes.** Later edits to positions, reliability, traceability, anatomy or exclusions, or adoption of changed predictions, return the record to Draft/Needs reconfirmation. Notes, navigation and sharing tags do not invalidate it. Historical confirmed snapshots remain available.

The right-side GUI key must show in bold:

**Confirm entire B-scan approves the final segmentation, including unchanged automatic curves. Your unreliable and not-traceable marks remain exceptions.**

## Two separate local judgments

| Judgment | Reviewer meaning | Display and training interpretation |
|---|---|---|
| Reliable/approved | The final boundary is acceptable at this position. | Solid curve; eligible positional target subject to the masks and data roles below. |
| Unreliable | A plausible position can be suggested, but it is uncertain. | Dashed candidate; negative reliability evidence. Preserve a defensible supplied position for ambiguity-aware analyses, not as an exact reliable target. |
| Not traceable | The image does not support placing this boundary here. | Gap; negative traceability evidence. No exact positional target is supplied. |
| Anatomically absent/interrupted | The reviewer explicitly judges anatomical absence/interruption. | Optional separate anatomical label and no ordinary boundary target. Do not infer this from poor visibility. |
| Unusable image | This column span is unusable for all boundaries. | Global exclusion; no positive positional target or filled thickness value. |

Unreliable and not traceable remain distinct buttons and distinct data fields. Switching tools alone creates no judgment. Clearing a mark restores unknown unless the reviewer explicitly affirms a state or confirms the completed B-scan. Reliability restoration does not cancel a traceability denial or anatomical-absence judgment.

Missing human judgments remain unknown in drafts and historical records. Under the new full confirmation contract, acceptable finite positions outside explicit exceptions receive affirmative approval even if no manual stroke was needed. No-trace regions supply traceability supervision without requiring a guessed coordinate.

## Positional training targets and provenance

The usable training segmentation is the final human-reviewed result, with a mask identifying where reliable positions were approved. The UI shows one working segmentation. Internally retain:

- Frozen starting predictions and model/source identity.
- Exact human strokes, software joins and ordering displacements.
- Coordinate-specific final human approval, including unchanged automatic positions.
- Per-boundary traceability, reliability and anatomical judgments, plus image exclusions.
- Reviewer identity, revisions, timing, display/context exposure and data role.

Build the reliable positional target mask from explicit new-contract approval and appropriate state/geometry masks. It must include unchanged and software-adjusted final coordinates approved by the reviewer; a drawn-only filter would incorrectly discard valid evidence. Origin labels support sensitivity analysis, not a requirement to redraw every correct curve.

Exclude explicitly unreliable, untraceable, absent, globally excluded and geometrically invalid positions from reliable hard targets. Preserve the established shadow exclusion policy; a model vessel footprint is not itself a human no-trace judgment. Any future change allowing reliable positional targets in automatically shadow-flagged columns needs a separately specified and tested policy. Uncertain/untraceable/shadowed endpoints do not produce ordinary thickness measurements; preserve NaNs without filling or smoothing.

Keep ambiguous manually supplied or explicitly retained candidates with their state and provenance. Merely storing a numerical model value in a not-traceable or excluded region does not make it human positional evidence. Independent ambiguous traces can support disagreement-aware objectives after their validity is assessed.

Historical labels retain their original eligibility rules and provenance. The old v3 completed checkbox alone remains metadata. A reviewer may reopen an old case and explicitly confirm it under the new contract, saving a new revision with the original intact. Never bulk-upgrade old completion/acceptance flags to positional approval.

## Collection budget and sampling

Start with the existing provisional budget of **120 unique B-scans**, not 120 volumes:

| Reviewer | Planned reviews | Assignment |
|---|---:|---|
| Lead | 120 | 90 development + 30 reserved assessment |
| Main collaborator | 60 | 30 shared development + the same 30 assessment cases |
| Each additional collaborator | 30 | The same shared development set |

These are planned counts, not a completed assignment or evidence of adequate statistical power. With the lead and three colleagues the plan totals 240 reviews of 120 unique B-scans.

Suggested development allocation remains 50 CNV, 15 ONH, 10 shadow/low-signal/artifact and 15 readable examples. Tags may overlap; report actual unique-case counts rather than adding overlapping tags as disjoint observations. Prioritize suspected gross segmentation errors at CNV centers and edges, include transitions into readable tissue, and spread work across lesions, animals, eyes and visits. Use true days post laser where known. Keep correct-looking/readable controls to detect regression and provide affirmative reliability evidence.

Avoid consuming the budget with consecutive slices through one lesion. Neighboring slices are useful context, not independent subjects. Review-priority scores and model uncertainty are candidate-selection aids, not known error measurements or acquisition-quality labels.

## Independent review, saved cases and discussion

Use distinct reviewer IDs. Each reviewer can navigate their own saved drafts and confirmed cases, resume unfinished work, filter flagged cases and see yellow reviewed-row indicators. The lead can display saved work with colleagues in an explicitly identified discussion mode.

For independent shared annotation, everyone begins from the same frozen automatic release and sees only their own corrections. Export case assignments without the lead's traces or judgments. Discussion of the lead's completed work must not silently become independent annotation; retain exposure information and original independent records. Adjudication, if performed, is a separate traceable record rather than overwriting either reviewer.

Use 5–6 practice examples to align anatomical conventions, especially the distinct dark GCL band, RPE endpoints and disrupted CNV/ONH anatomy. Practice does not contribute to independent agreement estimates. Aim for about 20 especially ambiguous and 10 moderate/clear cases in shared development. Retain an 8–10-case subset with model overlays hidden to examine anchoring; final confirmation still applies only to defensible supplied positions and explicit exceptions, not hidden model coordinates.

Assessment reference traces should be obtained independently with automatic overlays hidden before any reveal. Record later exposure; keep model-derived thickness hidden during blind tracing. A blindly reviewed no-trace interval needs no invented curve. Familiarity after discussion is different from independent agreement.

## Data roles and assessment

Freeze the 30 assessment cases and their roles before the first training round; do not claim the existing small reserved queue already constitutes all 30. Select assessment cases systematically or randomly across intended contexts rather than selecting only obvious failures. Keep fitting, operating-threshold calibration and assessment distinct.

For animal-excluded claims, all eyes, visits, nearby slices, crops and augmentations from one animal must remain in one role. Starting weights must also exclude assessment animals. The current all-label checkpoint has prior exposure to much of the cohort; newly held-out slices from those animals are development assessment, not an unseen-animal final test.

If assessment repeatedly guides changes, call it development validation. A final test requires genuinely excluded animals or new acquisitions with checkpoint ancestry checked. Summaries and uncertainty estimates must account for clustering by animal/lesion, not treat thousands of adjacent A-lines as independent samples.

## Training in rounds after GUI collection

Collect roughly 40–50 completed development reviews first. Audit confirmation semantics, usable boundary/state coverage, reviewer agreement and review time before fitting. Use the remaining development budget to target persistent failures; expand toward 150–200 lead cases only if evidence supports the additional work.

1. Freeze a versioned dataset snapshot of valid completed reviews, explicit exceptions, data roles and source/reviewer history. Never train after each click.
2. First evaluate updating reliability/traceability while freezing positions. Keep anatomical absence separate from image traceability. Balance affirmative and negative evidence by boundary, case and animal.
3. Fine-tune positions using reliable approved final coordinates, including unchanged automatic curves and corrected/moved/joined coordinates that were explicitly confirmed. Preserve origin for manual-origin versus all-approved sensitivity analyses; the primary new-contract training pool need not exclude valid unchanged approvals.
4. Treat unreliable candidates and independent-reader disagreement as ambiguity evidence. Do not train guesses as exact reliable targets or average incompatible anatomical interpretations blindly. A small shared set does not establish calibrated uncertainty.
5. Compare against the frozen starting model and frozen-position alternative. Retain readable controls and examine boundary-specific regression. Do not reuse generated predictions as new independent human truth.
6. Export immutable model rounds through the common provider interface. New predictions can serve new cases; confirmed reviews and shared assignments retain their original sources. Explicit adoption preserves history and requires reconfirmation where the result changes.

## Success criteria

Measure results by boundary and available CNV interior/margin, ONH, readable and obscured contexts:

- Position error in micrometers, especially upper-tail error and lengths of large-error runs.
- False reliable reporting in human-marked ambiguous/untraceable regions.
- Retention of defensible reliable boundaries; withholding everything is not success.
- Reviewer correction effort and completion time, plus candidate usefulness.
- Independent reviewer differences in position and state judgments.
- Saved-review usability: reliable resumption, no accidental duplicate records, correct persistent yellow lines, and intact review history across provider updates.

Report missing context and unreliable layers explicitly. Improved GUI behavior, approval coverage or reader agreement alone does not establish a validated measurement model.
