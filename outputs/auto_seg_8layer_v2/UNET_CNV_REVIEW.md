# CNV-aware segmentation: review and revised direction

Review performed 2026-09-07 (local date). This is a review and proposed next plan, not a trained-model result. The original UNET_PLAN.md, code, human labels and segmentations are preserved.

## Recommendation

Keep a small U-Net as the leading learned model, but change the project from “predict eight lines everywhere” to “predict each boundary where measurable, identify local failures, and route a limited correction queue.” Compare a single-B-scan boundary U-Net with a three-B-scan-context (2.5-D) version before selecting the production model. A U-Net can itself produce the learned boundary costs; these are compatible approaches, not competing categories.

The largest immediate bottlenecks are lesion-core training coverage, local annotation validity, and evaluation that detects localized errors. There is no current experiment establishing that U-Net, nnU-Net, a transformer, or the classical cascade is best for these tree shrew CNVs. A larger model is not a substitute for those missing measurements.

The feasible operational target is automatic processing of every supported processed volume, with reliable measurements where the image supports them, explicit unavailable results elsewhere, and review of a measured fraction of cases. Neither a human nor a model can validate a boundary that is absent from the recorded image. Manual en-face CNV footprints can remain an accepted input to lesion analysis; this makes that workflow mask-assisted. A structural-OCT-only mode should remain available for volumes without a footprint. Unreviewed/missing masks must never mean “no CNV.”

## What is actually on disk

Read README.md, PIPELINE.md, the segmentation skill, the eight-surface contract and GUI/label code, the v2 report and U-Net plan, all major Phase 1 modules, and the CNV footprint/review workflow. Inspected a low-quality v2 example image. The root README/PIPELINE and parts of the skill describe an older ten-surface workflow; the active eight-boundary definitions are in code/eight_surface/config.py. Their historical recommendations must not silently replace the newer contract.

Read-only census of the standard folders:

| Item | Current finding |
|---|---|
| Eight-boundary decisions | 102: 76 corrected, 26 rejected, no accepted |
| Corrected coverage | 21 volumes, six animals: TS165, TS169, TS241, TS247, TS250, TS267 |
| Reviewed en-face CNV labels | 28 volumes across 11 animals; 19 nonempty CNV masks, nine empty masks |
| ONH-edge traces | Present in 11 of those 28 files; open edge traces, not exclusion-area masks |
| Cached U-Net training images | 53; 23 currently corrected B-scans have no cached image |
| Model/training | No model or training implementation in the U-Net package; torch absent from the activated octa environment |
| Blind repeatability | Ten packs present; no files in the expected repeatability/labels directory |
| CNV-targeted packs | Standard outputs/eight_surface/cnv_review directory absent |

The approximately 160 images in the existing review design are **B-scans**, each containing 512 A-lines. This review interprets the user's “~160 A scans” as that B-scan queue.

Four of the 32 standard review volumes have no saved CNV label in outputs/cnv_labels: TS247_OS_2024-11-26_D42_s04_121636; TS267_OS_2025-03-19_D28_s03_103903; TS267_OS_2025-04-02_D42_s02_104209; TS283_OD_2025-01-22_D0_s02_111740. This is a file reconciliation item, not evidence that the user's intended CNV review was incomplete. Some may be intentionally omitted or saved elsewhere.

Using the current cnv_review.lesion_zones defaults (75 µm rim, 250 µm nearby extent, adaptive inner rim), intersected with non-excluded columns in corrected B-scans whose volume has a saved footprint:

| Zone | Non-excluded A-line positions | B-scans containing any | Animals represented |
|---|---:|---:|---:|
| Remote | 20,800 | 67 | 6 |
| Nearby | 4,843 | 24 | 3 |
| Rim | 842 | 13 | 3 |
| Core | **15** | **1** | **1 (TS267)** |

These are geometrical annotation-coverage counts, before per-surface validity, not independent training examples or accuracy estimates. A B-scan can contribute to several zones. Footprint definitions and local exclusions affect the counts. Nonetheless, the present corrected set provides almost no core evidence under the project's own zone definition.

