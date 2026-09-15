# Implementation and verification — September 15, 2026

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
