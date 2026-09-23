# Train CNV v9: corrected-label baseline and vessel/ONH-aware comparison

Implement, train, verify, and deliver two CNV footprint models in this repository:

- **v9 Model 1** (`v9_m1`): the v8 conservative Model 1 segmentation recipe, trained using only the latest CNV correction round.
- **v9_m2**: the same corrected CNV supervision and comparable segmentation training, adding vessel/ONH context and a fitted candidate-level confidence adjustment using size and vessel/ONH relationships.

Run both models on the **same 50 new acquisitions**, and deliver a local HTML comparison gallery so I can inspect them and choose a model before starting another correction round. Complete the work rather than stopping at a proposed implementation. Do not automatically choose a winner or start another training cycle after delivery.

## Working directory and immutable inputs

Project: `G:\OCT_TreeShrew\octa`.
Read `AGENTS.md`, `README.md`, `PIPELINE.md`, and applicable skill instructions. Activate the `octa` conda environment before Python; do not invoke its executable without activation. Read processed MATLAB/HDF5 inputs only; never reconstruct RAW or modify source acquisitions.

All new code, checkpoints, manifests, inference caches, reports, gallery assets and launchers belong under `outputs/octa-auto_cnv_v9/`. Preserve every existing annotation, model, prediction, export and GUI. Older releases are read-only inputs. Record hashes of consumed labels, masks, model source and selection manifests. Use atomic writes and resumable stages with a duplicate-run guard.

CNV supervision:
`outputs/octa-auto_cnv_v8/manual_review/review/regions/`

Correction queue and derived reports:
`outputs/octa-auto_cnv_v8/manual_review/queue/queue.json`
`outputs/octa-auto_cnv_v8/manual_review/reports/quantification/`

Baseline implementation and configuration:
`outputs/octa-auto_cnv_v8/model1/config.json`, `models.py`, `train.py`, `sampling.py`, and relevant input/inference code.

**Use this exact vessel/ONH export:**
`G:\OCT_TreeShrew\octa\outputs\octo-vessel_onh_v2\final_output_v1`

Read its `README.md`, `manifest.json`, `VERIFIED.json` and `load_masks.py`. Despite its parent folder's name, this export contains **58 saved manual records and 256 frozen v1 fallback records; it contains no learned v2 predictions**. Do not substitute `octo-vessel_onh_v2/predictions`. The prior overlap measurements discussed for learned v2 do not describe this export; measure this export separately.

## Audit and freeze the correction targets

“Corrected labels only” means **this latest 30-acquisition correction round**, not the older 67-acquisition v8 training dataset. Do not silently add earlier v7/original labels. Explicitly confirmed unchanged proposals are valid human-confirmed labels; do not require a brush edit when the whole-field confirmation is valid.

At prompt preparation the saved state was 29 confirmed acquisitions: 21 positive, eight negative, 44 kept CNV regions. One acquisition, `TS247_OD_2024-10-23_D7_s05_114003`, was deliberately deferred with “weird image and unsure if cnv there.” Re-audit current source records rather than hard-coding these counts. A valid later confirmation may supersede that state; otherwise exclude the deferred acquisition from training, normalization, calibration and scoring. Do not force it to negative or fall back to an older annotation.

Validate current annotation signatures, revision, source identity, grid and stored masks using the correction schema. Derive a frozen v9 supervision snapshot without modifying labels or refreshing upstream reports in place. Train only from the snapshot's explicit manifest; do not glob historical target revisions.

- Kept regions in a valid confirmed image supply positive pixels.
- Other assessable pixels in that confirmed image supply reviewed background, including confirmed no-CNV fields.
- Unsure/excluded pixels remain unknown and are masked out of the loss.
- Drafts, deferred fields, removed regions and automatic proposals are not positive labels. A removed proposal supplies negative evidence only where the final whole-field confirmation establishes background; overlap with a final kept region stays positive.
- Preserve every confirmed small or irregular footprint. Apply no size, vessel or ONH filtering to the human targets.

Retain animal, eye, visit/date, actual/nominal day basis, acquisition, annotation revision, source hash, proposal origin and v8 training exposure. Keep the 10 prior v8 reference cases distinguishable from the 20 acquisitions originally excluded from v8 fitting. That historical distinction is not an independent test split for v9.

## v9 Model 1

Keep the v8 Model 1 compact U-Net and original 19-channel input recipe as the baseline, including its existing handling of unavailable measurements. Add no new `final_output_v1` vessel/ONH channels or candidate-size confidence adjustment to this model. “Labels only” specifies the supervision source, not a label-only or single-channel input network.