## What the old plan gets right

- Replacing shared hand-designed edge filters with boundary-specific learned evidence addresses an observed limitation. The v2 report still has RNFL_GCL/GCL_IPL median errors around 9–10 µm and p90 around 27–28 µm on its original labeled cohort. Those p90 figures are percentiles of B-scan medians, not column-level p90.
- Animal-grouped evaluation, independent human labels, masked losses, orientation checks, invertible coordinate transforms, and explicit abstention are all worth retaining.
- Removing healthy relative-depth windows from the learned decoder is reasonable to test. Keeping those windows unchanged, as the older skill suggests, can exclude the human CNV answer regardless of how good the learned evidence becomes.
- Retesting slow-axis refinement is appropriate. Preserve historical settings for baseline comparisons; do not increase smoothing to make lesion surfaces look cleaner.

## Changes needed before training

### 1. Record local visibility and actual human supervision

The current label format has edited/visible/reliable flags of shape [8], but exclusions of shape [512]. targets.py therefore treats a surface marked edited as supervised throughout every non-excluded column. The GUI supports local strokes with tapered joins and ordering displacement, yet saves no per-column stroke provenance. An edited surface flag cannot prove every column was drawn, inspected, or left unchanged intentionally. Conversely, lack of numerical displacement does not prove a human did not review a correct line.

For the next CNV round, add backward-compatible per-surface, per-column reviewed/drawn/visible/reliable/displaced provenance, preferably with an explicit unknown state and distinction between directly drawn stroke support and automatic taper. Preserve whole-image exclusions separately. Do not retrofit precise masks from surface-minus-auto differences; those differences cannot recover human intent. Legacy records remain usable only under a documented conservative policy, with an audited subset to assess the limitation. Never hand-write or migrate human evidence through a training script.

This is especially valuable at a lesion: the outer retina may be unmeasurable in its center while remaining visible beside it, and inner surfaces may remain measurable in the same columns. The current choice between excluding all surfaces locally or disabling one surface across an entire B-scan loses that distinction.

### 2. Define the outer boundaries through CNV

The current eight-boundary contract calls PR_RPE the former RPE-complex peak, and RPE the outer RPE edge (former BM endpoint). These names do not establish that either line is anatomical Bruch's membrane under disrupted/elevated RPE. The PHOTORECEPTOR band combines ONL and other outer-retinal structures; it is not an isolated photoreceptor-cell measurement.

Keep these definitions explicit. Create an illustrated annotation decision sheet for intact, elevated, disrupted, shadowed and cropped outer retina. Where a boundary cannot be identified, label it unavailable, not a smooth continuation. Do not turn peak-to-outer-edge spacing into anatomical RPE thickness or CNV volume without a validated endpoint convention. A new BM or 3-D lesion target would require separate justified annotation; en-face masks do not supply axial lesion extent.

Maintain non-crossing order where boundaries exist, but do not require a positive healthy layer thickness or a surface in every column. A forced one-pixel gap is still fabricated tissue if a layer has disappeared. Missing predictions must not push remaining visible boundaries through cumulative ordering corrections. Measure decoder displacement and slope limits at lesion rims, rather than inheriting the classical max_step=2 blindly.

### 3. Repair the evaluation before optimizing it

evaluate.py computes a median absolute error over each B-scan, then a median/p90 over those medians. Its gross_miss_frac is the fraction of B-scans whose median exceeds 25 µm. In a read-only synthetic probe, adding a 100 µm error to all eight surfaces in 51 of 512 columns returned median=0, p90=0 and gross_miss_frac=0. A localized CNV failure can therefore disappear from all three summaries.

Retain historical summaries for comparison, but add per-column errors within core, inner rim, outer rim, adjacent and remote zones; per-lesion summaries; localized gross-error extent; thickness bias/error; per-animal summaries; and risk versus retained coverage. Report errors before abstention and on retained predictions with explicit denominators. Missing predictions on visible ground truth must count as abstentions/failures, not vanish or propagate through np.median as unexplained NaNs. Assess inappropriate confident predictions where reviewers say the boundary is not measurable.

