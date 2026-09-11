# octa-seg_v2 — focused review and iterative improvement

Status: round_000 implemented 2026-09-10. See START_HERE.md for the focused reviewer, ten complete volumes, checks and feedback commands. This is a workflow/policy release using the existing model; new training awaits balanced explicit review evidence. All new code is isolated here under code/octa_seg_v2, following the user's request to keep all v2 work in this folder.

## Goal and starting point

Build a focused segmentation reviewer and a repeatable feedback-to-training loop around the current successful eight-boundary model. The user reviewed the two additional pilot volumes and described both as fantastic. Preserve the current positional model as the starting point; prioritize learning where measurements are unreliable and providing useful uncertain candidates in those areas.

The main interaction is marking a vertical strip of a B-scan as **unreliable for measurement**, across all boundaries in that strip. This should allow dashed candidate positions to remain available for inspection and correction. It is a different judgment from not being able to identify a particular boundary at all.

Deliver a usable first review release before requiring another labeling session. Review in short rounds, retrain from explicit feedback, compare with the previous round, and regenerate the same ten volumes. Target 20–30 minutes of review per round, with a 60-minute maximum. Keep CNV/vessel/ONH annotation and model development in its separate workstream.

Use `code/octa_seg_v2` for new model/workflow implementation and `outputs/octa-seg/octa-seg_v2` for its artifacts. Preserve v1, the six-volume pilot, original annotations, and the separate octa-thick work. Read the repository instructions and current source before implementing; activate the octa environment for Python work.

## 1. Focused segmentation GUI

Use the existing native B-scan editor, navigation, provenance-aware label writer, and pilot strip-selection interaction. Provide a dedicated launcher and a focused layout: large B-scan, compact en-face navigator, optional neighboring slices, boundary selection, and a short action panel. Move detailed probabilities, metrics, and provenance into an expandable inspection panel. Retain free browsing, bookmarks, undo/redo, autosave, and previous/current model comparison.

CNV/vessel/ONH overlays are read-only context in this GUI. Load saved annotations on scan opening and offer Refresh overlays. The other GUI does not need to run simultaneously or follow the same location. Region classification and mask painting belong in that separate GUI.

### Primary review actions

1. **Unreliable region:** drag over an A-line interval, covering the full displayed depth and all eight boundaries. Immediately withhold measurements there and show available candidates as uncertain. Save an explicit regional reliability judgment for training.
2. **Clear regional mark:** return those columns to their previous applicable judgments; clearing does not assert that the image is reliable.
3. **Approve shown measurements:** explicitly affirm the visible, finite solid segments in the selected range. Record the particular boundaries and coordinates approved. This action does not approve hidden boundaries or dashed candidates.
4. **Correct / approve candidate:** draw a selected boundary or explicitly approve a displayed candidate for future position training. A correction can remain uncertain until the user affirms it as measurable.
5. **Not traceable:** retain a separate per-boundary action that removes both measurement and candidate locally.
6. **Exclude unusable image:** retain the stronger existing image-exclusion action for stretches where neither measurements nor candidates should be used.

The default regional tool is Unreliable region. In its explicit mode, dragging paints the full-depth strip; the GUI intercepts that gesture before boundary-editing handlers. Keep established gesture meanings in their existing modes and show the active mode clearly. Support marking the whole B-scan using the same interval mechanism.

Regional judgments supply a default for all boundaries, with a later explicit per-boundary review able to establish an exception. For example, after marking an obscured strip unreliable, the user can affirm an ILM segment that remains visible. Explicit not-traceable marks and hard image exclusions continue to prohibit automatic continuations. Undo and later edits must invalidate superseded positional approvals.

The pilot's Good/Bad/Unsure ratings remain a separate assessment layer. Do not reinterpret those historical ratings, or whole-volume praise, as eight boundary-reliability labels. New training-oriented regional marks must come from the explicit Unreliable region action.

## 2. V2 reporting and candidate policy

### ILM is a solid working boundary

Per the user's instruction, promote the existing neural ILM position to the default solid, editable working segmentation in v2, bypassing v1's missing-positive-calibration withholding for ILM. Use the current model's ILM; do not substitute an older model silently.

Finite, in-image, correctly ordered ILM positions can contribute to v2 experimental RNFL, total-retina, and inner-retina thickness when the other endpoint is reportable. Regional unreliability, explicit boundary denials, image exclusions, and invalid geometry still apply. An explicitly unreliable ILM is handled consistently with other unreliable boundaries; solid is its default rather than an exemption from review.

