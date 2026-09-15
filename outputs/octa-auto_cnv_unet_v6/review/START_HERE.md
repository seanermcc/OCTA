# Review original B / C CNV predictions

Open **[OPEN_CNV_REVIEW.cmd](OPEN_CNV_REVIEW.cmd)**. The old launcher in `all_samples` now opens this GUI too.

## Review a sample

1. Choose an acquisition, **B or C**, and **seed 267, 268 or 269**. Use **B vs C at this seed** to compare matching seeds. Orange always shows the original, unedited predictions. Magenta marks disagreement, not which model is correct.
2. Use the four checkboxes on the right: **B acceptable**, **B unacceptable**, **C acceptable**, **C unacceptable**. Each model has one independent rating per acquisition and seed. Click a checked option again to clear it. Leave undecided pairs unset.
3. Accept adequate detection and extent without cosmetic boundary edits. Reject meaningful false suggestions, missed CNVs, or gross extent errors. Ratings assess the original outputs even after human editing.
4. Select a false suggestion and use **Delete false suggestion**. To mark a miss, use **Add missed CNV**, paint its footprint, choose displayed-model attribution or **both B and C at this seed**, then **Confirm missed CNV**. Both-model attribution shares one human footprint.
5. Painting, erasing, and outline confirmation remain available. **Confirm gross outline correction** explicitly records a significant extent error. These error actions mark only the attributed model/seed unacceptable. Undo/Redo restores the associated ratings and current evidence state.
6. **Save** retains partial work; ratings and confirmed errors save immediately. **Finish this review** is allowed with unset ratings and unresolved drafts. It creates no whole-field background labels and does not declare unreviewed tissue negative. Use **Next** to continue.

**Show manual annotations** is off by default. When enabled, prior annotations appear only as read-only cyan references (lavender for prior uncertainty and gray for prior removals). They never enter the CNV list, need no reconfirmation, and cannot block saving or finishing. Hiding a reference says nothing about whether tissue is negative.

The structural OCT, actual OCTA, and native B-scan remain linked. The layer-thickness view retains its original experimental interpretation and missing-value gaps. Scroll the right panel for notes and lesion-editing status; model-rating progress is shown separately at the top.

## Files and preservation

- **Active reviews:** `regions/`; current ratings, human footprints, error evidence and revision history. Session timing is separate in `sessions/`; launcher errors are in `logs/viewer.log`.
- **Archive:** [`../old_review/20260914_231418/archive.zip`](../old_review/20260914_231418/archive.zip), with [`MANIFEST.json`](../old_review/20260914_231418/MANIFEST.json). All 60 archived files were verified before relocation. A later session flush and the former summary launcher are preserved in `late_session_and_launcher.zip` alongside it. The archive was packed losslessly to reduce disk allocation overhead.
- **Previous review information:** `legacy_all_samples/`. The two active human review records and their existing history were copied byte-for-byte into `regions/`. Historical Keep/Remove actions remain recorded but do not assign new B/C ratings. Original pilot review assets in this directory remain intact.
- **Frozen inputs:** read directly from `../all_samples/` and the provenance-linked native exports. All six prediction sets, checkpoints, comparison reports, original pilot and original manual annotations remain unchanged. No inference, retraining, threshold tuning or negative-label export is performed.
- **Status:** [HUMAN_REVIEW_STATUS.md](HUMAN_REVIEW_STATUS.md), refreshed with [SUMMARIZE_REVIEW.cmd](SUMMARIZE_REVIEW.cmd). Human evaluation remains pending except for real user decisions already saved. Test actions are isolated and never counted as human evaluation.

## Loading and verification

The GUI asynchronously loads the next two acquisitions in the filtered navigation order. It retains at most three samples and 1,536 MiB of native array data, subject to available memory. Switching B/C or seeds reuses native images. Obsolete queued work is cancelled; an in-progress disk read finishes its current operation before cancellation is checked. Prefetch creates no review records, viewed events, ratings or review time.

**Verified:** 22 automated checks, real-data comparisons on three acquisitions, and startup through the actual launcher. See [VERIFICATION.md](VERIFICATION.md) for measured loading results and preservation evidence.

**Disk space:** the G: drive filled during an early verification attempt. Only new test scratch files were removed by this task, and the new archive/history storage was compacted without data loss. A later disk check showed approximately 150 GiB available. A failed save retains edits in memory and does not overwrite the prior saved record.
