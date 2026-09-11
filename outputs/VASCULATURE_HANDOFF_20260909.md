# Handoff: major-vessel segmentation and editable 32-scan queue

**Date:** 2026-09-09  
**Workspace:** `G:\OCT_TreeShrew\octa`  
**Status:** Implementation and queue preparation are complete. The user can correct automatic vessel masks in the en-face GUI instead of tracing from scratch. No segmentation model was trained.

## User's request and decisions

The user initially supplied screenshots and said they had drawn two vessel masks. They asked whether image contrast and shape could handle this without training a model, whether 32 annotations were really necessary, and asked us to try several scans.

They explicitly narrowed the target to **only clearly visible major vessels for now**; smaller vessels may be considered later. These are the dark large-vessel features in the **structural OCT en-face projection**, not a capillary-flow or CNV vessel-density analysis.

We produced a classical contrast-and-shape baseline on six scans. The user liked the result and requested a gate to remove round/small detections and favor continuous thick bands. After seeing that cleanup, they approved it and asked us to prepare **all 32 existing en-face examples as editable starting masks**. We completed that and reopened the GUI.

The earlier advice to try 6–8 reviewed masks first was an incremental evaluation suggestion, not an established sample-size requirement. It was superseded operationally by the user's explicit request to preload the entire 32-scan queue. The number 32 comes from the existing broader review queue; it is not a measured minimum for vessel-model training.

## What is ready now

- All **32** scans in `G:\OCT_TreeShrew\octa\outputs\eight_surface\segmented` have automatic major-vessel proposals.
- At preparation, **three** scans already had saved human vessel masks. All three were preserved; the other **29** scans preload automatic masks.
- The third human vessel mask, TS169 OS, was discovered during the queue work. Do not keep assuming there are only two human masks.
- All **28 existing en-face/CNV annotation files** had unchanged SHA-256 hashes at the end of preparation, before reopening the interactive GUI. CNV/ONH annotations were preserved.
- The GUI was reopened successfully at **scan 4 of 32**, `TS241_OD_2024-09-25_D42_s03_111600`, the first unfinished vessel review at that time. Startup verification confirmed a visible window, an unreviewed automatic mask, and 25,203 vessel pixels.
- The GUI process was still running when this handoff was written. Its startup screenshot/JSON are historical startup evidence, not a live progress tracker. The user may have reviewed more scans since then; inspect current labels before reporting a new count.

The three saved vessel masks at preparation were:

1. `TS165_OD_2025-04-29_WT_s06_114517`
2. `TS165_OS_2025-04-29_WT_s02_121711`
3. `TS169_OS_2025-01-14_D35_s04_121533`

## Opening and using the GUI

Activate the environment first. Do **not** invoke the environment's Python executable directly: on this Windows machine, skipping activation can cause MKL/matplotlib interpreter crashes.

```powershell
. D:\Anaconda\shell\condabin\conda-hook.ps1
conda activate octa
Set-Location G:\OCT_TreeShrew\octa
python code\open_enface_vessels.py
```

This launcher selects the first scan without a completed vessel review. The ordinary `code\eight_surface\cnv_gui.py` also discovers the automatic proposals by default.

User controls:

1. Select **Vasculature brush** or press **V**.
2. Left- or right-drag paints; **Ctrl+right-drag erases**.
3. Adjust brush diameter as needed; undo/redo works.
4. After inspecting the whole vessel mask, tick **Vasculature reviewed**.
5. Use **Save en-face labels / Ctrl+S**, then proceed to the next scan.

Dirty edits are also saved when navigating or closing. Partially corrected masks can remain unreviewed drafts and resume exactly as saved. The sidebar now scrolls so controls remain accessible on smaller screens. There is no need to reopen or restart an already active GUI merely to read this handoff.

## Critical annotation/provenance behavior

Automatic proposals and human annotations are separate:

- **Automatic starting masks:** `G:\OCT_TreeShrew\octa\outputs\eight_surface\vasculature_proposals\<scan_id>_proposal.npz`
- **Human saves:** `G:\OCT_TreeShrew\octa\outputs\cnv_labels\<scan_id>_cnv.npz`