Record the origin as a versioned working-policy decision, such as `ilm_working_default`. Keep the original model scores and reasons. This display/reporting policy does not create positive training labels or establish probability calibration. Human approval and manual correction remain separately identifiable.

### Allow substantially more uncertain candidates

Keep measurements and candidates in separate arrays. Relax candidate generation, not the definition of a measured boundary:

- Prefer a registered contextual estimate when v1's context checks succeed.
- Otherwise allow the current neural boundary proposal as a dashed review candidate when the position is finite, in the retinal crop, and noncrossing with the available neighboring boundaries.
- The fallback can cover long uncertain stretches, including a full-width uncertain region, without requiring v1's two lateral anchors, both adjacent slices, or 128-column gap limit. Mark its source as `neural_proposal`; do not describe it as independently corroborated by neighboring slices.
- Preserve gaps through explicit or automatic not-traceable regions and hard exclusions. Invalid positions do not become candidates. Do not smooth away CNV deformation, bridge forbidden gaps, or reuse generated candidates as evidence for later candidates.
- Retain spike/entropy warnings on candidates so suspicious guesses remain easy to find. A dashed line is a proposal for review, not a reliable measurement.

The normal v1 reporting thresholds for the other boundaries remain the initial baseline. Regional feedback subsequently teaches the existing reliability output to withhold measurements in problematic columns. Do not lower thresholds simply to increase solid coverage.

## 3. Feedback and training loop

Add a versioned GUI-written regional-reliability record containing scan identity, native B-scan/A-line interval, action, model/round identity, timestamp, revision/history, and optional reason. Preserve it independently of individual boundary strokes. The importer resolves regional defaults and explicit per-boundary exceptions into training masks with recorded provenance.

- An unreliable-region mark supplies a negative **reliability** target for the affected boundaries. It does not supply a negative traceability target or a boundary position.
- Missing marks remain unknown. Clearing a mark restores the underlying state rather than creating affirmative evidence.
- Explicit approval of visible measurements supplies affirmative state evidence for the recorded boundaries. Position training additionally requires an exact stroke or an explicit position-approval event tied to unchanged coordinates.
- Do not train on automatic tapers, ordering displacement, inherited default flags, unknown legacy stroke spans, unreviewed candidates, or quality-pilot Good/Bad ratings.
- A later denial, displacement, changed position, or rejection revokes prior positional approval. Existing labels remain read-only; derived datasets are frozen snapshots.

Reuse the existing position and traceability/reliability architecture initially. Regional reliability targets are expanded across the affected boundaries, so broad obscured strips can teach the existing reliability head without requiring a new region-classification network. Balance training by animal, reviewed region, boundary, and affirmative/negative evidence; a wide bad strip must not overwhelm all good examples simply through its number of A-lines.

Deliver `round_000` with the current positional model, the new GUI, ILM policy, and expanded candidate policy. Reuse compatible neural predictions and save checkpoint references/hashes. Incorporate any newly eligible explicit feedback only through an audited dataset snapshot. If there is no new training evidence, identify this initial release as a workflow/policy update rather than claiming a newly learned improvement.

For each subsequent round:

1. Freeze new feedback and its data roles.
2. Update reliability/traceability with the position branch frozen first.
3. Fine-tune positions only when eligible corrections/approvals exist; compare against the frozen-position alternative and keep manual-only versus approved-position sensitivity results separate.
4. Compare candidate usefulness, good-boundary retention, inappropriate reporting, and positional error on assessment evidence withheld from that round's fitting.
5. Export the same ten volumes under an immutable round directory and show the previous/current difference in the GUI.

Include good-signal approvals and a small random assessment subset alongside difficult strips. Keep assessment feedback out of the model/calibration being assessed. Separate training, calibration, and evaluation by animal for animal-excluded claims, including checkpoint ancestry. Assessments of a previously all-label-trained model on seen animals are development/workflow results. Determine seen/unseen status from actual eligible training and checkpoint ancestry, not merely membership in an annotation inventory.

Keep runs resumable and separate GPU training/inference from CPU/Qt work as required by this workstation. Train in an explicit batch between review rounds, not after every click. If feedback lacks adequate positive/negative support, report that limitation and preserve the working provider while collecting the missing examples.

## 4. Ten complete volumes

Run all ten complete native volumes in the first v2 output. Reusing unchanged image/position caches is allowed; recompute v2 states, candidates, measurements, and reports under its documented policies. Preserve all 512 B-scans per scan.

### Six already reviewed volumes