The current control/CNV stratum derives from the nominal day label, treating all post-laser scans as CNV and D0 as control. Replace it with independent reviewed lesion status and documented acquisition timing, allowing unknown. A remote selection-role flag is not proof of a biological control. An en-face core denotes the footprint interior, not guaranteed axial destruction or active neovascular tissue.

### 4. Treat uncertainty as a measured predictor of error

A depth softmax always distributes probability somewhere. Its entropy is not automatically calibrated, and removing a scalar prior does not remove the network's learned anatomical expectations. A confident prediction can still be unsupported. Synthetic shadows paired with unchanged boundary targets teach reconstruction through occlusion, not abstention.

Add a local measurability output with explicit human-supported targets. Mask boundary/region losses for genuinely unobservable or synthetically fully occluded targets while training the appropriate visibility/quality behavior; model realistic partial shadows separately. Use rejected images for rejection evaluation, and for quality supervision only when the reason is known. Do not turn a global rejection into invented per-surface negative labels.

Evaluate entropy, a small independently trained ensemble's disagreement, and acquisition/visibility signals. Calibrate on development animals only against specified error events, then measure false confident errors and review yield on untouched animals. Temperature scaling alone is not a guarantee of boundary-error or distribution-shift calibration. Preserve independent acquisition QC; its scores and local_confidence are not interchangeable with model confidence.

### 5. Simplify and test the input geometry

dataset.py stacks a flattened crop and a separately cropped unflattened image as two channels. Identical tensor indices correspond to different anatomical positions. A network might learn to use this, but it is not a spatially aligned rescue channel and should not be assumed robust.

Start with a single canonical B-scan and conservative full-retina coverage. Compare with B-scan neighbors at b-1, b, b+1 as separate channels predicting the center slice. Keep their native correspondence explicit; assess motion and any registration rather than assuming perfect alignment. Test neighbor dropout/fallback. This preserves the center slice and lets the model learn whether neighboring evidence helps. Compare N=1 and N=3 averaging empirically; historical jitter changes alone do not establish boundary accuracy.

If flattening helps, apply a common, validated coordinate system to spatial channels and preserve an invertible mapping. Measure crop containment and lesion shape in original coordinates. The current lossless test validates circular shift/inverse, not the lossy crop. build_sample can zero out off-crop boundary weights and still succeed when some supervision survives, despite stronger documentation. A corrupted crop needs a wider/native fallback and a logged failure, not quiet removal of difficult examples. Cache identity must include preprocessing parameters and source/label geometry; existing cache reuse checks existence without verifying a requested new averaging setting.

### 6. Freeze evaluation snapshots, not the pool of future labels

The Phase 1 test suite currently passes 23/24 checks. The failing baseline-reproduction test compares today's larger labeled cohort to a fixed report from the original 53 corrected B-scans. This is a cohort mismatch, not proof of a numerical regression. The real-cache test checks 53 samples and silently skips newly labeled records without a cache.

Version the original regression-test cohort, current data manifests and animal splits. Allow new dataset versions, but do not silently regenerate a test split midway through model selection. Reserve animal-level validation for early stopping/calibration separately from final evaluation. Eleven animals produce 55 leave-two-out folds; exhaustive pairs are expensive and heavily overlapping, not 55 independent experiments. Prefer a frozen animal-grouped development design with a locked final test if coverage permits, or nested grouped evaluation if holding animals aside makes lesion coverage untenable. Report the limited animal count and cluster uncertainty at animal level.

The report's assertion that an outer-anchor rule has “no fitted parameter” does not make it independent: choosing its brackets and crop margins from human examples is data-dependent development too. Use the historical v2 output as a fixed practical comparator, and document its overlap with development labels when interpreting generalization.

## A practical sequence

