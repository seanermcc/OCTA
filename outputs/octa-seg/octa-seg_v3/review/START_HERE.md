# octa-seg_v3 — whole-B-scan review

Open **[OPEN_OCTA_SEG_V3.cmd](OPEN_OCTA_SEG_V3.cmd)**. The familiar launcher one folder above also opens this replacement. Use your own reviewer ID; `lead` reopens the lead's work.

## Review a B-scan

1. Choose a volume and native B-scan, or open **My saved reviews**.
2. Select a boundary on the right. Left-click/drag corrects it. Your stroke stays where you drew it; colliding neighbors move. Joining or moving a line does not mark it unreliable. Nearest-boundary picking is off by default and optional under Advanced.
3. Click **Unreliable**, then right-drag to retain an uncertain dashed position. Click **Not traceable**, then right-drag to leave a gap. Both tools act on the selected boundary. Click the active tool again to turn it off. Tool selection alone creates no annotation.
4. **Draw as unreliable** is separate: it draws uncertain new coordinates with a left-drag. The marking buttons keep existing coordinates.
5. Inspect every boundary across the entire image and click **Confirm entire B-scan**. If boundaries were hidden, the first click restores the all-boundary inspection view; inspect it and click again. Red rulers identify unexplained missing, out-of-image or crossing positions. Correct them or record an appropriate uncertainty/no-trace/absence/image-exclusion judgment.

**Confirm entire B-scan approves the final segmentation, including unchanged automatic curves. Your unreliable and not-traceable marks remain exceptions.**

Confirmation includes inspected joins and moved neighbors, preserving their software origin. No redrawing of correct curves is required. Autosaved work is Draft until confirmation. Later geometry/state changes require reconfirmation; notes, view changes and sharing flags do not. Changing a data-use role requires reconfirmation. Undo/redo restores the corresponding approval validity.

Ordinary drawing preserves reliability on joins and neighboring lines. Explicit unreliable marks remain until you restore them. Editing a confirmed B-scan changes its confirmation status without making unrelated lines look unreliable. Each stroke is saved immediately in the review record; the secondary label file is updated between gestures and when saving, confirming, navigating or closing.

## Gestures

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
| E | Clear image exclusions |
| Wheel / middle-drag or Space / F | Zoom / pan / fit |
| 1–8 or brackets | Select a boundary |
| Left/right arrows or Page Up/Down | Adjacent native B-scan |

Explicit modifiers take precedence over latched tools. Reliability restoration cannot erase no-trace or anatomical-absence decisions. **Clear marks in last span** clears visibility/reliability to unknown. Anatomical absence and its separate clearing action are under Advanced. Numerical ranges are also there; normal work uses dragging.

## Find and resume saved work

The navigator uses **solid yellow** for confirmed reviews and **dashed yellow** for saved drafts/legacy work. Cyan marks the current slice. These lines cover the full native width and remain in the thickness view. Hover shows native B-scan/status; click the row to reopen. Browsing and sampling flags alone never create review lines.

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

Refresh reloads compatible CNV/vessel/ONH context, also refreshed after app activation and debounced filesystem polling. Human masks, drafts and reviewed absence take priority. Saved CNV v5/v4/v3 region records are supported. The completed learned ONH v2 proposal adapter is available via the explicit experimental checkbox; its documented false detections prevent automatic promotion. The existing vessel proposal remains the default.

New providers must follow [PROVIDERS.md](PROVIDERS.md). Unreviewed cases can use a compatible completed surface release. Existing reviews and independent queues retain their saved source, and changed source hashes are rejected. No baseline-adoption button is offered in this release; explicit model migration requires a separately reviewed workflow. Overlay exposure is recorded separately from frozen inference inputs.

Read [TRAINING_PLAN.md](TRAINING_PLAN.md) for the single active collection contract and provisional 120-unique-B-scan budget. No model was trained in this GUI task. See [IMPLEMENTATION.md](IMPLEMENTATION.md) for executed checks and limits.