| Scan ID | User's full-volume review |
|---|---|
| TS165_OS_2025-04-29_WT_s02_121711 | Decent; some solid segments should be uncertain/dashed. |
| TS247_OD_2024-11-06_D21_s03_104157 | Great, almost perfect, especially with good signal. |
| TS283_OD_2025-01-29_D7_s02_123712 | Really solid; a few misplaced labels near ONH. |
| TS325_OD_2026-05-26_6mo_s01_112940 | OK, but needs more uncertain guesses. |
| TS328_OD_2026-04-09_beforelaser_s01_130813 | Fantastic, per the user's review of the additional tests. |
| TS336_OD_2026-05-22_D21_s05_114507 | Fantastic, per the user's review of the additional tests. |

### Four additional randomly selected CNV volumes

Selection was computed before viewing new segmentation outputs on 2026-09-10. Eligible scans had an existing processed source, a post-laser scan identity, and a reviewed nonempty CNV annotation; the original six were excluded. There were 16 eligible scans across seven animals. With Python `random.Random(20260910)`, sample four animals uniformly without replacement from the sorted animal list, then one scan uniformly from each animal's sorted eligible list. This balances animal representation rather than weighting animals by their number of scans.

- TS241_OD_2024-09-25_D42_s03_111600
- TS247_OD_2024-10-30_D14_s05_105423
- TS250_OS_2026-03-23_D27_s03_115357
- TS336_OD_2026-05-22_D21_s03_113534

Freeze these identities and record the selection pool, seed, and rationale in the implementation manifest. Do not replace a selected scan because its segmentation looks poor. They are additional CNV acquisitions, not necessarily unseen training animals or volumes.

Use current saved CNV/vessel/ONH annotations with their review/provenance flags. Saved manual work and reviewed-empty vessel masks take priority. Where vessel work is absent, generate a proposal with the existing vessel baseline/shape-gate recipe and preserve its automatic provenance; do not write a human label file. Missing CNV/ONH annotations remain unknown.

The pilot's two new scans had no vessel masks, unlike the original four. Account for this when comparing coverage: save a v1-policy baseline using the same footprint inputs as v2, so an effect of added vessel context is not mistaken for a learned change. Preserve the original pilot separately as historical evidence.

## 5. Measurements, compatibility, and acceptance

Reuse the pilot's entropy, spike/jump, signal, thickness-distribution, and available-ONH-distance reports across all ten volumes. Report solid, dashed, and withheld fractions by boundary; false solid reporting in explicitly unreliable regions; retention in approved good regions; candidate approval/correction rates; and review time. Region-level Good/Bad judgments can validate warning metrics but do not establish per-boundary accuracy.

Compare positions/thickness where eligible assessment traces exist. Keep mean/median/SD/IQR, local roughness, invalid/crossing fractions, and finite coverage together. Interpret CNV deformation and eccentricity as context rather than tuning every volume toward a common average. Use existing ONH marks only; identify partial-edge distances and leave missing distances unknown.

Retain the existing meanings and shapes of `reported_positions`, `uncertain_estimates`, `state`, `probabilities`, `raw_position_branch`, and thickness arrays. Add explicit candidate-source, policy-reason, regional-feedback, and round provenance fields. Compatibility `surfaces` contains reported positions only. Shadowed thickness and thickness with an unreportable endpoint remain NaN. Make the ILM working-policy origin available to the separate octa-thick reader without rewriting its existing results.

Required checks:

- Regional marking and undo affect exactly the selected native columns and all intended boundaries; later explicit exceptions resolve correctly.
- Regional unreliability permits eligible candidates but creates no position or not-traceable targets; hard exclusions and denials prohibit both measurements and candidates.
- ILM is solid/reportable by default under the working policy; denied, unreliable, invalid, and excluded ILM remains correctly handled. The policy alone never enters human ground truth.
- Broad uncertain-region fallback works without lateral anchors; candidate provenance is retained; no forbidden gaps are bridged.
- Save/reopen, stale-approval invalidation, conflict/history handling, and quality-rating separation work through real GUI interactions.
- Orientation, crop offsets, native overlay alignment, NaN thickness propagation, and the ten-volume manifest are verified. Original annotations and completed versions remain unchanged.
- Comparisons separate policy changes, footprint-input changes, and learned changes. Checkpoint/data roles are audited before making generalization claims.

Deliver `START_HERE.md`, the focused GUI launcher, the fixed ten-volume manifest, complete exports, review queue, training/resume commands, round comparison reports, and tests. The first success criterion is a comfortable review workflow that makes dubious measurements easy to mark and useful uncertain proposals easy to correct. Further learning is judged by fewer inappropriate solid measurements, retained good segmentation, more useful candidates, and less review effort—not by line coverage alone.
