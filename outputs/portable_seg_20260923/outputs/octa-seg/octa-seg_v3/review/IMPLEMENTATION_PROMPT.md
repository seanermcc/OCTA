# Implement the new octa-seg_v3 review GUI

Implement this specification completely, including migration, documentation and verification. This is an implementation request, not a request for another plan. Use the revised `TRAINING_PLAN.md` beside this prompt as the intended annotation and training contract. Do not train a new model during this GUI task.

## Goal and project context

Build the ongoing review GUI for correcting the B-scan segmentations that are most wrong, particularly at CNV centers, margins and transitions. The reviewer starts from automatic boundaries, corrects the same working segmentation, marks uncertain or untraceable portions, and confirms the entire B-scan once. Independent reviewers must be able to review common cases, and the lead must easily reopen their own work without duplicating it.

Project: `G:\OCT_TreeShrew\octa`.
V3 release: `G:\OCT_TreeShrew\octa\outputs\octa-seg\octa-seg_v3`.
New GUI and supporting materials: `<v3>\review`.
Archived previous GUI and supporting materials: `<v3>\old_review`.

Read the project `AGENTS.md`, `README.md`, `PIPELINE.md`, the `octa-layer-segmentation` skill, and the v1/v2/v3 guides and relevant code before editing. The user explicitly changes the older drawn-only training convention: under the NEW whole-B-scan confirmation contract, unchanged automatic positions explicitly confirmed by a human are approved positional training evidence. They are not manual strokes. Historical generic acceptance/completion flags do not gain this meaning retroactively.

Activate the `octa` conda environment; do not call its Python executable without activation. Use processed-volume/canonical caches with verified orientation and native coordinates. Do not reconstruct RAW files, modify original acquisitions, tune segmentation priors, retrain models, or overwrite frozen prediction releases. Real human labels are written only through the GUI and its established annotation writer. Synthetic GUI tests must be isolated and excluded from training.

## 1. Archive and establish the new home

1. Inventory the old v3 GUI, launchers, guides, training plan, configuration/catalog files, dependency records, verification records, reviewer storage and queues. Check for a running GUI or active writer before migration; never move files out from under it.
2. Create a recoverable archive in `old_review` of the old GUI and the supplementary material needed to understand and restore it. Include a dated manifest with hashes, original paths, dependency versions/locations, and restore instructions. Preserve referenced small runtime dependencies where needed for reproducibility; reference large frozen volumes/checkpoints in place rather than duplicating them. Exclude the new `review` and archive directory from recursive snapshotting. Preserve any existing archive rather than overwriting it.
3. Keep existing reviewer labels, journals, revisions and shared queues intact. Make the migration read-only with respect to historical originals, and record exactly where old records remain accessible. A GUI-mediated migration/adoption into new-format records is allowed with provenance and backups; do not synthesize historical human decisions in a script. Old reviews must appear in the new saved-review browser even before adoption.
4. Put the replacement code, launchers, current guide, implementation notes, revised training plan, verification outputs and new review storage under `review`. Existing large source datasets remain referenced in place. Preserve these specification documents.
5. Audit path assumptions. Existing `common.py` derives roots from its directory depth; launchers contain relative import paths and journals/queues contain provider paths. Simply moving files one directory deeper is insufficient. Use explicit validated root resolution and verify launching from arbitrary working directories and paths with spaces.
6. Update the familiar top-level v3 launchers to open the new GUI after successful verification. Make the current top-level documentation clearly point to `review`. Archive the original training plan and replace its active entry point with the revised plan or a clear link. Do not leave competing active training contracts.
7. Version event semantics. Old stroke journals must replay with the old ordering rules, and historical completion flags must remain historical metadata. New ordering/confirmation behavior must not silently change old saved positions or manufacture approvals.

## 2. Drawing must take priority over neighboring automatic boundaries

The current `feedback.resolve` uses top-to-bottom `enforce_order`, which can push a newly drawn outer boundary downward because an inner boundary is misplaced. Replace this for NEW edits with ordering anchored on the active boundary:

