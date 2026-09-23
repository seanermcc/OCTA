# Implementation and verification

## September 22, 2026 — final CNV context

`cnv_context.py` adapts the final v9 dataset and live final corrections read-only.
`Navigator` renders a pink native-pixel outline with 30/255 alpha fill; `Editor`
projects each current CNV row through the displayed B-scan depth at 30/255 alpha,
with pink lateral borders. Source precedence and refresh are documented in
PROVIDERS.md. Layer inference, manual annotations and training policy are unchanged.

Executed `verification/check_final_cnv_context.py` in the activated octa environment:
all 324 acquisition masks validated (203 confirmed positive, 105 confirmed negative,
14 pending, two poor-image exclusions). In-memory checks exercised draft/absence
priority over accepted targets, uncertainty exclusion and incompatible-grid rejection.
Offscreen Qt checks covered every A-line at three depths across six navigation steps,
including rows outside a lesion, plus the en-face fill/edge alpha. A real read-only
window loaded TS169 OD D35 s01 at native B-scan 156, with exact mask-row equality.
All 16 existing lesion unit tests passed. No human annotations were written.
Results and inspected screenshots are in `verification/final_cnv_context/`.

## September 17, 2026 — manual lesion tools and compact help

The active GUI now adds three manual targets without changing the existing eight-boundary model, layer ordering or thickness policy:

* `CNV region`: a full-depth column-span mask, beside `CNV edge` below `Draw as unreliable`.
* `CNV edge`: an independent, optionally discontinuous depth trace sharing that row, with an `i` explaining region versus edge. Ctrl+drag erases. It has no taper or ordering interaction with retinal boundaries; explicit uncertainty and no-trace judgments remain independent.
* `Hyper_Ref`: a pixel mask on the following row, with a native-pixel brush-size dial, numeric diameter and an `Erase` toggle (keyboard E) shared by all annotation types. Stroke rasterization is continuous and round in image coordinates; zoom/stretch only changes its display.

`i` toggles hide/show the drawing explanation, CNV-region/edge comparison, full-confirmation explanation and thickness-coverage explanation. The coverage button sits directly beside the percentage. **All boundaries**, below RPE and above the marking tools, toggles the eight retinal curves (including their uncertainty/error indicators) and the manual CNV region/edge/Hyper_Ref overlays without writing annotation. Partial checkbox selections synchronize its SOME state; confirmation first restores hidden curves for inspection. Selecting a retinal boundary or pressing 1–8 exits the lesion tools. Lesion overlay visibility is under Advanced and must be restored for final confirmation.

All annotation writes still go through `label_gui.Editor.record_event` and its atomic journal writer. `lesions.py` is a read-only replay/target module; `lesion_tools.py` only collects gestures and calls the editor. Journals keep native canonical edge/stroke coordinates, brush sizes, region edits, definition identity, confirmation snapshots and history. New lesion-only drafts do not manufacture eight-layer compatibility labels. Autosave, undo/redo, navigation, read-only discussion and source identity use the existing mechanisms.

The subsequent layout correction places the CNV pair together and adds the all-boundaries display toggle. CNV-region selection clears the latched uncertainty tools and unreliable drawing mode, not their saved annotations. Qt tests explicitly draw regions with each previous marking tool selected and verify unchanged traceability/reliability arrays, no accidental image exclusion and no journal event from selecting the tool. The boundary-toggle checks cover all/none/partial display, retained CNV overlays, unchanged approval, and confirmation restoring the inspection view. The latest runs fingerprinted 663 existing annotation/metadata files with no changes; the 637-file count below belongs to the initial update.

Whole-layer confirmation remains compatible with older records. New GUI confirmations additionally carry `cnv-lesion-review-1`, the tentative `cnv-lesion-tentative-1` definition text, an exact compressed snapshot and digest. Old confirmations without this additional contract remain layer-only. New definition entries must be appended to the version registry; historical definitions must not be edited in place. Mixed definition versions within a case require an explicit future migration workflow. No anatomy is silently changed when terminology changes.