Start from **fresh weights**, not the all-animal v8 checkpoint. Use the v8 training defaults as the controlled starting point: seed 267, 100 epochs, 32 optimizer steps per epoch, effective batch four, AdamW learning rate 0.001 and weight decay 0.0001. Preserve the baseline loss and animal-balanced sampling where applicable to the smaller corrected cohort. Audit whether each sampling pool actually exists; document deterministic fallbacks. Existing model predictions may locate difficult reviewed-background patches but never supply truth.

Fit normalization only on the applicable training partition. Use mixed precision/microbatch accumulation if needed, preserving effective batch and optimizer-step counts. Save resumable optimizer, scaler and RNG states. Any necessary deviation from the baseline must be recorded with its reason.

Export raw probabilities and unfiltered threshold candidates. Retain the v8 conservative display policy as a separately named comparison view if useful; do not silently delete small candidates from the primary raw output.

## v9_m2

Use the same CNV supervision, animal partitions, seeds, training budget and backbone depth/width as v9_m1. Add native vessel and ONH context channels from `final_output_v1`, plus explicit availability/review/uncertainty context sufficient to distinguish unknown masks from reviewed absence. Record the exact channel definitions.

Join by acquisition identity and validate source/grid/hash through the export loader. Masks are native `[B-scan, A-line]`, 512 × 512; do not transpose, flip or silently register. En-face projection depth ranges may differ. Respect `excluded_from_analysis`; export presence is not authorization to train on an excluded scan. If exclusions affect the CNV cohort, use a common eligible cohort for both models and report the reason for each omission.

Manual exports can contain drafts and untouched automatic pixels. Use them as provenance-qualified context, not as exhaustive ground truth. Vessel and ONH review statuses are separate. Empty fallback ONH masks do not establish absence. Mask unknown context explicitly rather than making absence claims. If some training acquisitions lack usable context, retain them with declared missing-context channels; never silently replace a missing file with a trusted empty mask. Report context coverage by source and target.

Add a **small regularized candidate-level confidence model** after segmentation. Its features should include raw candidate probability summaries, log observed area, vessel overlap/proximity, ONH overlap/proximity, and context availability/reliability. Keep feature count modest for this dataset. Fit size-related behavior from reviewed evidence; do not invent a biological minimum size from the smallest observed lesion.

Generate fitting examples from predictions made without training the CNV segmenter on that animal. Match candidates against confirmed positive/background/ignored masks with an explicit, frozen matching policy. Audit splits, merges and ambiguous overlaps; ambiguous or insufficiently assessed candidates should not be confidently assigned false/true labels. Fit and select any adjustment without access to its evaluation animals. Do not fit a confidence model to in-sample segmentation outputs and report it as independent performance.

The adjustment changes a **candidate's score/ranking**, not its footprint geometry. Save raw score, adjusted score, size, context features, matching/calibration provenance and any display-selection reason. Do not clip vessel pixels out of CNVs, impose a zero-overlap rule, force round shapes, or hard-delete small candidates. Candidates beyond the supported size range or with missing context need an explicit extrapolation/availability flag. Call scores uncalibrated unless calibration is demonstrated.

Show both m2 raw and adjusted results, so we can distinguish changes due to its segmentation network from changes due to candidate scoring. Size is a confidence feature; it is not an extra annotation target or a command to reproduce the cohort size histogram.

## Fair comparison and leakage controls

Use animal-grouped development evaluation with fresh weights and training-only normalization. Keep all eyes, visits and repeat acquisitions of an animal in its partition. Freeze partitions, calibration roles, candidate matching and metrics before inspecting results or the new gallery. A shared deterministic nested animal-grouped scheme can provide out-of-sample candidate examples and independent adjustment evaluation; document its cost and exact roles. Never reuse a candidate's evaluation label for fitting its adjustment.

Audit vessel context provenance for label-informed corrections or derivation that compromises evaluation. Report manually assisted and frozen automatic context separately. No new-image or unseen-animal accuracy guarantee follows from these small development folds or a manually assisted context pipeline.

Report lesion detection recall/precision, false positives per acquisition, pixel Dice/IoU, acquisition-total-area error, and per-lesion area error for matched lesions. Include size strata derived from training animals only, negative fields and per-animal results. Keep raw and adjusted m2 results separate. Inspect matching failures and do not portray connected-component correspondence as confirmed biological identity. Save development results separately from final all-confirmed-label inference models.

