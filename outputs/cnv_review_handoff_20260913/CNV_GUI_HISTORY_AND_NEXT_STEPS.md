# CNV GUI development, review-batch handoff, and proposed automation plan

**Project:** tree shrew OCT/OCT-A CNV analysis  
**Prepared:** September 13, 2026  
**Current reviewer:** octa-auto_cnv_v5  
**Scope:** work completed in this conversation, the saved review inventory, and the next development steps. This report does not change annotations or train a model.

## 1. Where we are now

The workflow evolved from an automatic thinning/candidate viewer into a dedicated CNV annotation interface. V5 now supports adding, correcting, confirming, removing, and marking uncertain lesion footprints, with real OCTA and retinal thickness available for inspection. Its B-scan is read-only and shows only the boundaries of the selected thickness layer.

The reviewer reports having finished the batch. A read-only inventory of the saved files finds **15 v5 review files for the 17 selected TS267 acquisitions**, of which **11 record a completed whole-field review**. Four saved scans remain marked `in_progress`; two acquisitions have no v5 review file. This is a saved-record distinction, not a claim that those images were never examined. Those gaps should be reconciled in the GUI before the batch is described as fully complete or its unmarked regions are used as negative training labels.

The saved files contain **25 kept CNV region entries, 7 Unsure entries, 19 rejected entries, and 1 draft entry**. These are recorded annotation decisions, not independently adjudicated biological lesion counts or detector accuracy measurements. The current CNV suggestions still come from the v3 heuristic detector. **No CNV U-Net has been implemented or trained.**

The machine-readable evidence for this section is [REVIEW_BATCH_INVENTORY.json](G:/OCT_TreeShrew/octa/outputs/cnv_review_handoff_20260913/REVIEW_BATCH_INVENTORY.json). It includes an exact audit timestamp, scan and region records, and SHA-256 hashes of every inspected v5 review file.

## 2. What changed across the versions

| Version | Problem addressed and resulting behavior | Recorded delivery evidence |
|---|---|---|
| **v1 — starting baseline** | Automatic CNV/thinning maps, fitted unaffected-retina reference, percentage-deficit contours, linked B-scans, and a separate proposal-editing workflow. Detection relied strongly on thinning/background support and missed important manual locations. | 17 TS267 acquisitions; 13 candidates; 0/7 legacy D7/D28 manual components matched within the reported 75 µm tolerance. |
| **v2 — integrated automatic and manual review** | Combined proposal assessment, footprint editing, diagnostic maps, and boundary review in one interface. Candidate generation became independent of background availability. Clustered structural disruption and invalid neural geometry could expose a lesion even when thickness could not be measured. | 220 candidates; 7/7 legacy locations matched; 16 tests and 17 actual GUI scan opens passed. Eight default background fits were insufficient. The very broad candidate coverage made the apparent location improvement an inadequate measure of usefulness. |
| **v3 — reduce implausible CNV proposals** | After the user reported excessive false-looking detections, added compact/round-or-oval shape requirements, vessel-trunk avoidance, structural support, conservative fragment grouping, and an expected-count sanity check. Diffuse, elongated, clipped, and weak candidates moved out of the main proposal list into retained diagnostic evidence. Added navigation to saved manual outlines and a manual-first launcher. | 29 proposals across 17 scans, with 0–4 per scan; no scan actually needed the four-proposal cap. 6/7 legacy manual locations matched. The lower D7 legacy location remained missed. Fourteen tests and 17 GUI opens passed. |
| **v4 — filled painting and useful layer maps** | Closed paint loops now filled their interiors. Replaced the structural-evidence panel with selectable RNFL/GCL/IPL/etc. thickness; kept full retinal thickness on the right. Preserved the manual workflow in a new folder and read previous reviews without overwriting them. | 20 tests and 17 scan checks passed. The GUI still inherited too many boundary-editing and diagnostic controls. |
| **v5 — dedicated CNV reviewer** | Rebuilt the interface around two top image panels, a small CNV list, and one read-only B-scan. The second image switches between actual OCTA and layer thickness. Removed boundary editing, core/footprint switching, and the extra diagnostic/thinning panels. Added explicit whole-scan completion metadata for future supervised learning. | 16 behavioral tests passed; real OCTA and all 8 thickness choices were checked on all 17 scans. B-scan boundary pairs matched the thickness endpoints; opening, switching views, and navigation left existing review files unchanged. |