The batch script never writes human labels. The GUI loads a proposal only if that scan's vessel class has no saved work. Saved nonempty manual masks, reviewed empty masks, and saved automatic drafts all take priority. Even a saved **empty unreviewed draft** must not be refilled on reopening.

New GUI saves use label format **`4-enface-vessel-proposals`**; formats 1, 2 and 3 still load. Fields include:

- `vasculature_mask`: final/current editable mask.
- `vasculature_origin`: `manual` or `automatic_proposal`.
- `vasculature_proposal_path`, `vasculature_proposal_sha256`: seed provenance.
- `vasculature_initial_mask`: original automatic starting mask.
- `vasculature_brush_touched`: actual brush footprint, including erase strokes; undo/redo restores it too.
- `reviewed_targets`: explicit decisions in **CNV, VASCULATURE, ONH** order.

Painting part of an automatic mask does **not** mark the whole vessel class reviewed. The user must explicitly check the review box. A reviewed automatic-origin mask means the human reviewed it, not that every pixel was redrawn. Untouched automatic pixels must not be misrepresented as manual strokes. Older labels have no retrospective stroke provenance.

Loading an untouched proposal and closing without changes creates no human annotation. CNV/ONH contents and their review flags retain their existing behavior; linked B-scan surface review is preserved.

## Algorithm that the user approved

No neural network or random forest was trained. The final contrast threshold was calibrated on the initial two TS165 brush masks, and both informed development; this is not a completely label-independent method.

Input is the original processed-volume **structural** projection, not screenshots: mean `20*log10(amplitude)` over the same stored retinal band used by the GUI. Work remains in native **[B-scan, A-line]** coordinates, normally 512 × 512. No predicted retinal surface defines the projection. Depth averaging is invariant to depth reversal, so this projection step does not use the historically unreliable stored orientation flag.

The contrast baseline uses background subtraction, multiscale Hessian ridge evidence, limited correction of persistent field-wide intensity steps, and a fixed final evidence threshold of **0.18**. It leaves the outer ten pixels unassessed because of image-frame artifacts. Evidence is a filter response, not calibrated probability or acquisition quality.

The approved shape gate uses the **same settings on all 32 scans**:

| Parameter | Value |
|---|---:|
| Minimum connected area | 600 pixels |
| Minimum estimated centerline span | 80 pixels |
| Minimum median centerline width | 6 pixels |
| Minimum centerline length / width | 5 |
| Minimum terminal side-branch length | 35 pixels |

Short/narrow terminal offshoots are pruned in one pass; internal connections are retained. Centerline span uses a weighted skeleton graph with a two-sweep geodesic estimate, allowing curved and branching vessel networks rather than rejecting them based on a round overall outline. The gate **only removes existing candidate pixels**; it does not fill unsupported gaps. Median width is a component criterion, not a guarantee at every cross-section. These are pilot cleanup settings, not validated biological cutoffs.

## Measurements and limitations

The original six examples were the two TS165 eyes plus:

- `TS247_OD_2024-10-30_D14_s05_105423`
- `TS267_OD_2025-04-16_D56_s03_102014`
- `TS305_OD_2025-08-07_D35_s01_114451`
- `TS325_OD_2026-03-03_D98_s01_131308`

The six approved shape-gated masks reproduced **exactly** during 32-scan preparation. No contrast or shape parameters were retuned for the additional scans.

Comparison against the two initial human brush masks:

| Scan | Dice before → after gate | Precision before → after | Recall before → after | Previously matched vessel pixels retained |
|---|---:|---:|---:|---:|
| TS165 OD | 0.724 → 0.726 | 0.728 → 0.750 | 0.719 → 0.704 | 98.0% |
| TS165 OS | 0.730 → 0.727 | 0.684 → 0.706 | 0.782 → 0.749 | 95.8% |

The gate improves precision, sacrifices some recall, and leaves mean Dice essentially unchanged. It reduced connected regions across the six examples from **79 to 29**, removing **27,206** candidate pixels; not every removed region was false.

These are **development comparisons**, not independent validation: the initial two masks are opposite eyes of the same animal/session and informed development. Existing human ONH exclusion is reused for the OS comparison and shown in green; automatic ONH detection was not implemented. Human-painted vessel pixels in the unassessed border still count as misses. The four other pilot scans had no reviewed vessel masks and were not assigned accuracy scores.

Known remaining problems:

