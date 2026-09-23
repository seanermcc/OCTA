# CNV footprint review v7

Double-click **OPEN_OCTA_AUTO_CNV_V7.cmd**. It activates the `octa` environment. Alternatively, activate `octa` in Anaconda Prompt, change to this folder, and run `python -B viewer.py`.

The frozen queue contains **253 distinct candidate acquisitions across 10 non-WT animals**. Eligibility is strictly **after day 7**; D7 itself is excluded. These are candidates for inspection, not 253 known positive images. The goal is **30 confirmed positive images**, plus useful confirmed negatives encountered along the way. Three lesions in one image count as one image.

## Review an image

1. Inspect both top images and the linked native B-scan. Click an en-face point in Inspect mode to choose its exact B-scan and A-line; use the slider or spin box for rows 0–511. Left is structural OCT; right is actual `frame_OCTAAvg` OCTA projected over the saved retinal crop. It is not a layer-specific slab. This release focuses on these optical views; optional thickness views were not added.
2. Choose **Add CNV** (N) for each separate lesion, then **Paint** (B). Drag to paint a footprint; a closed loop fills on release. **Erase** (E) trims the selected region. Brush diameter is in native pixels. There are no size, shape or lesion-count restrictions.
3. **Keep CNV** (K) accepts a region. **Unsure** (U) or **Exclude area** marks uncertainty/unreadable tissue; use either with a selected footprint, or click it without a selection to start a new area and paint it. **Remove** retains a region as removed in history. To finish, explicitly resolve all drafts and empty footprints. Separate lesion entries remain separate even when their union supplies the positive target.
4. **Save** (Ctrl+S) and autosave retain partial work. They do not certify that you inspected the rest of the field. When you have checked the entire image and marked all visible CNVs and uncertainty, click **Confirm entire image** once. The kept union becomes positive, every other assessable pixel becomes reviewed background, and unsure/excluded pixels remain ignored. You do not paint ordinary background or approve it region by region.
5. For an entirely assessable field with no CNV, check **No-CNV present**, then **Confirm entire image**. This explicitly produces an empty positive mask and whole-field negative coverage. The checkbox alone is a draft intention. It cannot coexist with active drafts, CNVs, unsure or excluded areas; resolve those explicitly first. For indeterminate images use **Skip / defer**, with a reason, instead of absence. Deferral is never a negative label.

Adding a CNV after selecting absence clears the absence selection and invalidates completion, retaining Undo history. Every geometry, region-state, uncertainty or absence change invalidates whole-image confirmation until reconfirmed. Navigation, selection, zoom and context toggles do not. **Undo/Redo** restore geometry and confirmation together, including after reopening the saved revision. A positive/uncertain overlap must be resolved or explicitly confirmed as ignored; the saved confirmation audits its pixel count.

## Footprints on the B-scan

Each displayed footprint intersects the current native `[B-scan, A-line]` row. Its A-line intervals shade translucent vertical bands across the displayed structural depth, with matching color and a top strip. Disconnected intervals and multiple lesions remain visible. The selected region is emphasized. No intersection means no band.

**These are lateral footprint bands, not axial lesion boundaries. The full shaded depth is not a claim of diseased tissue.** Images use canonical depth increasing away from vitreous, without a lateral transpose or flip. The displayed image is a retinal crop; its canonical depth offset is shown, so the top of the crop need not be canonical depth zero. B-scan display scales axes by 1460/512 µm laterally and 1.12 µm axially.

Green means human-confirmed CNV; orange draft; purple unsure/excluded; cyan historical reference; gray removed when shown. Gold is the optional unreviewed v6 C/seed-267 prediction. Selecting a region or drawing does not move the chosen row/cursor. Mouse wheel zooms and middle-drag pans; **Fit views** resets. **Escape** returns to Inspect.

## Queue, resume and progress

**Previous/Next** traverse the frozen queue (or its filtered subsequence); **Next pending** skips confirmed and explicitly deferred records but includes drafts. Use the searchable acquisition dropdown and animal/day filters to browse. **Return to fixed queue** clears filters and returns to the last queue navigation position, independent of manual dropdown browsing. The last acquisition and B-scan resume on restart. Browsing and prefetch never create annotation decisions.

The screen displays confirmed CNV images / 30, confirmed no-CNV images, drafts/deferred, queue position and per-animal positive/negative counts. Counts rebuild from validated current v7 records, with unsaved current edits reflected immediately. Editing a completed field back to Draft decrements its count. Repeat confirmations do not add images. Different repeat acquisitions are distinct images but remain clustered by animal/eye/visit; they are not independent animals or proven independent lesions.

At 30 positives, the application saves and offers a natural stopping point with a summary. It remains editable and does not launch training. The milestone is not proof of sufficient sample size or detector accuracy. Negatives do not consume a positive-image slot. All 253 candidates are persisted; when a pool is exhausted the queue skips it, with the reason recorded in `queue/config.json`.

Seed **20260918** fixes random visits and acquisition order within each animal. Animal cycles use numeric order TS169, TS241, TS247, TS250, TS267, TS283, TS305, TS325, TS328, TS336. TS165 is WT: there are 11 total animals, 10 non-WT. TS169 and TS283 each have only one eligible visit. TS336 July 28 keeps indexed D56 identity despite a D77 folder label; actual days are unknown. Day basis and discrepancies appear in the GUI and queue manifest. See `reports/INVENTORY.md` for the full audit.

## Optional context

Both historical manual references and original v6 C/267 suggestions start hidden on each image. Their separate switches control both en-face and B-scan overlays. Historical references are read-only and never become blocking drafts. The GUI does not copy references automatically or support one-click adoption; draw your own region and explicitly Keep it. Display exposure is recorded with source/model hashes when work is saved. Seed 267 is not claimed to be the best seed. Model ratings are not required.

## Storage and recovery

Everything new lives here: `review/regions/<scan_id>.json` is authoritative, `review/regions/history/` retains versioned recovery records, `review/session.json` stores navigation, `queue/` freezes selection, `cache/native/` holds narrowly necessary recovered native images, and `logs/` records recoverable loading errors. `verification/` is isolated synthetic work and screenshots and never contributes to real progress. No old release, original human label, prediction or checkpoint is modified.

The schema retains native geometry runs, classifications, positive/reviewed-background/ignored masks, whole-field confirmation hash/revision, source identity, reviewer, focused time and reference exposure. Atomic replacement preserves the previous head on save failure. A revision written before a failed head update is a recovery candidate, not authoritative completion. Failed saves retain in-memory edits and prevent navigation/closing. Stale writers cannot overwrite a newer revision. Keep that window open and reconcile the two revisions; do not delete its unsaved work. Lock files identify the saving PID/time. Only remove a stale lock after verifying that its process exited, preserving files first.

Missing/changed providers produce a specific error and remain unlabeled; retry after restoring the provenance-matching source/cache. One background reader retains current/next providers up to 1.5 GiB; full image hashing can make a cold load take several seconds. Ten newer acquisitions lack persisted native B-scans; they are recovered in one bulk processed-volume read, freshly oriented with the established functions and checked against the v6 array hash, then cached only under v7. No RAW reconstruction or neural inference occurs. Large existing native image arrays stay referenced, not copied.

Run `python -B summarize.py` in activated `octa` to refresh progress, historical-label hashes and source-precedence reports without changing annotations or the queue. Run `python -B verify.py` for isolated contract tests. `verify_real.py` opens four real providers and makes synthetic gestures only in verification storage. See `VERIFICATION.md` and `TRAINING_PLAN.md` before future export/training.