These figures describe successive development releases, not an independent comparison on a fixed, newly adjudicated test set. In particular, **220 → 29 proposals is a reduction in review burden, not a measured precision improvement**. The old manual-location comparisons used sparse legacy components and a distance tolerance; they do not establish boundary accuracy. The new batch needs its own reference audit and a fresh, explicitly defined comparison.

Historical sources: [v1 guide](G:/OCT_TreeShrew/octa/outputs/octa-auto_cnv_v1/START_HERE.md), [v2 delivery report](G:/OCT_TreeShrew/octa/outputs/octa-auto_cnv_v2/DELIVERY.md), [v3 guide](G:/OCT_TreeShrew/octa/outputs/octa-auto_cnv_v3/START_HERE.md), [v4 guide](G:/OCT_TreeShrew/octa/outputs/octa-auto_cnv_v4/START_HERE.md), and [v5 guide](G:/OCT_TreeShrew/octa/outputs/octa-auto_cnv_v5/START_HERE.md).

## 3. Scientific distinctions established during development

### Detect a possible lesion before asking whether thinning is measurable

The initial v2 request identified a concrete failure in **TS267 OD D14, B-scan 230 / A-line 85**. The automatic boundaries had invalid geometry and the thickness was unavailable. Background support was also absent, which had prevented the earlier proposal workflow from surfacing that location appropriately.

V2 exposed the local crossing/geometry evidence without inventing thickness or a human annotation. V3 retained that focus while tightening the proposal rules. Local segmentation failure can be evidence worth inspecting, but is not sufficient by itself to establish a CNV; vessels, acquisition artifacts, low signal, and ordinary segmentation errors must still be distinguished.

### Core, anatomical footprint, and thinning extent are different objects

- **Candidate core:** the automatic detector's central proposed focus. This is an algorithmic editing seed, not a biological boundary.
- **Manual CNV footprint:** the full region the reviewer judges to belong to the lesion, including confidently identified edges. This is the intended target for the future CNV segmentation model.
- **Thinning footprint/percentage contours:** descriptive measurements of supported thickness change relative to an estimated unaffected reference. They are not automatically the lesion's anatomical border.

The earlier quantitative workflow preserved full retinal thickness as **ILM to outer RPE edge × 1.12 µm/pixel**, and signed deficit as **100 × (reference − measured thickness) / reference**. Missing values stayed missing. Background fitting, extrapolation, and sensitivity variants did not turn absent tissue measurements into observed thickness. These distinctions remain relevant to downstream CNV quantification even though v5 deliberately removes the quantitative-diagnostic controls from the annotation interface.

### Shape and number expectations guide proposals, not human truth

The user specified that the target lesions are generally round, lie between vessels, usually number 1–2, and occasionally 3–4. V3 incorporated those expectations to reduce implausible automatic detections. Human reviewers were instructed to follow the image rather than force a perfect circle or a preset count. A count check must not silently erase a genuinely reviewed lesion. Future model evaluation should retain all predictions before postprocessing so count limits cannot conceal false positives or misses.

### The structural-evidence map was not a CNV probability map

The removed map highlighted strong local brightness departures, in either direction, from the structural en-face image. Vessels, shadows, and artifacts could also appear bright. It was neither blood flow nor thickness nor a calibrated probability of CNV. The user found it unhelpful for annotation; v4 replaced it with layer thickness, and v5 simplified the layout further.

## 4. Segmentation, OCTA, coordinates, and provenance

**Underlying layer segmentation.** The GUI versions reused saved **octa-seg_v1 ALL_LABELLED** outputs from the **longitudinal_assessment/v2/round_000** exports. Creating a new CNV GUI version did not train a newer layer model. The recorded position checkpoint is under [octa-seg_v1/models/ALL_LABELLED](G:/OCT_TreeShrew/octa/outputs/octa-seg/octa-seg_v1/models/ALL_LABELLED). The D14 export's [neural_complete.json](G:/OCT_TreeShrew/octa/outputs/longitudinal_assessment/v2/round_000/volumes/TS267_OD_2025-03-05_D14_s01_104048/neural_complete.json) records its model paths and hashes.

