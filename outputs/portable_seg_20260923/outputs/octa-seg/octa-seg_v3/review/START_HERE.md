# octa-seg_v3 — whole-B-scan review

Open **[OPEN_OCTA_SEG_V3.cmd](OPEN_OCTA_SEG_V3.cmd)**. The familiar launcher one folder above also opens this replacement. Use your own reviewer ID; `lead` reopens the lead's work.

## Saved CNV context — September 22 update

The final v9 CNV assessment/correction dataset now loads automatically. The en-face
view shows a **pink outline with light translucent fill**. At the selected native
B-scan, matching pink bands cover the **full displayed depth** wherever that row
intersects a CNV footprint. Moving between B-scans updates these bands.

Saved final corrections take priority immediately, including saved drafts and
confirmed absence; an additional dataset export is not required to refresh the
display. Otherwise the final dataset supplies accepted masks and confirmed
negatives. Pending cases retain their selected assessment footprint and explicitly
say **correction pending**. Unsure/excluded pixels in saved corrections are omitted;
poor-image exclusions show no footprint and remain identified as excluded.

Use **Refresh saved vessel / CNV / ONH overlays** after saving elsewhere, or allow
the existing automatic refresh. Save and close an already-open reviewer, then
relaunch it once to load this code update. These pink overlays are reference
context; the separate manual CNV region/edge tools keep their existing behavior.

## Manual CNV tools — September 17 update

**Automatic shadows are light orange full-depth columns.** A normal reliable retinal-boundary or CNV-edge stroke lifts the automatic shadow mask across its directly drawn horizontal span **for all boundaries**, not only the selected one. The orange tint disappears there; a small orange marker at the top retains the manual-override provenance. Existing strokes explicitly recorded as reliable are included without rewriting their journals. Joins, displaced neighbors, confirmation alone, uncertain strokes, region painting and Hyper_Ref paint do not create overrides. Undo, erasure, resetting the source stroke, or denying its reliability/traceability can restore the shadow mask if no other qualifying stroke remains.

This only removes the automatic shadow restriction. **Vessel masks and explicit manual unreliable, Not traceable, anatomical-absence and image-exclusion judgments remain separate.** Untouched boundaries are not automatically labeled reliable. Confirmation still approves only valid positions outside the remaining exceptions. ILM remains exempt from automatic vessel/shadow uncertainty. Overridden shadow columns are retained as a separate group for future training and analyses; see TRAINING_PLAN.md for the include/exclude switch.

Under **Boundary editing**, the tools are arranged as:

```text
All boundaries: ON / OFF
Unreliable          Not traceable
Draw as unreliable   i
CNV region          CNV edge     i
Hyper_Ref            size dial   Erase
```

* **CNV region:** left- or right-drag horizontally across the lesion to mark full-height columns. Ctrl+drag clears a span. Selecting it switches off previously selected uncertainty tools and takes drawing priority; saved unreliable/not-traceable judgments stay unchanged. This is separate from image exclusion, the CNV sampling tag and the automatic en-face overlay.
* **CNV edge:** left-drag to trace the bottom lesion edge. Ctrl+drag removes a span. Separate strokes can leave gaps; this trace never pushes a retinal boundary. Draw as unreliable and the boundary uncertainty marking gestures also work on CNV edge.
* **Hyper_Ref:** left-drag to paint dots. The dial controls diameter in native image pixels; **Erase** (keyboard E) toggles erase (or hold Ctrl while dragging). Painting stays aligned when zooming or stretching the view. Undo/redo and autosave cover all three tools.

**Erase** works on the selected retinal boundary, CNV region, CNV edge or Hyper_Ref. Turn it on, then left-drag; turn it off to draw again. For boundaries/region it removes the selected horizontal span; Hyper_Ref uses the round brush. Retinal erasure removes coordinates while preserving existing traceability, reliability and anatomy judgments; it does not declare tissue absent. Undo restores erased data. E no longer clears image exclusions; use Ctrl+right-drag or the Advanced exclusion controls.

Manual region is translucent purple, edge is pink, and painted dots are gold. Select a retinal boundary (or press 1–8) to return to layer editing. **Advanced** includes a manual-lesion overlay visibility control. CNV edge can extend outside CNV region without a warning or confirmation restriction. Erasing a region does not erase edge or paint annotations.

