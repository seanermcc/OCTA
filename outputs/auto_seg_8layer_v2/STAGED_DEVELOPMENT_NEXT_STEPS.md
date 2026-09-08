# Staged segmentation development: next steps

Updated 2026-09-08. This document supersedes the sequencing in UNET_CNV_EXECUTION_PROMPT.md: develop the control/non-CNV model now; the CNV-specific GUI update and specialist are a later stage. The historical UNET_PLAN.md and earlier critique remain useful technical background, not an instruction to postpone Stage A.

## Verified starting point

A read-only audit of the annotations found all 160 unique B-scans in the standard review queue have decisions, across 32 volumes and 11 animals. There are 101 corrected and 59 rejected decisions, no missing decisions, no labels outside that queue, and no unreadable files. Counts are saved in STAGED_DEVELOPMENT_CENSUS_20260908.json.

Corrected B-scans by animal: TS165 3; TS169 3; TS241 7; TS247 26; TS250 4; TS267 37; TS283 7; TS305 3; TS325 11. TS328 and TS336 have only rejected decisions in this queue. Thus there are nine animals with some corrected evidence, not eleven training animals. These counts precede surface validity and control/non-CNV eligibility checks. TS247 and TS267 together contribute 63 of 101 corrected B-scans, so pooled metrics and uniform image sampling can be dominated by them.

There are 28 reviewed en-face masks, 19 positive and nine empty. Missing footprint files are unknown, not negative. There are 53 cached training images; 48 corrected B-scans lack a cache. The U-Net folder contains preparation/evaluation modules but no model/trainer. Torch is absent from the activated octa environment. No repeatability labels exist in the expected repeatability/labels folder; the general review queue is complete, but that separate measurement is not established here.

## Stage A: dependable control/non-CNV layer segmentation

Goal: train, evaluate and package one small eight-boundary model for controls and suitable non-CNV tissue across supported acquisition-quality conditions. Do not wait for a CNV-specific local-visibility GUI update. Do not promise that absent image evidence can be recovered. All eight current boundaries and all seven directly derived bands plus TOTAL remain in the output, with unreliable measurements explicit.

### 1. Establish the eligible supervision

- Join surface annotations, source review packs, scan metadata, independent acquisition QC and reviewed en-face footprints in native coordinates. Separate WT, confirmed pre-laser, reviewed footprint-negative post-laser, remote tissue in positive volumes, lesion/near-lesion tissue, and unknown status. A post-laser negative footprint is not automatically a healthy control; D0 is not automatically pre-laser; the pack's is_control selection flag is not biological control status.
- Make Stage A's supervised columns exclude CNV and a documented physical buffer. Existing nearby-zone extent (250 micrometers) is a starting candidate for remote eligibility, not validated absence of CNV effects. Preserve signed distance and record the chosen threshold; examine sensitivity using development data only. Do not equate outside-footprint tissue with histologically normal tissue. Images may retain lesion context, but it supplies no Stage A boundary supervision inside excluded zones.
- Use corrected, edited, visible, reliable surface evidence outside image exclusions. Displaced-only and untouched automatic lines are not ground truth. Current legacy flags are surface-wide, so local drawing provenance is unknown. Preserve that uncertainty; do not invent stroke masks from numerical differences. Audit existing examples/source information and document the supported legacy eligibility policy. If ordering displacement compromises a surface's final human evidence, exclude or flag it conservatively. Request only a small targeted audit if the evidence is insufficient, not a blanket relabeling exercise.
- Regions require two valid bounding endpoints. Rejected images have no boundary targets; retain them for rejection/coverage evaluation. Do not assume every rejected image proves every boundary invisible. ONH-edge traces are open traces, not retinal exclusion-area masks.

Deliverable: a versioned manifest showing eligible volumes, B-scans and columns per surface, animal, biological group and QC stratum, with exclusion reasons and label/source fingerprints.

### 2. Repair evaluation and lock animal groups

Replace headline dependence on B-scan medians with column-level boundary error (median and tail), signed thickness bias, thickness absolute error, large-error fraction and contiguous failure extent. Keep historical summaries for compatibility. Include per-animal and QC breakdowns and explicit coverage. A synthetic 100 micrometer miss in about 10% of columns must be detected. Missing predictions on eligible ground truth count as failures/abstentions with denominators, rather than disappearing. Report both raw and retained-prediction error so withholding difficult columns cannot manufacture success.

Version the historical 53-label benchmark separately from the completed cohort; an expanded cohort need not reproduce the old numerical summary. Make cache coverage failures explicit rather than skipping absent cases. Snapshot label revisions/hashes so later annotations do not silently alter a benchmark.