`CNV region` is manual supervision, not an automatic footprint or an exclusion. Erasing it retains edge/paint data. CNV edge is independent of that region; outside edge strokes are accepted without a warning and remain eligible as explicit positive targets. Hyper_Ref outside the region is an overridable warning; acknowledged painted positives remain known while unpainted outside pixels do not become background targets. Within a confirmed usable region, unpainted Hyper_Ref is negative, including a completely empty mask. Drafts, earlier layer-only reviews, synthetic/practice records and the wrong data role have no approved lesion targets. Exclusion/shadow guards remain. Export format `octa-reviewed-targets-2` adds separate lesion arrays and known/valid masks plus crop geometry and definition provenance; it does not fit a model. Confirmed geometry revision comes from the actual confirmation event, even after later metadata-only events.

### Confirmation warning override

New GUI confirmations carry `review_policy: review-warnings-1` and `acknowledged_warnings`, containing exact half-open unresolved-boundary and outside-Hyper_Ref spans. CNV edge containment is not a warning. The reader validates acknowledgment against replay, preserving the strict validation of older confirmations without this policy. Snapshot/digest, source, identity, scope, revision and approved-mask checks remain mandatory. The GUI asks “Are you sure segmentation is fully complete?” only when review warnings exist; No/close makes no annotation change, and Yes records completion with the warning provenance. Invalid retinal positions remain invalid and cannot enter approved positional training targets. No judgments are automatically rewritten as unreliable or untraceable. The export manifest preserves the policy and acknowledged warnings for audit.