- Keep the exact drawn boundary position, within the actual image depth limits.
- Move conflicting shallower neighbors upward and deeper neighbors downward, recursively through all affected boundaries, maintaining a minimal noncrossing separation without enforcing healthy layer thicknesses.
- Only move neighbors where the edit/join causes a collision. Do not globally reshape the B-scan or alter unrelated columns. Handle NaNs, hidden boundaries, excluded columns and anatomical gaps explicitly; never invent a missing boundary solely to satisfy ordering.
- Image limits can make a complete ordered stack impossible. Do not silently clamp the active stroke to an incorrect neighbor or pretend invalid geometry is reliable. Preserve the intended edit, visibly identify unresolved geometry, and require correction or an appropriate no-trace/exclusion judgment before completion.
- A deliberately selected boundary stays selected while drawing near another curve. The existing nearest-boundary feature must not hijack a PR correction because the INL is nearby. Keep nearest selection optional and its active state clear.
- Highlight moved neighbors so the reviewer can inspect them. Track direct drawing, joins and displacement internally. Software movement alone is not positive human evidence; whole-B-scan confirmation can explicitly approve the final positions, including inspected joins and displaced neighbors.
- One undo restores the complete stroke and all resulting neighbor movements, states and completion validity; redo restores the same result. Reopening must reproduce it exactly.

## 3. Simplify boundary tools on the RIGHT

Place clear, persistent tools immediately below the right-side boundary selector:

- Normal drawing: left-click/drag corrects the selected boundary in the working segmentation.
- **Unreliable**: a checkable on/off marking button. While selected, an ordinary right-drag marks only the selected boundary's horizontal span unreliable, exactly like Alt+right-drag, without moving the curve. Retain a dashed uncertain position.
- **Not traceable**: a separate checkable on/off marking button. While selected, an ordinary right-drag marks only that boundary's span not traceable, exactly like Shift+right-drag. Show a gap.

The two marking tools are mutually exclusive; clicking the active tool turns it off. Changing tools alone must not change saved annotations. Turning a tool off does not erase marks already made. Show the active mode and gesture beside the tools. Preserve original modifier shortcuts, including Ctrl+Alt/Ctrl+Shift restoration. Explicit modifiers should take precedence over a latched mode. With neither tool selected, right-drag retains the existing whole-column image-exclusion behavior. Ensure pan/zoom gestures still work.

Keep a distinct, understandable option for drawing an uncertain best-guess position (the existing Draw as unreliable behavior). Do not confuse drawing uncertain coordinates with marking existing coordinates uncertain. Provide an easy clear-mark interaction and undo; clearing a judgment means unknown unless a positive judgment is explicitly made. Reliability restoration must not erase not-traceable or anatomical-absence decisions.

Hide A-line start/stop boxes and technical interval notation from the normal interface. Direct dragging defines the span and displays a highlight. Numerical selection may remain under Advanced. Boundary-specific tools act on the selected boundary; whole-image exclusion must be clearly labeled as affecting every boundary.

Retain anatomical absence/interruption as an optional advanced judgment, distinct from poor visibility. Move data-use roles, sampling tags, diagnostics, blind-review options, and specialized reset/exclusion operations into compact collapsible sections. Preserve their recorded meanings.

## 4. One primary action: Confirm entire B-scan

Replace the old metadata-only completion checkbox and the confusing range/candidate approval workflow with one prominent **Confirm entire B-scan** action. The review scope is every required boundary across the entire native B-scan width; selection span, active boundary, and display filters must not silently narrow it.

The reviewer is affirming:

> I reviewed all boundaries across this B-scan. The remaining positions are acceptable except where I explicitly marked uncertainty, lack of traceability, or unusable image.

Use all-boundary display for final inspection. If the user was viewing only one boundary or hiding others, restore a clear all-boundary review view before the final confirmation can attest to unseen content. Do not add eight independent approval clicks or mandatory per-boundary checklists. No partial-confirmation action is needed. Autosaved work remains Draft until this action succeeds.

The resulting record MUST:

1. Approve unchanged automatic portions inspected by the reviewer as well as corrected portions. Model uncertainty alone must not prevent a reviewer from approving a defensible displayed position.
2. Preserve every explicit unreliable, not-traceable, anatomical-absence and unusable-image mark. Whole-B-scan confirmation must not convert these exceptions into reliable positional targets or fill their gaps.
3. Approve the final positions of software-moved neighbors and joins when inspected and confirmed, while preserving their original provenance. They remain software-derived followed by human approval, not invented manual strokes.
4. Identify unexplained missing boundaries and invalid geometry before completion, with an actionable on-image indication. Explicitly marked uncertainty/no-trace regions are valid completed outcomes; no invented curve is required. Display checkboxes must never imply anatomical absence or completeness.
5. Save a versioned whole-B-scan confirmation event and a stable final segmentation/state snapshot, including reviewer, scan, native coordinates, boundary set, source/model identity, annotation revision, applicable exclusions, timestamp and data role.
6. Bind completion to that exact geometry/state revision. Any later positional edit, state mark, exclusion change or adopted prediction change returns it to Draft/Needs reconfirmation. Navigation, zoom, notes and sharing tags do not invalidate geometric confirmation. Undo/redo must preserve revision validity correctly, never leave changed geometry marked complete.

