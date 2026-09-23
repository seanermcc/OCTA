# Implement CNV footprint review v7 and document the next training round

Work in `G:\OCT_TreeShrew\octa`. Implement and verify a new standalone CNV footprint annotation GUI in:

`G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v7\`

This is an implementation request: build the application, prepare its reproducible review queue, verify it on real acquisitions, and write the future training plan. Do not stop at another proposal. Do not train a model in this task. The desired outcome is a working application in which I can complete **30 distinct en-face images containing confirmed CNVs**, alongside useful confirmed negative images, and then return for model training.

The target is now **30 positive images, not 30 individual lesions or 30 B-scans**. An image with three confirmed CNVs counts as one positive image. Each reviewed image must include all CNVs I can identify in that field.

## 1. Read the project and preserve existing work

Read `AGENTS.md`, `README.md`, `PIPELINE.md`, `DEMO_GUIDE.md`, and `.agents/skills/octa-layer-segmentation/SKILL.md`. Relevant application sources and reports are:

- `outputs/octa-auto_cnv_v5/START_HERE.md`, `viewer.py`, `review_store.py`, `loader.py` and `thickness.py`: the preferred simple labeling workflow and whole-field review semantics.
- `outputs/octa-auto_cnv_unet_v6/START_HERE.md`, `ANNOTATION_AND_INPUT_AUDIT.md`, and `evaluation/SEED_REPORT.md`: model and supervision history.
- `outputs/octa-auto_cnv_unet_v6/all_samples/START_HERE.md`, `inventory.json`, `scan_status.csv`, `models.json`, `records/`, and `comparison/`: completed cohort inventory, native inputs and predictions.
- `outputs/octa-auto_cnv_unet_v6/review/START_HERE.md`, `loader.py`, `common.py`, and `viewer.py`: current all-acquisition loading, caching and prediction review.
- `outputs/cnv_review_handoff_20260913/CNV_GUI_HISTORY_AND_NEXT_STEPS.md`: historical development context. Its statements that no CNV U-Net exists and its older review-completion counts have been superseded by v6 and the live records.
- `outputs/cnv_unet_pilot_20260913/CNV_UNET_PILOT_PLAN.md`: historical pilot design; the pilot was subsequently implemented as v6.

Keep v1-v6 implementations, released predictions/checkpoints and original human annotations unchanged. All new code, manifests, annotations, logs, caches, verification artifacts and documents belong under v7. Large immutable existing image arrays can be referenced with provenance rather than copied. Do not write to `OCTA_RawData` or `MATLAB Code`.

Beware of importing old helpers that compute write destinations from `__file__` or mutate module globals. Build an explicit v7 storage boundary and test that application use cannot write into old releases. Browsing alone must not manufacture annotation decisions.

## 2. Random review queue spanning the available non-WT animals

Refresh the real processed-acquisition inventory before constructing the queue. At prompt preparation, there are **324 distinct processed acquisitions from 11 animals**, including WT animal **TS165**. Thus the requested non-WT queue currently contains **10 animals**, in numeric order:

`TS169, TS241, TS247, TS250, TS267, TS283, TS305, TS325, TS328, TS336`

Do not fabricate an eleventh non-WT animal or include WT merely to reach eleven. Generate the eligible list from verified metadata and report changes if the inventory has changed. Use numeric animal identity, not sex suffixes.

Eligibility and sampling:

1. Include distinct acquisitions with an available processed volume and a usable native image provider. Select non-WT acquisitions **strictly after day 7**. D7 itself is excluded for this queue; make the threshold explicit in the configuration and guide.
2. Prefer verified `days_post_laser`. Where unavailable, use the indexed nominal day or an explicitly parsed day label and record that basis. Handle labels such as `D92` and `6 mo`; do not silently lose an acquisition merely because its numeric `day` column is blank. Exclude before-laser, laser-day, D0, WT and unresolved timepoints. Report discrepancies rather than infer true laser dates from folder names. Existing TS336 day-label discrepancies must remain visible in provenance.
3. Post-D7 status means **eligible for inspection**, not known CNV-positive. Model detections and day labels do not establish the presence or absence of CNV.
4. Use a fixed, recorded random seed and persist the exact queue. Within each animal, randomly order visit/date groups and choose among eyes/acquisitions without replacement. Cycle through different available visits before spending the queue on many same-visit repeats. Randomize within those groups; avoid always choosing scan 1 or OD. Animals with only one eligible visit can still contribute different acquisitions, with the limitation recorded.
5. Interleave one candidate per animal in the fixed numeric animal order, then repeat the cycle. Preserve that order across restarts. Skip exhausted pools with an explicit recorded reason. Do not duplicate byte-identical inputs or the same acquisition under different file paths.
6. Prepare enough candidates to continue beyond the first 30 inspected images: a negative, skipped, unusable or unfinished image does not fill a positive-image slot. Persist the full eligible queue or a reproducible ordered reserve. Do not describe the first 30 random candidates as 30 known CNV images.
7. Keep selection independent of U-Net score, model consensus and existing positive labels. Those can be inspected as optional context, but this main queue must not select only lesions the current model already finds. Record which candidates already have historical review evidence.
8. Freeze queue version, seed, source identity, day basis, animal, eye, session, repeat/acquisition identity and ordering rationale in human-readable and machine-readable manifests. New inventory discoveries should not reshuffle an active queue silently.

Provide Previous/Next, Next pending, resume last case, an acquisition dropdown/search, animal/day filters and a clear return to the fixed queue. Manual browsing must not rearrange the queue. Show the animal, eye, date/day basis and scan identity without requiring the user to interpret a long filename. A compact skip/defer action may record a reason but must not imply a negative label.

## 3. Simple v5-style labeling interface

Use the familiar two top image panels and a linked native structural B-scan below:

- Left: structural OCT en face.
- Right: actual OCTA, with optional existing layer-thickness views if straightforward to preserve. OCTA must use the real OCTA channel, not a thickness-derived substitute. Explain that the existing projection spans the saved retinal crop, not a layer-specific slab.
- Bottom: matching native structural B-scan, with slider/spin box and direct navigation by en-face click.
- A concise CNV region list and controls: **Add CNV, Paint, Erase, Keep CNV, Remove, Unsure, Undo/Redo, Save, Confirm entire image**. Closed paint loops fill their interior, as in v5. Each separate lesion remains a separate region. Do not constrain human masks to circles, a size range or a lesion-count cap.
- **No-CNV present** checkbox, with the exact meaning specified below.
- Persistent positive-image progress, negative-image count and completion status.

Start in manual labeling mode with automatic suggestions hidden. Allow optional read-only original v6 suggestions and historical manual overlays, separately toggled and labeled. Do not require the user to rate B/C models or cycle through seeds to complete an annotation. A simple default v6 C/seed-267 context overlay is acceptable, clearly identified as an unreviewed prediction, without implying that this seed is validated as best.

If copying a suggestion or old footprint into the editable annotation is supported, require an explicit action and retain its original source/model/revision. Untouched displayed predictions are never confirmed CNVs. Historical overlays should be optional references rather than automatically inserted blocking drafts.

Use consistent colors and an always-visible compact legend. Prefer the familiar v5 meanings: green = human-confirmed CNV, orange = draft/unconfirmed footprint, cyan = historical manual reference, purple = unsure, gray = removed when shown. Color represents review state rather than whether every pixel was drawn from scratch. The selected region should be visibly emphasized.

## 4. Whole-image positive and negative annotation contract

The user's intended label is a complete en-face segmentation:

**Once an image is explicitly confirmed, the union of kept CNV footprints is CNV-positive, and every other assessable pixel is CNV-negative. Unsure/unreadable/excluded pixels remain ignored. No separate painting of ordinary background is required.**

Drawing a CNV therefore defines its positive region and the proposed background complement. Display this meaning clearly near the completion control. A stroke, a region-level Keep or an autosave is not proof that the rest of the image has already been inspected: persist intermediate work as Draft, and commit the whole-field negative coverage through one **Confirm entire image** action after the user has checked the entire field. Do not add repeated per-region background approvals.

Use these rules:

- **Positive completed image:** at least one kept nonempty CNV, whole image inspected, all editable drafts resolved, and explicit uncertainty/exclusions preserved. All other assessable pixels become background. Do not infer extra CNVs from suggestions the reviewer did not adopt.
- **No-CNV present:** selecting this checkbox visibly declares the intended annotation to be whole-image absence. Finalizing with Confirm entire image stores an empty positive mask and explicit whole-field negative coverage. This is a valuable negative training image and not an error or skipped case.
- The no-CNV state must not coexist with active CNV masks or unsure/unreadable/excluded areas if it claims the *entire image* has no CNVs. If incompatible annotations exist, explain the conflict and require their explicit resolution; do not silently erase them. Adding a CNV after selecting absence clears that contradictory absence selection, returns the image to Draft and retains undo history.
- An image whose CNV status cannot be determined is Unsure/deferred, not negative. Provide an accessible way to mark uncertain areas; do not force guesses solely to finish or reach the target.
- Save/autosave preserves partial work and the draft absence checkbox. It does not create confirmed whole-image background. Exported negative labels require a valid explicit whole-field confirmation.
- Any subsequent mask, category, uncertainty, exclusion or absence-state change invalidates that image's confirmation until reconfirmed. Merely navigating, zooming or changing overlays does not. Undo/Redo restores the relevant geometry and confirmation validity consistently.
- Empty masks, invalid coordinates and unresolved positive/uncertain overlaps must not silently enter training targets. Resolve overlaps explicitly or ignore conflicting pixels with an audit record.

Retain positive, reviewed-background and ignored masks separately, plus the completion revision. The application may show an implied-background preview while editing, but training eligibility must distinguish it from confirmed background.

## 5. Show the en-face footprint on the B-scan

Every displayed CNV region must have a matching B-scan overlay before and after confirmation, in its current display color. Selecting or editing a region must update both views immediately.

The CNV annotation is a two-dimensional en-face footprint in native `[B-scan, A-line]` coordinates. For the displayed row `b`, intersect each footprint with that row and shade its included A-line intervals as **translucent vertical bands across the displayed B-scan depth**. Add legible interval edges or a small top strip if helpful. Preserve the structural image underneath. Distinguish the selected region, and handle disconnected intervals and multiple lesions correctly.

This is lateral footprint context, not an axial lesion segmentation: do not invent a lesion top/bottom, fill an anatomical lesion volume, or claim that the whole shaded depth is diseased. Label the overlay appropriately. The B-scan image and displayed footprint must use the same native row/column geometry with no unexplained transpose, flip or scaling offset.

If no region intersects the current B-scan, show no CNV band there. No-CNV images have no positive bands. Optional historical/prediction overlays should obey their visibility switches in both panels and remain distinguishable from the editable annotation. Keep current row and cursor stable during painting and model/context toggles.

## 6. Progress toward 30 positive images

Show prominently:

- **Confirmed CNV images: N / 30**
- **Confirmed no-CNV images: M**
- Draft/deferred counts and current queue position.
- A compact per-animal count so the coverage is inspectable.

Count unique native acquisitions with valid v7 whole-field confirmation and at least one confirmed nonempty CNV, once each. Do not count lesions, B-scans, repeated confirmations, seeds, historical files, just-opened images or incomplete masks as additional images. A same-acquisition revision updates its existing record. Different repeat acquisitions remain separate images, but reports must identify the repeated session/tissue relationship and never equate them with independent animals or lesions.

When a counted image is edited into a draft, changed to no-CNV, or loses its final CNV, update the counter immediately and correctly after restart. Persist authoritative completion metadata; rebuild counts from it rather than trusting a GUI session counter. Historical labels do not automatically fill the 30 slots; explicit v7 review/confirmation is needed to count that acquisition.

At 30 confirmed positive images, save safely and show that the collection target has been reached with a summary and a natural stopping point. Allow later review/editing; do not lock the application or launch training automatically. Preserve negatives acquired along the way. Reaching 30 is a workflow milestone, not proof that the model will be accurate or that the sample is statistically sufficient.

## 7. Historical CNV evidence and previous models

Write a concise `MODEL_AND_LABEL_HISTORY.md` and a refreshed historical-label inventory so the next training task can reuse the real work without guessing its meaning. Preserve at least this context, refreshing live counts and hashes:

- **v1:** thickness-deficit/background-reference pilot on 17 TS267 acquisitions; 13 proposals and 0/7 historical manual locations matched within 75 micrometers.
- **v2:** integrated detection/review; 220 proposals and 7/7 location matches, with substantial false-suggestion burden.
- **v3:** stricter structural/shape heuristic; 29 proposals and 6/7 location matches. Location/component counts were sparse development evidence, not validated sensitivity or exact lesion identities.
- **v4/v5:** annotation/GUI improvements over unchanged v3 suggestions, not newly trained CNV detectors. V5 introduced actual OCTA and whole-field completion; its CNV editor is distinct from the retinal layer-boundary model/editor.
- **v5 labels at prompt preparation:** 15 saved TS267 acquisitions, 14 completed fields, 25 kept lesion entries, eight Unsure entries and one draft. D0 OS remained partial; D28 OS and D35 OS had no saved v5 file. The 25 entries include repeated visits and are not 25 independent biological lesions. The v6 audit excluded 34 conflicting positive/uncertain pixels on D0 OD. Re-audit instead of assuming these counts remain current.
- **v6:** nine independently trained compact 2D U-Nets: A/B/C times seeds 267/268/269. A uses structural OCT + actual OCTA (2 channels); B adds eight automatic thickness-availability maps and shadow (11); C adds eight numerical thickness maps (19).
- The v6 compact architecture used widths 16/32/64/128, a 256-channel bottleneck, GroupNorm and a mirrored decoder; masked BCE/Dice, native 256-pixel tiles and overlapping full-field inference. Training visits were D0/D7/D14/D28/D35/D42, validation D49, and development holdout D56/D98. Nine acquisitions supplied training pixels; all were TS267. Both eyes were grouped by visit. Thresholds/checkpoints were selected on validation.
- Across three seeds, mean holdout Dice was A 0.678, B 0.584 and C 0.733. C recovered all six holdout lesion entries each time but retained false suggestions and outline errors. These are repeatedly evaluated entries in the same animal, not independent new-animal validation. Good within-TS267 overlap does not settle the user's reported excessive detections elsewhere.
- V6 B/C inference is complete on 324 acquisitions across 11 animals, yielding 1,944 saved prediction sets. Inference on other animals is not validation. B thresholds vary by seed (0.7/0.1/0.8); C used 0.5 for all three. Scores are not calibrated biological probabilities.
- Current v6 review is an original-prediction rating/error workflow. Its Finish this review does **not** certify whole-field negative coverage. At the last check it held two saved acquisitions/nine region records, zero new explicit model ratings and zero finished new ratings reviews. Refresh these facts rather than importing stale report counts.

Inventory original `outputs/cnv_labels`, v3/v4/v5 region reviews and current v6 human review records, retaining exact scan/native source identity, source paths/hashes, revisions, origin, completion scope and ignored areas. Existing positive references span TS241, TS247, TS250, TS267, TS283, TS305, TS325, TS328 and TS336; they are useful context, not automatically complete-field labels or a sampling prerequisite.

Do not overwrite or bulk-relabel old annotations, infer negative pixels from absent files, or transfer masks across different repeat acquisitions without validated registration. Do not treat every historical region approval as a CNV; inspect category, decision, uncertainty and scope. V6 model ratings alone are not pixel masks. V6 original predictions are never human truth.

When a user explicitly revises an old footprint in v7, create a v7 revision with provenance, preserving the original. Build a clear acquisition-level precedence/supersession manifest for future export so an old and new annotation of the same image are not counted as two samples. Conflicting sources need an explicit rule or adjudication flag, not silent union. Any byte-preservation verification should be read-only and report actual coverage.

## 8. Storage, performance and data integrity

Suggested v7 layout: `review/regions/`, revision history, `queue/`, `logs/`, `verification/`, `reports/`, and documents/launchers at the root. Use versioned schemas, atomic writes, stale-writer detection and recoverable history. Keep authoritative geometry, classifications, whole-field/absence confirmation, masks, reviewer/source identity, exposure to suggestions/manual references, timestamps and focused review time. Synthetic verification records must live separately and never count as real annotations.

Activate the `octa` conda environment before running Python. Do not call the environment's Python executable without activation. Prefer the existing working Qt/runtime infrastructure.

Use only processed `.mat` volumes or validated cached exports; never reconstruct `.RAW`. Canonical depth zero is vitreous; derive/check orientation with the established detection/preparation functions and verify native alignment. Avoid slow per-B-scan HDF5 loops and transposing giant volumes. Reuse the all-cohort native providers where possible, load asynchronously and prefetch the next candidates with bounded memory. Prefetch must not create review decisions or advance counters. Save errors must preserve unsaved work and previous valid disk data.

No segmentation retraining, new cohort inference or upstream label modifications are needed merely to build this GUI. Missing cache/provider cases must receive a specific recoverable status and not be silently called negative. Document any narrowly necessary cache preparation separately.

## 9. Write `TRAINING_PLAN.md` for the next CNV detector

The model objective remains **complete en-face CNV footprints**, with fewer false detections far outside CNVs while retaining real lesions. The immediate next step is broader, consistent human supervision, especially varied backgrounds that currently trigger false positives. No benefit should be claimed before measurement.

Document this future sequence:

1. **Freeze and audit a versioned dataset after collection.** Combine eligible original/v5 evidence, applicable explicit v6 human masks and completed v7 fields with source precedence and duplicate checks. Partial historical records can contribute valid confirmed positives but not unmarked negatives. New completed v7 positives supply reviewed background outside CNV/ignored areas; confirmed no-CNV images supply whole-field negatives. Preserve uncertainty, conflicts and draft status. Do not label missing thickness as negative CNV or drop a confidently labeled lesion because its thickness is unavailable.
2. **Count acquisitions, animals and repeated lesions separately.** Thirty confirmed positive images is the collection milestone. Preserve all useful confirmed negative fields encountered. Roughly 10-15 diverse negative images is a useful provisional addition for false-positive control, not a requirement to block GUI completion, a mandated prevalence or a guarantee of sufficiency. Do not count multiple visits as independent lesions.
3. **Use animal-grouped development and assessment.** Keep each animal's eyes, visits, repeats, crops and augmentations in one fold/role. Set aside assessment animals before fitting/model selection or use animal-excluded development folds, depending on actual coverage. Never reserve TS267 as unseen CNV assessment while starting from a TS267-trained checkpoint. Labeling animals now does not require using every label in training. Repeatedly inspected assessment results become development feedback.
4. **Audit upstream exposure too.** The current thickness-producing ALL_LABELLED layer models have seen the existing cohort animals. Holding an animal out only from CNV fitting does not create end-to-end independence. Use animal-excluded upstream inputs or genuinely new animals for that stronger claim; otherwise report the restricted independence honestly. A truly unseen final test may require new data. Do not automatically choose final test animals using model performance.
5. **Keep inputs autonomous and aligned.** Use raw numerical structural OCT/OCTA, frozen automatic availability/shadow and automatic numerical thickness as appropriate. Do not feed manual footprints, human correction locations, human unreliability marks, GUI colors/text, source identity, eye/day IDs or target-derived distances to the model. Retain measurement NaNs; only the model tensor uses a neutral normalized fill paired with availability. Real OCTA remains a crop projection, not a layer-specific slab. Photoreceptor composite includes ONL; Full retina uses ILM to outer RPE edge.
6. **Run a bounded next comparison.** Keep an image-only baseline A and the promising thickness-assisted C recipe under matched animal splits/training budgets; preserve frozen v6 outputs as the reference model comparison. B or further availability/shadow ablations can be added if evidence warrants. Treat random initialization versus fine-tuning as an explicit experiment with checkpoint ancestry tracked. More architecture complexity is not the default remedy for sparse single-animal training.
7. **Target false positives explicitly.** Sample acquisitions across animals and include reviewed background/negative fields, particularly vessel, shadow, bright-feature and field-edge errors. Mine difficult negative patches only within human-confirmed negative coverage of development images; model-only guesses are not negative labels. Retain representative ordinary cases. Inspect full-field false-positive behavior and validation-selected detection thresholds, not just tile overlap. Do not pick thresholds using assessment labels or hide failures with arbitrary shape/lesion-count caps.
8. **Measure usefulness.** Primary comparisons include missed lesions and false CNV regions per completed image, with recall/precision tradeoffs, footprint Dice/IoU and border error on reviewed areas, count/area errors, negative-field behavior, model correction burden and focused review time. Prespecify one-to-one lesion matching and score ignored/empty cases explicitly. Report by animal, lesion stage and artifact context; account for clustering. Dataset sampling and developer-tuned examples do not estimate natural cohort prevalence without qualification.
9. **Train in documented rounds.** Freeze each dataset/model revision; never retrain after each stroke. Evaluate improvements as new animals/cases are added. If the target of 30 images is inadequate, use measured errors and learning curves to choose the next labels. If recurrent errors require axial relationships absent from en-face projections, test a B-scan-stack/2.5D extension later with suitable evidence. No new model is trained in this GUI task.

## 10. Verification and deliverables

Implement meaningful checks of:

- Non-WT, strictly post-D7 eligibility; parsed/missing/discrepant day labels; deterministic visit-aware randomization; numeric animal round-robin order; no duplicate acquisitions; stable restart/resume; pool exhaustion and negative/skip continuation past the first 30 candidates.
- Painting, closed-loop fill, erasing, separate lesions, Keep/Remove/Unsure, undo/redo and reopening saved revisions.
- No-CNV conflicts, adding a lesion after absence, draft versus confirmed background, exceptions/overlaps, and invalidation/reconfirmation after edits.
- Positive-image counting once per acquisition; multiple lesions not inflating progress; negatives not counting toward 30; edits decrementing correctly; synthetic/historical/browsed cases not counted; restart and target-reached behavior.
- Exact en-face-mask row to B-scan-A-line overlays, including columns 0/last, first/last rows, disconnected masks, no intersection, multiple regions, color/state changes, zooming and optional overlay visibility. Inspect real screenshots as well as testing geometry.
- Historical source precedence and provenance; native source/grid checks; no old-label/prediction writes; atomic save failure and stale writer handling.
- Real launch and loading on several animals, including a previously unreviewed acquisition and an existing reviewed one. Test synthetic edits only in isolated verification directories. Opening real examples for verification must not create human annotations.

Deliver:

1. `OPEN_OCTA_AUTO_CNV_V7.cmd` and a working standalone GUI.
2. Persistent queue/configuration/manifests plus a concise inventory/eligibility report explaining the 11-total/10-non-WT distinction.
3. `START_HERE.md` covering the exact gestures, No-CNV meaning, whole-image confirmation, B-scan footprint bands, target counting, resume workflow and storage.
4. `MODEL_AND_LABEL_HISTORY.md` plus refreshed historical-label inventory/provenance.
5. `TRAINING_PLAN.md` with the future plan above, adapted to verified data availability.
6. Verification results and real screenshots; a release completion record that clearly means software verification, not 30 human reviews completed.

Finish with the launch link, the number of eligible animals/acquisitions and the confirmed-positive/negative counts actually present. Do not manufacture a completed review set or train a model. Resolve routine implementation choices autonomously within this scope and report concrete limitations.