**Why v4 could look worse than remembered.** Its automatic B-scan overlay drew the raw neural position branch, whereas the thickness maps went through the established thickness engine's filtering and saved-correction handling. That was a display/measurement mismatch; it was not evidence that a newly trained model had become worse. V5 uses the same filtered endpoint arrays for the thickness calculation and its displayed boundary pair. No boundary editor is embedded in v5.

**Layer definitions.** Available thickness choices are Full retina, RNFL, GCL, IPL, INL, OPL, Photoreceptor composite, and RPE band. GCL spans RNFL/GCL to GCL/IPL; IPL spans GCL/IPL to IPL/INL. Photoreceptor composite includes ONL and other photoreceptor structure. This eight-boundary export does not provide isolated ONL, ELM, or inner/outer-segment thickness maps. In thickness mode only the selected layer's two endpoints are shown. In OCTA mode there are no layer-boundary overlays.

**Experimental status.** The existing octa-thick engine's available-position policy and saved human corrections remain part of the displayed thickness. This is not a validated confidence guarantee. Shadowed, withheld, and invalid measurements remain unavailable; displayed lines also break where the selected thickness is unavailable. Color scales are per-layer/per-scan percentile ranges, so the numerical values—not color similarity across layers—are the meaningful comparison.

**Actual OCTA in v5.** V5 reads `frame_OCTAAvg` from the processed MATLAB/HDF5 files and caches a mean log-intensity projection over the saved retinal depth crop. It verifies native grid agreement and re-detects orientation from the structural depth profile. This is an actual OCTA-channel projection, not a fabricated thickness-derived image. It is a saved-crop projection, **not a layer-specific OCTA slab**. Adding this display did not make the unchanged v3 CNV detector start using OCTA.

**Data contract.** En-face masks use native **[B-scan, A-line]** coordinates on the selected 512 × 512 acquisitions. The source is `*_processedVolumes.mat`; no spectral reconstruction from `.RAW` was performed. Canonical B-scans have vitreous at depth zero. Axial scale is 1.12 µm/pixel; the approximately 1460 µm lateral field is distinct from the filename's `X500um` galvo-drive label. Same-day repeats were not silently registered or given transferred CNV labels. No longitudinal lesion-change claim has been established.

## 5. The final annotation workflow agreed with the reviewer

### What to label

Label the **whole confidently identified CNV footprint**, including its supported edge, rather than only its central core. Inspect structural OCT, OCTA, and the relevant B-scans together. Surrounding thinning or a thickness-map color change does not automatically belong inside the lesion.

For an ambiguous border, keep the confidently identified lesion and mark the doubtful portion as a separate **Unsure** region. Avoid covering a confidently labeled center with an uncertainty mask. If the identity of the entire feature is uncertain, mark that whole feature Unsure. The intended future training behavior is to ignore unsure pixels, not to teach them as healthy background. That target-export behavior remains a future implementation step.

### How separate regions work

**Add CNV → paint → Keep CNV → Add CNV again for the next lesion.** Painting continues to modify the currently selected entry, even after Keep CNV; Save does not start a new region. This explained the user's experience of two painted marks becoming a single CNV entry.

Each distinct confirmed CNV should have its own entry for instance counting. Multiple disconnected patches may share one **Unsure** entry if they all have the same uncertainty judgment: the entire entry's mask is uncertain. The sidebar entry count and the number of connected image patches are therefore not interchangeable.

When a saved manual outline and an automatic suggestion both describe the same lesion, use the outline best supported by the images, edit clear errors, Keep the final CNV, and Remove the duplicate. Start from the manual judgment rather than averaging two outlines or changing it merely to match the algorithm. A removed region remains in the saved record/history; Remove is not deletion of the original source annotation.

### Save, Next, and Finish scan

| Action | Meaning |
|---|---|
| **Keep CNV** | Explicitly confirms the selected footprint as a CNV. |
| **Unsure** | Records reviewed uncertainty; it is not a positive CNV or a confirmed negative. |
| **Save** | Saves current partial edits and decisions. It does not assert whole-field review. |
| **Next** | Saves edits and opens the next acquisition; it does not mark the current one finished. |
| **Finish scan** | After confirmation, records that the entire image was checked, all identifiable CNVs were added, and unreadable/ambiguous areas were marked Unsure. It stays on the same scan. |