Keep explicit masks for directly drawn positions, joined positions, displaced positions, approved final coordinates and each state judgment. A confirmed record can contain reliable targets, ambiguous candidates and no-trace regions. Confirmed means the review is complete, not that every boundary is reliable everywhere.

Implement and verify the training-target reader/export contract alongside the GUI. Explicitly confirmed unchanged and software-adjusted final positions must reach the approved positional target mask, subject to uncertainty, exclusion, geometry, shadow and data-role policies. Do not let old drawn-only masks silently discard them, and do not export every numerical position merely because the file is confirmed. Drafts are resumable records, not whole-B-scan-approved examples.

Put the following prominently in the RIGHT-side key, in bold:

**Confirm entire B-scan approves the final segmentation, including unchanged automatic curves. Your unreliable and not-traceable marks remain exceptions.**

Explain directly underneath that this confirms every boundary across the B-scan, and that uncertain/untraceable areas are useful training judgments without becoming reliable positional targets.

## 5. Navigator and saved-review browser

Provide a persistent, high-contrast yellow horizontal line on the en-face navigator for EVERY B-scan on which the current reviewer has saved boundary review work. It must survive navigation, app restart, overlay refresh, and switching between en-face and thickness maps. A mere hover, opening a B-scan or adding a sampling tag is not a boundary review.

- Use solid yellow for confirmed reviews and dashed yellow for saved drafts/legacy unconfirmed work, with a small legend. Give the current B-scan a distinct high-contrast indicator so it remains identifiable over a yellow line. A separate bookmark marker may identify selected-but-unreviewed cases.
- Optionally emphasize exact edited/marked spans along the review line while keeping the full-width line visible. Show native B-scan number and review status on hover. Clicking the line opens the saved record at its correct native coordinates.
- Implement a conspicuous **My saved reviews** action available during ordinary browsing. It opens a persistent searchable list with animal/scan, B-scan, Draft/Confirmed/Needs reconfirmation/Legacy status, last review time, bookmark/share flag and notes preview. Filter by volume, status, CNV/ONH tags and flagged/shared cases; support deterministic order, resume-last and next unfinished/unreviewed navigation.
- The lead can reopen their own final segmentation and state marks, move through saved cases using Previous/Next saved review, and revise the same case without creating accidental duplicates. Warn inline that a case already has saved work; do not repeatedly interrupt deliberate re-review with modal confirmations.
- Show counts that distinguish saved, confirmed, remaining assigned cases and all available B-scans. Do not treat merely browsing as reviewing or claim a whole volume is reviewed after one slice.
- Provide an explicit discussion mode/list for displaying the lead's saved work with colleagues. This is separate from independent annotation: their own reviewer accounts/assignments still start from the frozen automatic source and never preload the lead's corrections. Opening another person's review for discussion is read-only by default and cannot change ownership. Record exposure where needed for later agreement analysis.
- Load compatible historical v3 records into this browser with their real status. The old completed checkbox alone must not label them confirmed under the new contract. Permit the reviewer to inspect and explicitly confirm/adopt them through the new GUI, preserving the original record and provenance.

## 6. Hideable review queue toolbar

Normal browsing retains a compact volume selector, B-scan navigation, save status and My saved reviews. Hide the secondary Free browsing/queue toolbar by default; provide a clear Review lists/Show review toolbar toggle and remember the preference.

Keep shared/flagged queues and export capability. Show the toolbar when opening a queue, label navigation as Previous/Next selected B-scan (or saved review), and show which list is active. Hide/disable meaningless controls when no queue exists. Distinguish Previous/Next B-scan from jumping between selected cases across volumes. Do not auto-advance past an unsaved or failed confirmation.

## 7. Future segmentation releases and overlays

Create a common provider interface/manifest for retinal surfaces and en-face CNV, vessel and ONH masks. Include source scan identity, geometry/orientation/crop/spacing, surface or mask definitions, prediction version/checkpoint identity, completion marker, state availability and provenance. Drive supported boundary lists/order/thickness endpoints from validated definitions rather than scattering hard-coded eight-boundary and 512-column assumptions. Preserve this dataset's eight-boundary semantics; never map a differently defined future boundary by index alone.