1. Finish the broad review queue. Before starting the expensive within/edge/adjacent round, implement local annotation validity, audit the outer-boundary convention, and reconcile current files.
2. Freeze an initial dataset and development/evaluation animal partition. Build a modest first CNV round, for example 40–60 additional B-scans if coverage permits, distributed across lesion-bearing animals, lesion components, image quality, and timepoints. This is a workload proposal, not a sample-size guarantee. Prioritize underrepresented animals and cores; retain negative/remote examples. Adapt the count after measuring coverage and time. Existing cnv_review.py is reusable but currently selects globally across a mask: ensure small lesions are represented component by component, deduplicate existing labels, and preserve narrow-lesion/no-core cases explicitly.
3. Complete blind repeats with core/rim and low-quality cases included; where feasible obtain a small second-reader subset. Use repeatability to set justified surface-specific tolerances, not assumed pixel accuracy.
4. Repair targets, cache provenance and the evaluation harness. Run a reproducible single-B-scan small boundary U-Net pilot with optional valid-region auxiliary loss and a local measurability head. Build dense region supervision only from genuinely valid adjacent endpoints; a footprint is not a 3-D lesion class. Preserve thin-layer axial resolution.
5. Compare the same model with separate neighboring B-scans. Compare direct boundary prediction with a modest non-crossing decoder on the same held-out examples. Keep the classical v2 method as a comparator. An inexpensive shallow learned-cost comparator is useful if it adds little work; an extended round of scalar-prior tuning is not the main next investment.
6. If uncertainty and error analysis justify it, add a small ensemble and an optional footprint/distance channel, explicitly marking mask availability. Evaluate mask-assisted and image-only modes separately, including empty reviewed masks, unavailable masks, and modest footprint perturbations. Do not require a separate normal/CNV specialist initially.
7. Integrate targeted human correction immediately. Rank review units using validated error risk, diverse lesion/animal coverage and a random audit sample of apparently confident outputs. Evaluate at 10% and 20% reviewed CNV volumes, and also report reviewed B-scans, edited columns and active minutes. Do not claim a 10–20% burden solely because that many columns were flagged. If the risk target cannot be met at that budget, report the gap and acquire targeted evidence.
8. Only promote after lesion-stratified results and review burden support it. Then run resumably over all eligible indexed processed volumes, write versioned surfaces/validity/NaN thicknesses/provenance and review queues, and provide the same CLI for future scans. Monitor acquisition shifts and validate each subsequent model version on newly acquired animals/sessions. Automatic processing coverage and reliable measurement coverage are separate deliverables.

At 160 B-scans, millions of target pixels are strongly correlated and sometimes derived from partial lines. The old plan's projected 1–2 px outer-boundary accuracy, 3–5x improvement and 150–300-label sufficiency are hypotheses, not established expectations. Use learning curves and lesion coverage to determine the annotation budget.

## Why this model family, and alternatives

Structured surface regression with a shared U-Net feature extractor, a layer/lesion branch and a boundary-distribution branch has primary OCT precedent. That supports testing this design, but those human OCT cohorts do not establish performance in tree shrew vis-OCT CNV. [He et al., structured retinal surface segmentation](https://pmc.ncbi.nlm.nih.gov/articles/PMC7855873/).

nnU-Net is a useful reproducible segmentation baseline; it supports ignored labels, so sparse annotation alone is not a reason to dismiss it. A custom boundary/visibility model nevertheless matches this project's partial surface supervision and thickness outputs more directly. Add nnU-Net if enough correctly masked region labels exist and it answers an unresolved model-selection question. A full 3-D model adds data and memory demands before the value of adjacent-slice context is known. [Official nnU-Net documentation](https://github.com/MIC-DKFZ/nnUNet), [ignore-label support](https://github.com/MIC-DKFZ/nnUNet/blob/master/documentation/ignore_label.md).

Neural-network probabilities require empirical calibration; softmax is not sufficient. [Guo et al., On Calibration of Modern Neural Networks](https://proceedings.mlr.press/v70/guo17a.html). Pathological photoreceptor segmentation research has also investigated Bayesian U-Net uncertainty for identifying difficult regions; it motivates testing uncertainty-based review, without guaranteeing the proposed correction budget. [Orlando et al., U2-Net](https://arxiv.org/abs/1901.07929).

All architecture choices, zone widths, pilot sizes and review thresholds above are recommendations to test, not new validated quality claims.