**All boundaries**, directly below the RPE list entry, toggles all eight retinal curves and CNV region/edge/Hyper_Ref together. A partial selection is shown as SOME; clicking it shows all annotations. This is display-only: it leaves saved annotations and confirmation intact. Confirming with hidden curves first restores them for inspection. The `i` beside the CNV pair explains full-height lateral region versus lower-edge depth trace.

**Tentative convention:** Hyper_Ref means hyperreflective dots inside the lesion, above/separate from RPE. CNV edge means the bottom of the dark outer-retinal lesion above RPE. These definitions can change after examining the manual examples; describe differing cases in notes. The saved definition version preserves what each review meant. See [the plan](TRAINING_PLAN.md) before training.

**Confirm entire B-scan includes these new annotations. An empty Hyper_Ref mask inside an inspected CNV region means none is present.** Drafts and historical layer-only confirmations are not negative lesion labels. Older completed reviews retain their layer approval and show that the lesion tools have not yet been reviewed; explicitly inspect and reconfirm to include them. Each real stroke is saved by the GUI; opening a case or selecting a tool does not create a label.

Click the small **i** buttons to show/hide the longer explanations beside **Draw as unreliable**, **Confirm entire B-scan**, and the thickness **coverage percentage**. Restart an existing GUI window to load the update; use Save first to finish its current work.

## Review a B-scan

1. Choose a volume and native B-scan, or open **My saved reviews**.
2. Select a boundary on the right. Left-click/drag corrects it. Your stroke stays where you drew it; colliding neighbors move. Joining or moving a line does not mark it unreliable. Nearest-boundary picking is off by default and optional under Advanced.
3. Click **Unreliable**, then right-drag to retain an uncertain dashed position. Click **Not traceable**, then right-drag to leave a gap. Both tools act on the selected boundary. Click the active tool again to turn it off. Tool selection alone creates no annotation.
4. **Draw as unreliable** is separate: it draws uncertain new coordinates with a left-drag. The marking buttons keep existing coordinates.
5. Inspect every boundary across the entire image and click **Confirm entire B-scan**. If boundaries were hidden, the first click restores the all-boundary inspection view; inspect it and click again. Red rulers identify unexplained missing, out-of-image or crossing positions. Correct them or record an appropriate uncertainty/no-trace/absence/image-exclusion judgment.

**Confirm entire B-scan approves the final segmentation, including unchanged automatic curves. Your unreliable and not-traceable marks remain exceptions.**

Confirmation includes inspected joins and moved neighbors, preserving their software origin. No redrawing of correct curves is required. Autosaved work is Draft until confirmation. Later geometry/state changes require reconfirmation; notes, view changes and sharing flags do not. Changing a data-use role requires reconfirmation. Undo/redo restores the corresponding approval validity.

Missing, out-of-image or crossing retinal positions appear as **bright red bars at the top of the B-scan**, with a separate row for each affected boundary. Hover a bar for the boundary name. Confirmation warnings use the same bright red. These geometry warnings, and Hyper_Ref paint outside CNV region, open **“Are you sure segmentation is fully complete?”** Choose **Yes** to save a confirmed review with the exact warnings recorded, or **No** to return to editing. Invalid retinal positions remain excluded from positional training targets. A confirmed review with warnings is identified in the status text. Hidden overlays are first restored for inspection; read-only mode, unavailable data, stale/conflicting saves and storage failures cannot be overridden by this popup.

Ordinary drawing preserves reliability on joins and neighboring lines. Explicit unreliable marks remain until you restore them. Editing a confirmed B-scan changes its confirmation status without making unrelated lines look unreliable. Each stroke is saved immediately in the review record; the secondary label file is updated between gestures and when saving, confirming, navigating or closing.

## Gestures

The following boundary gestures apply when a retinal boundary is selected. The lesion tools use the gestures described above.