Unresolved boundary spans use separate bright red (#ff3030) ruler lanes at the top of the image, including single-A-line spans; hover identifies the boundary. Warning/error status text uses the same color. Confirmed-with-warnings status is retained on reopen. Hidden overlays still require inspection after being revealed. Read-only mode, missing data, storage failure and stale-writer/identity/replay conflicts cannot be bypassed.

Warning-update verification passed all 21 existing and 10 lesion unit checks plus both offscreen GUI suites, including popup acceptance/cancellation and save/reopen. Both runs fingerprinted 819 existing annotation/metadata files and found no changes. Results are in `verification/20260917_220617` and `verification/lesions_20260917_220442`; the latter includes the red-bar and popup screenshots. Earlier counts below describe earlier updates.

Verification commands (the launcher activates `octa`):

```text
VERIFY_V3.cmd --real
VERIFY_V3.cmd --verify-lesions
```

Verification covers the existing 21 contract checks and 11 lesion contract checks, together with offscreen Qt mouse/key/button checks for the old and new workflows. Lesion tests cover independent layer geometry, split traces, continuous paint, erase, draft/old-label masking, confirmed empty negatives, independent uncertainty restoration, exclusion/shadow masks, definition/snapshot validation, roles, save/reopen, undo/redo, confirmation invalidation, display/help toggles and read-only behavior. Warning tests exercise Yes/No popup buttons, canceled confirmation creating no label, independent outside-edge confirmation, bright red multi-boundary and single-A-line bars, saved/reopened override provenance, and exclusion of invalid geometry from training targets. The actual training-target reader is exercised with in-memory unit records; all disk annotation fixtures are explicitly synthetic and ineligible.

Read-only rendered checks loaded CNV TS267, control TS165 and prelaser TS247 caches (five B-scans total). Layout inspection includes real CNV and synthetic painted screenshots. These are software-rendering and storage checks, not evidence of segmentation accuracy or a live desktop usability study. **637 pre-existing annotation/metadata files were fingerprinted and unchanged.** No production annotation or new trained model was created. Results: [verification/latest.json](verification/latest.json), [verification/latest_lesions.json](verification/latest_lesions.json). Earlier September 15 implementation details follow below.

## Delivered behavior

The replacement is under `review/code/octa_seg_v3`. New GUI events use `semantics=3`; old events without this field retain the original downward ordering. New ordering anchors the exact active drawing, moves only colliding available neighbors in affected columns, stops at the first non-conflicting neighbor, and leaves impossible image-edge geometry visible for an explicit correction/judgment. Joins stop at missing or explicitly denied selected-boundary gaps. No healthy-thickness priors were changed.

## Drawing reliability and latency fix

New strokes preserve existing reliability judgments on joins and moved neighbors. Their provenance remains separate from reliability; it no longer forces dashed styling or a pale dotted overlay. Explicit negative marks and geometry errors still affect display. A retained confirmation display mask keeps unrelated curves visually stable after an edit, while the actual approval is revoked and training still requires reconfirmation. This display-only mask is derived during replay and is not a training target or a change to historical annotation arrays. Events with semantics 1/2 retain their original reliability replay.

The stroke path validates/replays once, uses vectorized ordering with equivalence checks against the original algorithm, and saves compact atomic journals without copying every historical snapshot. Revision history, locking, stale-writer checks and fsync remain. Compatibility NPZ saves are batched after 500 ms idle and flushed on Save, confirmation, navigation and close. Saves and context refreshes defer during a live gesture.

The synthetic 30-stroke benchmark with one full confirmation measured median stroke handling plus UI processing at **611 ms before / 193 ms after** (last ten: 687 / 202 ms). Both runs used cProfile and the same fixture on this machine; timings are not a guarantee for every dataset or drive. Profiles and samples are under `verification/drawing_before_1789463455767681200` and `verification/drawing_after_1789463580768206100`; reproduction script: `verification/benchmark_drawing.py`. The regression suite now includes normal/uncertain drawing, retained neighbor reliability, revoked training approval, exact ordering equivalence, actual continuous Qt dragging, and deferral of writes/context refresh during gestures. See `verification/latest.json` for current results.

## Saved records and confirmation

`label_gui.py` is the only annotation writer. It writes authoritative revisioned journals atomically, retaining history and abandoned redo branches. Compatibility labels still use the established `eight_surface.labels` serializer through the GUI. Per-reviewer locks, exclusive file locks and hash comparisons protect new writes. Adoption verifies the historical hash and stores a backup/provenance; timers and browsing never adopt old work.

Whole-B-scan events use `whole-bscan-confirmation-1`. They store the scope, reviewer/scan/native geometry, boundary names, source/model identity, role, annotation and geometry revisions, timestamp, exact final positions/state/provenance masks and approved-position mask. The reader verifies snapshot identity and replay equality. Positional/state/exclusion changes revoke the full approval; undo/redo follows the replayed revision. Notes, display, navigation and sharing do not revoke it. Changing data role requires reconfirmation. Old completion metadata never creates approval.

The right-side tools, marking mode, key and confirmation action are persistent. Advanced tools hold numerical ranges, anatomy and specialized resets. Sampling/roles/notes are collapsible. Saved-review indexing merges historical and new journals by reviewer/scan/native row, distinguishing work from tags. A new adopted record supersedes its old view without duplicating the case. Navigator lines are rebuilt from saved work after refresh/navigation/restart, not from hover or memory alone.

## Training-target reader/export

`feedback.training_targets(record, baseline, offset, depth, shadow, role=...)` is the explicit reader. It verifies confirmation and source identity and returns:

* `approved_position`: eligible confirmed final coordinates, including unchanged, directly drawn, joined and displaced positions. Explicit unreliable/no-trace/absence, exclusion, shadow and invalid geometry are withheld.
* `drawn`, `joined`, `displaced`: origin masks, independent of human approval.
* Separate ambiguous candidates/manual positions and traceability/reliability/anatomy targets. Unknown remains masked; no-trace needs no numerical curve.

Draft, historical-only, practice, synthetic and mismatched-role records do not enter the new whole-confirmed training pool. Historical training readers keep their old contracts; they do not silently inherit this new meaning.

After activating `octa`, run:

```text
python "G:\OCT_TreeShrew\octa\outputs\octa-seg\octa-seg_v3\review\launch.py" --export-targets --reviewer lead --role development
```

`assessment` is a separate explicit export role. Exports go to unique `review/training_exports/` directories with provenance and a final completion manifest. They are derived targets, not new human labels. No training occurs. Preserve animal-separated roles and checkpoint ancestry as specified in [TRAINING_PLAN.md](TRAINING_PLAN.md).

## Executed verification

Run **[VERIFY_V3.cmd](VERIFY_V3.cmd) --real**. The dated output and [verification/latest.json](verification/latest.json) contain the executed results.

* **18 contract tests** passed, including historical replay, active PR edits through several misplaced inner boundaries, deeper edits, missing numerical proposals, image limits, join gaps, locality, independent state axes and shadow/exclusion thickness masking.
* Actual Qt mouse/button/key paths passed for selected-boundary drawing, both latched tools, explicit modifier precedence/restoration, no labels from toggles, full-width/all-boundary confirmation, unchanged/moved/joined target masks, undo/redo invalidation, exact reopen, autosave, saved-browser filters and persistent yellow lines.
* Interrupted saves leave authoritative bytes unchanged; stale writers are rejected. Independent reviewers begin from the frozen automatic source. Read-only discussion cannot write labels or mutate journal ownership.
* A previously GUI-written synthetic legacy record was opened without adoption, shown as Legacy, explicitly confirmed through the new button, and backed up with provenance. The historical source bytes remained unchanged. No real human decision was manufactured.
* A sealed synthetic context provider loaded. Missing completion, changed payloads, wrong native geometry and different boundary definitions were rejected. Frozen inference arrays remained unchanged.
* Real cached TS267 D14, TS165 WT and TS247 before-laser volumes loaded read-only with their recorded freshly determined orientation and native crop. B-scans 180/256/320 in the CNV scan and B256 in the other scans were rendered. The actual ONH v2 adapter loaded all three real records (4,215 / 7,545 / 0 pixels respectively). These counts verify loading, not accuracy.
* **232 existing historical and human-context files** were hash-checked before/after with no changes in the executed suite. The archive has 527 verified copies.
* The archived old GUI was extracted into a separate test project and successfully imported. The new launcher also passed from an arbitrary working directory in a relocated project whose path contains spaces. See [verification/path_verification.json](verification/path_verification.json). The familiar top-level verification launcher passed from outside the project.
* A separate **native desktop** launch was selected and activated with Computer Use. The real TS241 D0 B270 legacy review was visually inspected in a 1700-pixel-wide desktop window. Both marking buttons, the bold right-side confirmation key, all boundary controls, persistent yellow saved rows and cyan current row were visible. The real saved-review browser showed five Legacy records at their native B-scan numbers. Only read-only browsing was performed. This is distinct from the offscreen fixture screenshots.

The user then stopped Computer Use with Escape; no further desktop interaction was performed. Real-volume checks are preserved in the dated `verification/20260915_044458/results.json`; the subsequent final synthetic regression is in `verification/20260915_044619/results.json`.

## Limits and intentional choices

The model remains experimental. This task did not fit a model, tune priors, alter acquisitions or overwrite prediction releases. Annotation correctness still requires the human reviewer.

ONH v2 is opt-in because its completed report documents substantial false detections and declines promotion. The newer independent CNV U-Net workflow has no matching provider manifest; its exact integration contract is documented in [PROVIDERS.md](PROVIDERS.md). Optional context cannot change saved segmentation, frozen assignments or layer inputs.

Baseline adoption is not offered: saved work stays on its original provider. A source disappearing or changing produces an error rather than guessed geometry or silent model replacement. Shared queues remain a same-project/filesystem workflow, not a portable off-site data package.

The review files are under an output release directory and were already untracked in this workspace. No unrelated pre-existing workspace changes were reverted or committed.

## Shared eraser and navigator colors

The Erase toggle and E shortcut now apply to the selected annotation. Lesion erasure uses the existing GUI events; retinal erasure records `erase_boundary`, removing only the selected boundary coordinates/provenance in the swept A-line span while preserving traceability, reliability, anatomy and other boundaries. Erasure invalidates confirmation and supports save/reopen and undo/redo. Redrawing fills only the explicitly drawn span. Missing erased positions remain subject to the overridable geometry warning. Hyper_Ref remains brush-based; the dial does not size retinal/CNV-edge span erasure.

All boundaries includes all manual lesion overlays, and the Advanced lesion visibility control updates ON/OFF/SOME. Navigator confirmed rows are green (#41e36f), drafts/legacy remain dashed yellow, and the current row is solid orange (#ff9600) above the saved-status layer. Earlier yellow/cyan verification descriptions document the previous UI.

Verification passed 21 existing and 11 lesion unit checks plus both offscreen GUI suites in `verification/20260917_225746` and `verification/lesions_20260917_225626`. New checks exercise the shared eraser on region/edge/paint/retinal boundaries, local coordinate removal without new anatomy judgments, redraw, saved/reopened erasure, undo restoration of confirmation, full overlay visibility, and navigator colors. Both runs found 832 protected annotation/metadata files unchanged.

## Persistent vessel/shadow uncertainty

`context_policy.py` defines `vessel-shadow-uncertainty-1`. It combines frozen and currently displayed vessel masks conservatively, and adds shadow columns. The derived boundary guard exempts ILM. Rendering applies uncertainty after confirmation/positive human state and before manual no-trace/absence overrides; CNV edge uses the same guard. This fixes confirmation previously making masked curves solid. Image exclusions continue to suppress candidates. Context refresh recomputes the active editor without adding annotation events. Thickness maps and point readouts also mask the current vessel/shadow union, including cached other slices.

Training target generation excludes guarded non-ILM positions from reliable-manual and approved targets, withholds conflicting positive reliability supervision, and preserves human judgments separately. The original shadow guard still excludes ILM from hard shadowed positional targets. CNV-edge known/valid targets are masked through vessels/shadows without rewriting the stored edge state. Export includes the exact guard masks, policy identity, original human reliability and refreshed vessel provenance. Replay, historic snapshots, and saved review completion remain unchanged.

Regression coverage checks confirmed/drawn positions under vessel-only and shadow-only masks, ILM exemption, no-trace gaps, unmasked tissue, CNV-edge target masking, refreshed displayed masks, no annotation writes from refresh, and persistence after reopen. Read-only replay of the real confirmed TS241 D42 B189 found zero solid non-ILM positions and zero reportable thickness values inside the frozen vessel/shadow union; all 42 vessel-column ILM positions remained solid.

The guard update passed 21 existing and 13 lesion unit checks plus both offscreen GUI suites in `verification/20260917_231238` and `verification/lesions_20260917_231137`. Both runs found 835 protected annotation/metadata files unchanged. The lesion run includes a rendered confirmed vessel/shadow uncertainty screenshot.

## September 18: column-wide manual shadow override and visible mask

Policy `vessel-shadow-manual-override-2` supersedes the prior absolute shadow guard. Replay derives `shadow_override_sources` from surviving normal reliable retinal/CNV-edge direct strokes (including existing explicit reliable-drawing events). It does not rewrite human journals, confirmation snapshots or detector masks. Unreliable/legacy-unspecified strokes, joins, region/paint actions and confirmation alone do not create override evidence. Erase/reset and current per-boundary denials remove a source; any remaining source can still lift that full column. The context helper intersects these sources with the original shadow mask to define a separate override cohort and effective shadow mask.

The B-scan paints the effective mask light orange (#ffad55, alpha 32) through the full image depth. Overridden columns get only a small orange top marker with provenance tooltip. Rendering, CNV-edge display, cached thickness maps, point measurements and target preparation all use the effective mask. Explicit manual exceptions and vessel guards are retained independently. Removing a mask does not declare untouched curves reliable or confirm a draft.

Export format `octa-reviewed-targets-3` adds the original/effective shadow masks, column cohort and 9-row source mask. `--shadow-overrides include|exclude` is recorded in the manifest and output directory. Exclude removes the cohort from every supervision mask and state label; raw coordinates, manual judgments and cohort provenance remain separate. The training plan requires an independent include/exclude experiment and stratified analysis for this group, separate from manually unreliable labels.

Verification passed 21 existing and 16 lesion unit checks plus both offscreen GUI suites (`verification/20260918_003131`, `verification/lesions_20260918_003306`), with 1,152 protected annotation/metadata files unchanged. Tests cover direct-span-only override across all boundaries, preserved manual exceptions and vessel restrictions, no override from uncertain strokes/joins/painting/confirmation, source erasure and multiple-source behavior, undo/reopen, orange tint and provenance marker, and independent include/exclude target masks. The export CLI help exposes the new switch. Read-only replay of real TS241 D42 B244 at A-line 132 retains the original shadow bit but now lifts the effective mask for all boundaries and displays the reliably drawn GCL/IPL as solid. No production labels or training exports were created.