- Discover completed compatible releases and load fresh vessel/ONH/CNV context without rewriting the GUI each time. Provide adapters for existing formats, including a real automatic ONH proposal path as well as the existing vessel path. Never assume another ongoing task's output schema: inspect available outputs or document a precise integration contract if they are not ready.
- Automatically refresh compatible context overlays on reopening/returning to the app and through a manual Refresh action. Debounce filesystem changes, reject incomplete writes, and show a concise version/source indicator. Respect saved human masks and reviewed absence/drafts before automatic proposals.
- Preserve human corrections and saved final reviews. New layer predictions can start unreviewed cases; existing cases remain bound to their saved source/revision until explicitly adopting a new baseline. If adoption is offered, show changes, preserve the previous result and human evidence, and invalidate completion where required.
- Assigned independent-review queues freeze source versions. Visual overlay refresh must not silently change frozen model inputs, starting predictions or review assignments. Track contextual overlay versions/exposure separately from inference inputs.
- Geometry/anatomy mismatches must produce a useful explanation, not a guessed transpose, index shift or fallback presented as current. Missing optional overlays must not prevent layer review. Only explicitly compatible releases may load seamlessly.
- Retain original predictions and full history behind the scenes. The reviewer edits one working segmentation. Optional comparison/history is acceptable outside the primary workflow.

## 8. Revised training plan

Finalize the accompanying revised plan against the implementation. Make the whole-B-scan confirmation contract and all six resulting-record requirements above explicit. Highlight this sentence prominently:

**An unchanged automatic curve that a reviewer explicitly confirms as part of the entire B-scan is approved positional training evidence; redrawing an already-correct curve is not required.**

Preserve unreliable versus not traceable, uncertainty during training, reviewer identity/disagreement, original predictions/history, appropriate geometry/exclusion/shadow masks and animal-separated development/assessment. Do not require a separate candidate-approval workflow or insist that only manual strokes can be used after a valid new confirmation. Explain how approved unchanged/moved/joined coordinates enter training without being called hand-drawn. Historical flags are not retroactive approval. Do not promise calibrated uncertainty from a small shared review set.

Retain the existing 120-unique-B-scan starting budget and role separation as a provisional collection plan, not a completed dataset or guaranteed sample size. Focus development selection on CNV failures while retaining readable controls and distinct lesions/animals. Keep annotation, eventual training and scientific validation separate. This task implements the collection/target contract, not model fitting.

## 9. Verification and delivery

Add meaningful tests for the changed behavior, with synthetic GUI-written records only in the test area. Exercise actual Qt mouse/button/key paths, not only direct method calls. Cover:

- Drawing PR upward through misplaced INL boundaries, deeper edits, multi-neighbor cascades, missing numerical proposals, depth limits, active-boundary selection, locality, undo/redo and exact reopen behavior.
- Separate latched unreliable/not-traceable tools, original modifiers, restoration semantics, no labels from toggling tools, and protection of explicit exceptions during full confirmation.
- Full-width/all-boundary scope independent of selected span and display state; unchanged/drawn/moved/joined positions reaching their correct approved target masks; ambiguous/no-trace/excluded positions withheld appropriately; informative unresolved-gap handling.
- Draft versus confirmed records; edit invalidation, undo/reconfirm behavior, stable snapshots, autosave, stale-writer protection and interrupted saves.
- Persistent yellow review lines, accurate native coordinates, restart/refresh persistence, saved-review filters/navigation, duplicate avoidance and historical-record status.
- Independent reviewer isolation, frozen shared queues, lead discussion mode and original annotation bytes unchanged.
- Provider updates and missing/incompatible/partially written overlays, automatic ONH integration or an exercised fixture adapter, preserved approved results, and new launch/archive path correctness.
- Read-only loading and visual inspection of representative real CNV center/margin, ONH/shadow and clear-tissue cases; no manufactured real labels. Confirm that controls fit the actual desktop, the bold right-side key is readable, and both marking buttons and yellow lines are visible.

Document executed results and any unavailable future-provider integration honestly. Do not call an offscreen rendering check proof of an interactively visible window. Verify the old archive can be restored and the familiar launcher opens the replacement. Summarize changed behavior, how to launch, where old/saved work lives, and any actual limitations. Do not stop at a mockup or partially wired buttons.