| Gesture | Meaning |
|---|---|
| Left-drag | Draw selected boundary |
| Right-drag with a marking button active | Mark that boundary's span |
| Alt + right-drag | Unreliable, keep candidate |
| Shift + right-drag | Not traceable, show gap |
| Ctrl + Alt / Ctrl + Shift + right-drag | Explicitly restore reliability / traceability independently |
| Right-drag with neither marking tool active | Unusable image for **every boundary** |
| Ctrl + right-drag | Clear whole-image exclusion |
| Shift + left-drag | Explicit visible/reliable local judgment; does not complete the B-scan |
| Ctrl+Z / Ctrl+Y / Ctrl+S | Undo / redo / save |
| U | Clear selected boundary visibility/reliability marks to unknown |
| E | Toggle Erase for the selected retinal boundary, CNV region, CNV edge or Hyper_Ref |
| Wheel / middle-drag or Space / F | Zoom / pan / fit |
| 1–8 or brackets | Select a boundary |
| Left/right arrows or Page Up/Down | Adjacent native B-scan |

Explicit modifiers take precedence over latched tools. Reliability restoration cannot erase no-trace or anatomical-absence decisions. **Clear marks in last span** clears visibility/reliability to unknown. Anatomical absence and its separate clearing action are under Advanced. Numerical ranges are also there; normal work uses dragging.

## Find and resume saved work

The navigator uses **solid green** for confirmed reviews and **dashed yellow** for saved drafts/legacy work. **Orange** marks the current slice, above its saved-status line. These lines cover the full native width and remain in the thickness view. Hover shows native B-scan/status; click the row to reopen. Browsing and sampling flags alone never create review lines.

**My saved reviews** filters by scan/animal/notes, volume, status, CNV/ONH category and shared/bookmarked cases. It supports resume-last and previous/next saved review. Opening your own case revises the same record. Counts distinguish saved reviews, confirmed reviews, remaining selected assignments, and available B-scans.

**Review lists** opens the normally hidden secondary toolbar. It remembers its visibility, retains flagged/shared queues and export, and clearly separates selected-case jumps from adjacent-B-scan navigation. **Next unreviewed** follows the active assignment when one is present.

## Independent review and discussion

Each colleague uses a different reviewer ID. Shared queues freeze source/model identity and data role, and include no lead traces, notes or judgments. Colleagues begin from automatic predictions. The existing shared queue launcher remains supported.

To discuss saved work, choose its owner in the saved-review browser and open **Discussion mode**. It opens a separate read-only window; the observer's exposure is recorded separately from annotation. Another person's review cannot change ownership or become the observer's independent annotation.

## Storage and history

* New authoritative journals: `review/reviewers/<id>/journals/` (paths relative to v3).
* New compatibility labels: `review/reviewers/<id>/surface_labels/`, through the established annotation writer. These are **not** the whole-confirmation training contract; use the journal reader/exporter.
* Historical originals: `v3/reviewers/<id>/`. Old work appears as **Legacy** before adoption. Browsing, timers and save-only actions do not adopt it. An explicit GUI edit or confirmation makes a new record with the original path/hash and backup. Old completion flags are never retroactive approval.
* Shared queues: `review/review_queues/`; existing `v3/review_queues/` remains readable.
* Recoverable archive: see [migration.json](migration.json) and [MIGRATION.md](MIGRATION.md).
* Tests/screenshots: `review/verification/`; synthetic records are ineligible for training.

Do not edit the same historical case in an older window during adoption. A changed historical hash or simultaneous/stale new writer is rejected rather than overwritten.

## Context and future models

Refresh reloads compatible CNV/vessel/ONH context, also refreshed after app activation and debounced filesystem polling. Final v9 corrections and the final dataset take priority for CNV, with saved v5/v4/v3 region records retained as fallback for acquisitions outside that dataset. Human masks, drafts and reviewed absence take priority over optional automatic providers. The completed learned ONH v2 proposal adapter is available via the explicit experimental checkbox; its documented false detections prevent automatic promotion. The existing vessel proposal remains the default.

New providers must follow [PROVIDERS.md](PROVIDERS.md). Unreviewed cases can use a compatible completed surface release. Existing reviews and independent queues retain their saved source, and changed source hashes are rejected. No baseline-adoption button is offered in this release; explicit model migration requires a separately reviewed workflow. Overlay exposure is recorded separately from frozen inference inputs.

Read [TRAINING_PLAN.md](TRAINING_PLAN.md) for the single active collection contract and provisional 120-unique-B-scan budget. No model was trained in this GUI task. See [IMPLEMENTATION.md](IMPLEMENTATION.md) for executed checks and limits.