Final deployment fits may use all eligible confirmed correction labels after development settings are frozen. The final m2 candidate scorer may use the pooled appropriately out-of-sample candidate examples from that cohort. Save both deployable model bundles with normalization, context policy, confidence model and thresholds. Do not claim that development calibration necessarily transfers unchanged to the all-label fit.

## Fifty new acquisitions

Select **50 distinct acquisitions, shared by both models**, before inspecting their predictions. Use a fixed seed and balanced coverage of available non-WT animals and post-laser visits, targeting CNV review opportunities. Prefer post-day-7 acquisitions using actual days when known; record nominal-day discrepancies. Selection must not depend on which model predicts more attractive CNVs.

Exclude the entire v8 30-scan preview/correction queue, every acquisition with prior CNV supervision or use in the v9 fitting/calibration pipeline, duplicate source identities, known rejected-quality acquisitions, and acquisitions without usable processed inputs. Prior vessel-only review or prior automatic CNV inference does not by itself make an acquisition ineligible, but record that exposure. Audit all available historical CNV annotation inventories when establishing novelty, not just the v9 target folder.

Require the specified vessel/ONH export for all 50 so both models can be compared. Balance repeat acquisitions and avoid filling the gallery with nearly identical same-visit repeats; retain visit groups. Freeze the chosen acquisition list, eligibility audit and selection seed before inference. Use deterministic metadata-based replacements for missing/corrupt providers and log them. If fewer than 50 eligible acquisitions exist, report the actual shortfall instead of reusing reviewed scans or manufacturing “new” cases.

“New CNVs” means **new model-proposed candidate lesions requiring review**. Do not guarantee 50 confirmed-positive scans, discard zero-candidate cases to improve appearances, or label every prediction as actual CNV. All 50 scans must remain visible in the gallery.

## HTML gallery first

Provide a double-click launcher, a locally served HTML gallery if needed for array access, and a concise START_HERE guide. Validate the gallery in a real browser where available and save representative screenshots.

For each of the 50 acquisitions show aligned structural OCT and actual OCTA en-face views, v9 Model 1 candidates, v9_m2 raw candidates and v9_m2 confidence-adjusted candidates. Use identical geometry, image contrast and overlay conventions for comparison. Include:

- Scan/animal/eye/visit/day identity, prior exposure, mask source, quality/exclusion notes and queue position.
- Independent toggles for vessel, ONH, both CNV models and raw/adjusted m2 visibility; make the m2 adjustment easy to compare without overcrowding the initial view.
- Synchronized en-face navigation and linked native structural B-scan inspection, including rows 0 and 511, zoom/pan, and footprint intersections as lateral bands. These bands are not axial lesion segmentation.
- Candidate area in pixels and approximate µm²/mm², raw/adjusted score, context availability and overlap measures. Size estimates remain provisional until human correction.
- A view of candidates down-ranked or hidden by a display threshold, with adjustment reasons and easy recovery; retain all raw arrays.
- Filtering/navigation for animal, visit, zero-candidate cases and model disagreements. Every selected acquisition remains accessible.
- Optional persistent reviewer preference: Model 1 / Model 2 / neither / unsure, with notes and JSON export. Gallery preferences are not CNV ground truth and do not change annotations or trigger training.

Use this gallery for the initial model comparison. Do not open a correction GUI automatically. Prepare a manifest retaining both prediction choices so the selected model can later be loaded into the v7-style correction workflow without rerunning inference. Do not fabricate reviewed masks or pre-confirm candidates.

## Verification and handoff

Test source/grid/orientation matching, positive/background/ignored targets, partition separation, context availability versus absence, provenance exclusions, candidate matching and confidence export, size conversion, identical 50-scan membership, raw-candidate preservation, resume behavior and gallery navigation/overlays. Include meaningful synthetic checks isolated from human records plus bounded real-data checks.

Preserve canonical image orientation using the established processing functions and validated caches. Report approximate en-face footprint areas using the project's calibration; do not report lesion volume, unique biological-lesion totals across repeated scans, or CNV vascular density from these footprints.

Deliver a concise report with the final supervision counts and exclusions, model differences, context-source breakdown, independent development results and limits, actual training settings/checkpoints, all 50 inference statuses, gallery launch path and verification evidence. Check that consumed human annotations and frozen upstream outputs remain unchanged. Finish with both model bundles and the HTML gallery ready for me to inspect and choose between them.