- Long image borders/seams can still look like vessel bands.
- Some elongated lesion or motion artifacts pass the shape gate.
- Short true vessel fragments, including clipped edge vessels, can be removed.
- Existing gaps, incorrect widths and missed weaker stretches remain.

These are **editable starting masks**, not validated final analysis masks. Small-vessel/capillary segmentation remains outside the user's current scope.

## Files and implementation

Important reports:

- [Original six-scan baseline](G:/OCT_TreeShrew/octa/outputs/vasculature_baseline/20260909_major_vessels/START_HERE.md)
- [Shape-gate comparison](G:/OCT_TreeShrew/octa/outputs/vasculature_baseline/20260909_major_vessels_shape_gate/START_HERE.md)
- [32-scan queue guide](G:/OCT_TreeShrew/octa/outputs/vasculature_baseline/20260909_queue32/START_HERE.md)

The queue report directory also contains `manifest.json`, `queue_verification.json`, two 16-scan contact sheets, individual previews, and `gui_ready.json` / `gui_ready.png`. The proposal directory has a manifest too. Manifests record settings, code hashes, source/proposal details and preparation-time human-label hashes.

Code added in this conversation:

- `code/vasculature_baseline.py`: original contrast/Hessian pilot and calibration/report generation.
- `code/vasculature_shape_gate.py`: geometry gate and six-scan comparisons.
- `code/prepare_vasculature_queue.py`: generates proposals for the existing 32-scan queue.
- `code/eight_surface/vasculature_proposals.py`: validates/loads proposals and determines saved-work priority.
- `code/open_enface_vessels.py`: opens the first unfinished vessel review and records startup verification.
- `code/test_vasculature_baseline.py`, `code/test_vasculature_shape_gate.py`, `code/test_enface_vessel_proposals.py`: behavior/lifecycle tests.

Code updated: `code/eight_surface/cnv_gui.py` and `code/eight_surface/cnv_labels.py`. Documentation updated: project `README.md`, `PIPELINE.md`, and `code/eight_surface/README.md`.

The repository already had uncommitted GUI/CNV changes when this conversation began. We preserved and extended them; do not revert unrelated working-tree changes. No commit was created here. No retinal layer priors, trained layer models or raw acquisition files were changed by this vessel work.

## Verification completed

- All 32 proposals passed GUI-loader ID, native-grid, source-volume and retinal-band checks.
- All six pilot masks were reproduced exactly by batch generation.
- Existing human annotation hashes were unchanged during preparation.
- Four baseline tests and six shape-gate tests passed during pilot work.
- Eighteen workflow checks passed for queue integration: eight new proposal/draft lifecycle tests, one existing integrated GUI test and nine existing CNV workflow tests.
- Tests cover save/reload, undo/redo, empty drafts, reviewed absence, preserved manual masks, explicit review, old label compatibility, source/grid mismatch, CNV packs and linked surface review.
- The real GUI was launched and visually inspected with the correct automatic mask, existing CNV markings and unchecked vessel-review status. No startup error was logged.

To run integration checks after activating `octa`:

```powershell
Set-Location G:\OCT_TreeShrew\octa
python -m unittest discover -s code -p test_enface_vessel_proposals.py -v
python -m unittest discover -s code -p test_enface_segmentation_gui.py -v
Set-Location G:\OCT_TreeShrew\octa\code
python -m unittest eight_surface.test_cnv_workflow -v
```

## Guidance for the next conversation

The current task is complete and ready for human correction; do not automatically retrain a model, regenerate the queue or replace saved work. Read the project's `AGENTS.md`, `README.md` and `PIPELINE.md` before making further pipeline changes. Respect the distinction between automatic proposals, brush edits and explicit review decisions.

If asked to assess the next iteration, inspect current saved labels first because the user may have continued editing. Measure corrections and failure cases, ideally separating animals for development/evaluation. A small random-forest pixel classifier was discussed as a possible later step if rules require too much cleanup; a U-Net was a later fallback. Neither was implemented or authorized as the next automatic action.

Source inputs must remain `*_processedVolumes.mat` (HDF5), never `.RAW` reconstruction. Keep outputs under `octa/outputs`. Human annotations are written by the GUI, not hand-generated from a batch script. Continue using the activated `octa` environment.