A completed scan's unmarked areas can support future reviewed-background targets, subject to the uncertainty and label audit. Unmarked areas in a partial review remain unknown. Any subsequent edit invalidates the prior completion flag until the scan is finished again. The expected sequence is **review → Finish scan → Next**.

## 6. Where the manual work lives

The original masks remain in [outputs/cnv_labels](G:/OCT_TreeShrew/octa/outputs/cnv_labels). The original TS267 inventory contained six files: five with footprints and one explicit reviewed absence. D7 OD and D28 OD matched the selected pilot acquisitions. The two D56 OD files, D49 OS file, and D98 OS reviewed absence belonged to different repeats and were not transferred to the selected scans. The [original manual inventory](G:/OCT_TreeShrew/octa/outputs/octa-auto_cnv_v3/MANUAL_ANNOTATIONS.md) lists their exact paths.

V5's new work is in [outputs/octa-auto_cnv_v5/review/regions](G:/OCT_TreeShrew/octa/outputs/octa-auto_cnv_v5/review/regions), with revision history below that directory. When no v5 record exists, the GUI can start from a saved v4 record, falling back to v3. Once a v5 revision exists, it takes precedence; later work in an older GUI is not merged automatically. Original manual outlines are copied into an editable v5 record only through a reviewer action.

Saved records retain native mask runs, region identity, seed identity, edited pixels, decisions, uncertainty, origins, event history, source hashes, whole-field status, and limited exposure/timing information. Neither an untouched automatic suggestion nor simply opening a scan constitutes a human label. Whether suggestions were displayed in v5 is useful audit information, but does not prove what the person may have seen elsewhere. An unseeded region is not automatically an independent, blinded annotation.

## 7. Saved review-batch inventory on September 13

The table below reflects the JSON files inspected for this handoff. **Kept** counts region entries explicitly approved as Full Lesion; **Unsure** counts entries approved as Other. Dashes mean no saved v5 file, not zero CNVs. All scans belong to **TS267**; day labels identify visits and do not by themselves certify a negative/control scan.

| Visit / eye | Saved status | Kept CNVs | Unsure entries | Draft entries | Explicit reviewed absence |
|---|---|---:|---:|---:|---|
| D0 OD | In progress | 2 | 0 | 0 | No |
| D0 OS | In progress | 0 | 1 | 1 | No |
| D7 OD | In progress | 3 | 2 | 0 | No |
| D7 OS | Complete | 0 | 1 | 0 | No—uncertainty remains |
| D14 OD | In progress | 3 | 0 | 0 | No |
| D14 OS | Complete | 0 | 0 | 0 | Yes |
| D28 OD | Complete | 2 | 0 | 0 | No |
| D28 OS | No v5 file | — | — | — | Not recorded |
| D35 OD | Complete | 3 | 0 | 0 | No |
| D35 OS | No v5 file | — | — | — | Not recorded |
| D42 OD | Complete | 3 | 0 | 0 | No |
| D42 OS | Complete | 0 | 0 | 0 | Yes |
| D49 OD | Complete | 3 | 2 | 0 | No |
| D49 OS | Complete | 0 | 1 | 0 | No—uncertainty remains |
| D56 OD | Complete | 3 | 0 | 0 | No |
| D98 OD | Complete | 3 | 0 | 0 | No |
| D98 OS | Complete | 0 | 0 | 0 | Yes |

Of the 25 kept entries, **7 retain automatic seed IDs and 18 do not**. The latter may include manual copies or inherited work; they should not be labeled blinded independent drawings solely because their seed-ID list is empty. The **19 rejected entries must not be divided by the 29 original v3 proposals to claim a false-positive rate**: entries can originate from different sources and revisions, and a proper candidate-to-reference matching audit has not been performed.

### What the read-only inventory checked

The inventory checked native run bounds, agreement between approved masks and their saved reviewed runs, finished-scan counts, overlaps between kept CNV entries, overlaps between kept and unsure masks, and disconnected pieces within a kept CNV entry. It found no run/count inconsistencies, no positive–positive or positive–unsure pixel overlaps, and no kept CNV entry containing multiple disconnected components each at least 25 pixels. The 25-pixel threshold is an audit convenience, not a biological lesion definition. These checks do not prove that boundaries are correct or that all lesions were found.

The inventory records hashes and verified they remained unchanged during its read. It writes only this handoff's derived report/JSON; it does not modify human labels, generate training targets, adjudicate the images, or fit a model.