Choose splits only after the eligible-data audit. Keep both eyes, all dates, repeats and neighboring images from one animal together. Use animal-grouped development validation for tuning/early stopping/calibration and a locked final test where adequate coverage allows. Otherwise use nested grouped evaluation and disclose limited independent animal support. Do not automatically run 55 overlapping leave-two-out folds or silently reshuffle splits when labels arrive. Balance reporting and sampling across animals. With one WT animal, distinguish WT coverage from demonstrated generalization to new WT animals. Rejected-only animals support failure handling, not accurate-boundary evaluation.

### 3. Train a restrained first candidate

Implement a small 2-D boundary U-Net using masked boundary-distribution losses, with an optional valid-region auxiliary loss. Keep the current eight-boundary definitions in eight_surface/config.py: PR_RPE is the existing peak convention; RPE is the current outer endpoint. Do not silently reinterpret them as anatomical BM or restore retired surfaces.

Use canonical structural B-scans with adequate retinal coverage and a tested source-coordinate inverse. Start with N=1; compare N=3 only as a bounded development experiment. Match preprocessing between training and inference. The old flattened/unflattened two-channel input is not spatially aligned: do not inherit it as an assumed rescue mechanism. Validate crop containment and provide a wider/native fallback. Version cache keys by geometry, source and preprocessing; retain old caches as historical artifacts.

Train on suitable lower-quality tissue as well as clear images. Keep augmentations realistic, preserve thin axial layers, and do not supervise invented boundaries under complete synthetic occlusion. A local measurability head is optional only if suitable explicit targets exist; unknown legacy visibility is not a negative class. No CNV-GUI dependency is introduced.

Use direct boundary estimates and, if needed, modest learned-cost non-crossing decoding. Evaluate ordering displacement and avoid healthy-thickness priors as truth. Preserve classical settings for the v2 comparator rather than retuning the old cascade. Compare a 2.5-D variant only if the 2-D pilot's failure analysis indicates adjacent-slice information is a worthwhile next experiment. Do not make an architecture sweep a prerequisite for the first result.

### 4. Validate, package and establish the first release

Compare with stored historical predictions and the v2 baseline on identical eligible labels. Document any baseline-development overlap. Assess every boundary and derived layer, different qualities and animals, not merely a pooled improvement. Define practical surface-specific accuracy/bias/coverage requirements before final testing. If repeatability is unavailable, use explicitly provisional development criteria; do not claim human-level accuracy. Prepare a small blind-repeat queue if needed without blocking independent implementation or pilot training.

Calibrate error/review thresholds on development animals, never final-test animals. Entropy is only a candidate error signal. Report measurement coverage, gross failures, acquisition rejection, runtime and review effort. Do not claim a correction-time budget without timed human review. The future 10–20% CNV review target is not a measured Stage A result.

Package reproducible training/evaluation/inference commands, model/configuration versions, source-coordinate surfaces, reason-coded validity and NaN-masked thicknesses. Smoke-test full-volume inference and provide resumable batch operation. Promote to a validated Stage A release only if results justify it; otherwise keep a clearly marked experimental candidate and a focused next action.

Apply Stage A to validated eligible controls/non-CNV regions. A reviewed positive footprint and buffer must be excluded from validated Stage A measurement export even if provisional predictions are computed there. Missing footprints must remain unknown unless independent metadata establish eligibility. Save scope/region metadata with every output. Processed-scan counts should be refreshed from the index, not assumed from old README text.

## Stage B: CNV and difficult-region capability

After Stage A is established, add local annotation visibility/provenance for CNV review and gather representative core/edge/adjacent labels. Develop a specialist initialized from a copy of Stage A, preserving the validated first model. Give the specialist original OCT/context and optional footprints; it must be able to replace a wrong prediction, not merely adjust it inside a narrow window. Evaluate local per-surface replacement, joining artifacts and consistent boundary definitions. Low-quality non-CNV failures also need review or specialist handling.

Compare a two-model system with a single mixed-training candidate when CNV evidence permits. A permanent two-model architecture is not pre-decided. Evaluate the combined error, coverage and human workload, including the proposed 10–20% of CNV volumes reviewed. Production should preserve Stage A performance while adding CNV capability. Future-scan support requires geometry checks and acquisition-shift QC, not an unconditional accuracy guarantee.

## Immediate next action

Execute CONTROL_NONCNV_EXECUTION_PROMPT.md. The next task should implement Stage A through an actual pilot, evaluation and inference packaging, continuing independently while any small human-audit questions are pending. This document records the plan; no training was performed to create it.
