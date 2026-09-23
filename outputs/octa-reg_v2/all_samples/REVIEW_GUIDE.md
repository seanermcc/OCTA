# Montage placement review

Open `OPEN_REVIEWER.cmd`, or visit http://127.0.0.1:8771/TS165_OS/index.html while
the local reviewer server is running. The server listens only on loopback.

- Supported and flagged groups start visible. Orange dashed fields are existing
  flagged placements; their automatic reasons remain visible after review.
- Select a field and choose **Review category** to move it between **Overlap /
  supported**, **Flagged / uncertain**, and **Excluded**. Alternatively drag its
  scan-list row onto one of those sections. Excluded scans disappear from the map;
  exclusions you make here are reversible and retain the previous pose for restore.
  The original source exclusions remain locked because they have no prepared pose.
- Write **Scan notes** for any category, including flagged scans. Text autosaves
  after a short typing pause or when leaving the box. Category changes clear that
  field's placement confirmation and reopen montage confirmation. Notes reopen
  montage confirmation. Confirming a field's pose never changes its category.
- Day checkboxes filter both the map and field list. Labels have at most four
  characters (`pre`, `d0`, `d14`, `d119`, `wt`, `6mo`). Hover for dates and the
  source day convention. Actual days after laser take priority when available;
  the current prepared inventory mostly provides nominal days. TS165 OS contains
  only the WT visit, so its legend has one `wt` checkbox.
- Click a field in the map or list. **Confirm field** approves its current rigid
  placement. **Move field** enables dragging; **Rotate field** rotates by dragging
  around the marked center. The angle box and ±1° buttons allow precise rotation.
  Focus the canvas in Move mode to nudge with arrows (Shift = ten pixels).
- **Undo** reverses this session's last review action. **Reset to automatic**
  restores the original pose and clears confirmation. For an unlocalized field,
  **Place at view center** starts a manual draft without claiming automatic evidence.
- **Move ONH** in the map toolbar lets you click the correct center or drag the
  orange marker. Select **Done moving ONH** to return to normal navigation.
  **Reset ONH** restores the original center; **Undo** reverses an ONH correction.
  The images stay in place. Whole-montage confirmation is reopened, while individual
  field confirmations are retained because their placement has not changed.
- **Review all fields** reveals all groups/days. **Confirm montage** then approves
  the current review decisions across the montage, separately from individual pose
  confirmations. Flagged stays flagged and excluded stays excluded. Unlocalized
  scans can remain flagged; supported fields must have a placement first.
- Moving, rotating, resetting, or reopening a field clears that field's and the
  montage's confirmation. Supported fields with confirmed poses get green outlines;
  flagged fields keep orange dashed outlines even when their pose is confirmed.

Changes save automatically after each gesture or decision. Check **Saved to disk**
before closing. A failed save is visibly marked **NOT SAVED**; retry or export the
draft JSON. Concurrent stale tabs cannot overwrite a newer saved review. Reloading
restores saved placements and decisions; display filters start with all days visible.

**Retry save** resends pending changes after an unsuccessful save. When there are no
pending changes, it reports that everything is already saved. **Export review JSON**
downloads a backup of the current decisions, placements, ONH correction, and current
ONH-relative transforms, including unsaved changes. It is not an image export and
does not save back to the server. The reviewer currently has no JSON import button.

Each eye's `human_review.json` stores current decisions and rigid transforms in
native pixels relative to the unchanged ONH/reference origin. `review_history/`
contains immutable revisions, including confirmation snapshots and UTC save times.
Schema 2 adds `onh_override` (a manual center in the original automatic frame) and
`effective_matrices_to_onh_pixels` (all current placements rebased to that center).
The matrices inside `fields` remain in the original frame for stable rendering.
Older review records load with no ONH override; source matrices are never overwritten.
Schema 3 adds `decisions`, keyed by scan ID, with `tier` and free-text `notes`.
`analysis_records` materializes every scan's automatic category, effective review
category, notes, pose-confirmation state and current transform. Excluded scans have
no effective transform (their old editable pose is retained only for undo/restore).

Future analyses must use `octa_reg_v2.review_server.analysis_inputs(folder)` rather
than the original automatic `montage.json`. This entry point checks the registration
fingerprint, requires whole-montage confirmation, returns only supported scans by
default, and retains the saved review revision and ONH correction. An explicit
`include_flagged=True` includes placed flagged scans with their category and notes;
excluded scans are never included. `require_confirmed=False` is an explicit draft
inspection option. Existing automatic reports and coverage images are unchanged;
this change does not rerun downstream analyses.
These are placement-review records, separate from layer/vessel/ONH mask labels and
the automatic registration. Republishing the UI preserves them. Changed automatic
poses are fingerprinted and require reconciliation rather than silent reuse.

The overview cards display whole-montage and individual review progress. Original
PNGs and automatic coverage totals remain explicitly labeled as original; they do
not incorporate day filters or manual corrections. No automatic registration,
mask, raw volume, or training label is altered by this reviewer.

## Orientation

The origin is the reviewed ONH where available, otherwise an explicitly estimated
ONH or unresolved reference field. The axes retain the reference image orientation:
x increases right along A-line columns; y increases down along B-scan rows. Other
fields are rotated/translated into that frame, without mirroring. This does **not**
establish anatomical north/superior, south/inferior, nasal or temporal. Independent
acquisition orientation is needed before using those labels or comparing anatomical
directions between eyes. Editing the reference field does not move the coordinate
origin or automatically adjust other fields.

## Maintenance

After activating `octa` and setting `PYTHONPATH` to the repository's `code` folder:

```
python -m octa_reg_v2.reviewer_publish
python -m octa_reg_v2.review_server
python -m unittest octa_reg_v2.test_review -v
```

`reviewer_publish` updates all 19 interfaces and visit metadata without rerunning
registration. Browser interaction tests use the isolated `reviewer_test/TS999_OS`
fixture, never real review decisions. The original `PUBLICATION.json` remains the
automatic-registration provenance; `REVIEWER_VERIFICATION.json` describes this UI update.