### Items to reconcile before calling the saved batch fully complete

1. Reopen **D0 OD, D0 OS, D7 OD, and D14 OD**. Confirm whether the whole image was reviewed and whether any post-finish edit reset the status. Resolve the remaining D0 OS draft, then use Finish scan where appropriate. Do not automatically change these flags from a script.
2. Reopen **D28 OS** (`TS267_OS_2025-03-19_D28_s01_103036`) and **D35 OS** (`TS267_OS_2025-03-26_D35_s01_103011`). No v5 review file or earlier v3/v4 region review was found for these selected acquisitions. If they are confirmed negative, record that explicitly with a whole-field review; file absence is not a negative label.
3. Spot-check the three saved absence scans: **D14 OS, D42 OS, and D98 OS**. Their recorded active-review times are approximately **8.2–8.9 seconds**. This is a reason to verify coverage, not proof of careless review: the timer cannot establish total historical inspection or annotation quality.
4. Adjudicate a small visual subset of positives, uncertain borders, and removed suggestions. Include **D0 OD's two kept entries** rather than assuming that a nominal D0 must be negative, and revisit the known D7/D14 challenges. Neither day labels nor current candidate counts should override the image and acquisition history.

The release `COMPLETE.json` and old `RESULTS.json` files describe software/pilot delivery, not live human-review completion. Use the current review JSON and this timestamped inventory for the post-batch status.

## 8. Proposed next plan toward automated CNV analysis

The detailed plan remains in [plans/CNV_UNET_PLAN.md](G:/OCT_TreeShrew/octa/outputs/octa-auto_cnv_v5/plans/CNV_UNET_PLAN.md). The sequence below incorporates the newly observed saved-batch status.

### Step 1 — Reconcile, visually audit, and freeze this batch

Resolve the six completion/save gaps above; inspect the remaining draft and the negative examples; review a sample of uncertain borders, potential misses, and removed candidates. Distinguish biological lesion instances from sidebar entries and legacy connected components. Freeze a versioned reference manifest containing exact acquisition IDs, latest authoritative region revisions, source hashes, category/coverage semantics, and an explicit uncertainty mask policy.

**Deliverable:** an audited TS267 development reference set and a documented disposition for every scan. A full training exporter is a subsequent implementation task, not something performed by this handoff inventory.

### Step 2 — Expand beyond TS267 and define independent evaluation

Add several other animals, confirmed negatives, both eyes where appropriate, lesion stages, low-signal examples, vessel/edge artifacts, and difficult rather than only obvious lesions. The earlier suggested **20–30 fully reviewed acquisitions across several animals** is a starting annotation budget, not a statistically sufficient cohort or a reason to collect more repeats from one animal alone.

Group **all visits, eyes, repeats, crops, and augmented images from an animal into the same partition**. Use animal-level development folds and reserve different animals for final evaluation before selecting models or thresholds. Numeric animal identity governs grouping because sex letters in filenames can conflict.

The current upstream ALL_LABELLED segmentation already saw TS267 and other labeled animals. Holding an animal out of CNV training does not undo exposure in a thickness-producing upstream model. For an end-to-end independent thickness-assisted evaluation, use animal-excluded upstream segmentation or genuinely new animals unseen by either model; otherwise explicitly report the narrower scope of independence.

**Deliverable:** a split manifest, an acquisition/review queue, and an upstream-exposure audit.

### Step 3 — Implement a conservative label exporter and train a baseline

Build a **CNV image-segmentation U-Net**, separate from the retinal-boundary U-Net. U-Net is an image model, not an LLM; the existing eight-boundary prediction head is not a CNV-footprint head. Reuse sound project infrastructure and provenance handling, not an assumed interchangeable output layer. The proposed architecture follows the image-segmentation family described in the [original U-Net paper](https://arxiv.org/abs/1505.04597); that paper is motivation for a baseline, not evidence of performance in this dataset.

First compare structural OCT alone, real OCTA alone, and their aligned combination. Only then test whether selected thickness maps with explicit missingness channels improve detection. Use raw numerical images, not colored GUI screenshots or annotation overlays. Thickness or vessel channels used for autonomous evaluation must not depend on target-specific manual corrections that would be unavailable in deployment.

Export kept footprints as positives, explicitly completed fields as background outside positive/unsure masks, partial unmarked fields as unknown, and unsure areas as ignored. Reconcile rejected candidates against positive and unsure labels before using them as hard negatives. Do not treat unedited suggestions as human supervision. Compare a compact 2D U-Net with an nnU-Net baseline if justified by the dataset and workload; see the [nnU-Net paper](https://www.nature.com/articles/s41592-020-01008-z) and the separate plan for the proposed experiment.

**Deliverable:** a reproducible, audited dataset export and a first trained baseline with probabilities, source manifests, and development-fold predictions. No such export or training was performed here.

### Step 4 — Evaluate against the existing heuristic suggestions

Run a fresh comparison against the unchanged v3 suggestions using the newly audited reference. Define one-to-one lesion matching before scoring. Measure missed-lesion sensitivity, false positives per scan, precision, scan-level false positives/negatives, count error, boundary overlap/error where borders are reliable, and uncertainty by animal and failure type. Handle empty/negative scans explicitly.

Measure practical review burden as well: time and number of additions, corrections, removals, and acceptances. The objective is fewer misses and false proposals with less human work—not merely fewer candidates or smoother circles. Report raw predictions before shape/count filtering so a four-lesion display limit cannot disguise errors. The old 75 µm legacy location hit rate is only historical development evidence.

**Deliverable:** an error atlas and a comparison table with uncertainty estimates grouped by animal, plus a prespecified decision about whether the new model is actually useful.

### Step 5 — Review mistakes, iterate, and earn full automation

Create an active-review queue combining uncertain predictions, suspected false positives, possible misses, model disagreements, and a fixed random sample. Keep negative scans in the loop. Retrain on reviewed development additions, preserve every model/data revision, and keep the final test set out of this feedback process.

If failures persist only in depth, consider a later B-scan-stack/2.5D stage; do not assume a larger model solves a sparse or inconsistent label set. Agree acceptance thresholds before looking at the final test results. Evaluate a frozen model on unseen animals and prospectively acquired scans before an automation trial. Keep review fallback for poor acquisition quality or unstable predictions, and version downstream area/thickness analysis separately from lesion detection.

**Deliverable:** a measured decision on readiness for an automation trial, with a rollback and human-review path. Adopting U-Net alone does not establish full automation.

## 9. Practical entry points and handoff files

| Item | Location |
|---|---|
| Manual review / D14 | [OPEN_MANUAL_REVIEW.cmd](G:/OCT_TreeShrew/octa/outputs/octa-auto_cnv_v5/OPEN_MANUAL_REVIEW.cmd) |
| Automatic suggestions / first scan | [OPEN_OCTA_AUTO_CNV_V5.cmd](G:/OCT_TreeShrew/octa/outputs/octa-auto_cnv_v5/OPEN_OCTA_AUTO_CNV_V5.cmd) |
| Saved manual / D7 | [OPEN_SAVED_MANUAL_D7.cmd](G:/OCT_TreeShrew/octa/outputs/octa-auto_cnv_v5/OPEN_SAVED_MANUAL_D7.cmd) |
| Current GUI instructions | [START_HERE.md](G:/OCT_TreeShrew/octa/outputs/octa-auto_cnv_v5/START_HERE.md) |
| Separate detailed model plan | [CNV_UNET_PLAN.md](G:/OCT_TreeShrew/octa/outputs/octa-auto_cnv_v5/plans/CNV_UNET_PLAN.md) |
| This handoff's saved-file evidence | [REVIEW_BATCH_INVENTORY.json](G:/OCT_TreeShrew/octa/outputs/cnv_review_handoff_20260913/REVIEW_BATCH_INVENTORY.json) |
| V5 implementation verification | [verification](G:/OCT_TreeShrew/octa/outputs/octa-auto_cnv_v5/verification) |
| V5 interface example, OCTA mode | [v5_octa.png](G:/OCT_TreeShrew/octa/outputs/octa-auto_cnv_v5/verification/v5_octa.png) |
| V5 interface example, thickness mode | [v5_thickness.png](G:/OCT_TreeShrew/octa/outputs/octa-auto_cnv_v5/verification/v5_thickness.png) |

The screenshots are delivery-time examples of the interface, not a visual audit of the newly completed annotation batch. Previous GUI versions, original labels, and model files remain available. The immediate next work is to reconcile and audit the saved review state; model development follows that audit as a separate task.
