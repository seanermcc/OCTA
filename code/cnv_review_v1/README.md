# Separate CNV region reviewer

Open **OPEN_CNV_REVIEW.cmd** in this folder. It activates the `octa` environment
and opens the 32-scan queue. The default first scan is TS247 D21 from the recent
manual review. Loading structural/OCTA projections can take a minute or more;
the window displays loading status while the volume is read.

This application lives entirely in `code/cnv_review_v1`. It imports the existing
data readers and provenance-aware boundary editor without changing their files.
The previous GUIs, launchers, masks, boundary labels and model outputs are intact.

## Reviewing a region

1. Select a scan at the top. Existing CNV masks are separated into connected
   regions, each initially **Unclassified**. An imported outline is not a
   diagnosis or a category decision.
2. Click a region or its list entry. The reviewer selects a nearby manually
   drawn B-scan if one exists, otherwise the region's middle row. Yellow spans
   on both en face views show recorded manual strokes; faint dotted rows show
   saved reviews. Red rows indicate rejected B-scans, which remain accessible.
   The list gives exact row numbers. **Near selected region** optionally limits
   that list and the row overlays; the margin is in native B-scan rows.
3. Click a saved row, use the B-scan number/slider, or press Page Up / Page Down.
   A click within two rows of a displayed review snaps to it; the number and
   slider always select the exact native row. Indices run from 0 to 511.
4. Choose **Full Lesion**, **Normal**, or **Other**, and add notes for that
   particular region. Other remains an incomplete draft until it has explanatory
   text. Notes are available for all three categories. No category is inferred
   from the segmentation, vessel mask or scan's experimental group.
5. **Draw region**: left-drag a closed outline in either en face panel and
   release. **Redraw** changes the selected outline while retaining its identity,
   category and notes. **Remove**, **Undo region edit** and **Redo** let you adjust
   the region list. Escape cancels an unfinished outline. Touching/disconnected
   older outlines may need redrawing/removing to match your intended lesion units.

Region changes autosave after a pause. **Save all / Ctrl+S**, scan navigation and
closing also save. Unclassified regions and Other-without-notes are preserved as
drafts. Merely browsing an imported outline does not create an annotation file.

## Editing the B-scan

The lower panel is the actual boundary editor, embedded in this window. Select
one of the eight current boundaries, then left-drag to change it. Undo/redo is
Ctrl+Z/Ctrl+Y while editing. Boundary edits save with Save all, the boundary Save
button, Ctrl+S, navigation or closing. Notes in that panel belong to the B-scan;
notes beside the region list belong to the region.

- Solid coloured segments: recorded direct strokes without an uncertainty denial.
  This describes provenance, not independent accuracy.
- Orange dashed strokes: drawn positions marked uncertain, excluded or displaced.
- Dashed coloured curves: current automatic or saved joined/untouched geometry.
- **Compare latest auto (dotted)**: display the current automatic prediction
  alongside a saved correction. It does not change the annotation.
- The selected boundary's existing visibility/reliability ruler and local flags
  remain visible. The expandable editing-help control lists all gestures.

Shift+right-drag marks the selected boundary locally unidentifiable;
Alt+right-drag marks it locally unreliable. Add Ctrl to restore the corresponding
flag. Right-drag alone excludes the whole A-line for every boundary; Ctrl+right
clears that exclusion. These decisions remain separate from lesion categories.
Drawing retains local unreliability (and sets visibility over the new stroke as
in the current editor). Rejected reviews remain available for further inspection.

The B-scan is fitted using approximately 1460 µm field width and 1.12 µm/depth
pixel. Drawing coordinates remain the original native pixels. Wheel zooms;
Space pans the B-scan; middle-drag pans either en face view. **Fit views** resets.

## Vessels

The saved vessel mask takes priority, including reviewed empty masks and saved
empty automatic drafts. Where there is no saved vessel work, the existing
major-vessel proposal is displayed and explicitly identified as unreviewed.
The blue mask stays on both en face panels and appears as translucent blue
columns plus a blue strip in the B-scan, including during boundary editing.

These are **projected vessel footprints, not vessel depth segmentations**. The
2-D mask supplies which A-lines intersect a vessel; it does not locate vessels
axially. Vessel masks remain read-only in this new reviewer. Continue vessel
brush corrections in the previous GUI, save there, then use **Reload sources**.

## Original sources and new saves

New output directory: `outputs/cnv_review_v1/`

| Folder | Content |
|---|---|
| `regions/` | Per-scan JSON containing individual region IDs, native footprints, categories, notes, completion flags, B-scan intersections and source metadata |
| `regions/history/` | Earlier saved region revisions |
| `surface_labels/` | New boundary corrections in the existing eight-boundary/local-provenance label format |
| `surface_history/` | Earlier revisions of boundary files saved by this new GUI |
| `surface_context/` | Original annotation path/hash, source volume/crop, automatic-provider identity and timing scope |
| `settings.json` | Optional persisted provider configuration after choosing a newer automatic folder |

Boundary source priority is this new folder, then the recent
`stage_a/20260909_full_labeled_cohort/manual_review_36/labels`, then
`eight_surface/labels`. These two original input folders currently contain
196 B-scan files with no overlapping scan/row keys. Older ten-surface labels
and independent repeatability labels are different contracts, not input to this
eight-boundary reviewer. Legacy labels without local provenance are shown as
saved traces with unknown stroke span; no precise manual footprint is invented.

A saved correction keeps its original curves, automatic baseline and local
flags. Rows without any saved geometric correction use the latest automatic
provider, even if an older automatic row had been accepted/rejected. Existing
image exclusion and uncertainty decisions remain; acceptance/review of an old
automatic position does not approve a changed prediction. The original label
is preserved, and the context records position reviews not transferred.
Loading or browsing these derived views writes nothing.

Timing in new saves measures the active linked-review window, including en face
inspection, rather than isolated B-scan editing. This distinction is recorded
in the context file and should be respected in later annotation-cost audits.

One application instance per output directory is enforced. Saves also detect
external changes to the destination rather than silently overwriting them.
The legacy applications may remain open: their output folders are separate.

## Updating automatic predictions

The toolbar displays the selected source for each scan. Default priority:

1. Full-cohort experimental model, 2026-09-09: all rows of the four volumes in
   `stage_a/20260909_full_labeled_cohort/full_volume_review/packs`.
2. Existing eight-boundary cascade in `eight_surface/segmented` for the other
   28 scans. This fallback is explicitly identified in the toolbar.

Choose **Choose newer auto folder…** to add a higher-priority provider, then
**Reload sources** after updates. The choice persists in the new settings file.
The current scan must be present and compatible before a folder is selected.
Missing scans fall back through the configured list. A present but incompatible
file raises an error instead of silently falling back.

Each file is `<scan_id>.npz` or `<scan_id>_pack.npz`, with:

- `surfaces`: float `[native B-scan, 8, native A-line]`, canonical vitreous-first,
  in the displayed retinal crop's depth coordinates, covering all rows.
- `scan_id`, `source` (or `source_volume`) with the processed MAT source path,
  `surface_names` in the current eight-boundary order, and `cascade_version`.
- `retina_band`: exact stored-depth `[lo, hi]` crop; or the existing full-volume
  pack's `label_offset` (canonical crop start). Native-grid arrays must not be
  resized, reordered, transposed or shifted.
- Optional `confidence` with the same shape. Learned-model packs carrying
  `prediction_checkpoint` do not reuse their confidence on the classical
  local-confidence scale. Optional `bscan_index` must be exactly `0..N-1`.

No prediction, training, quality ranking or vessel fitting is run by this GUI.
Future models can use this same export contract without changing the GUI.

## Checks

After activating `octa`, from the repository root:

```powershell
$env:PYTHONPATH = "$PWD\code"
python -m unittest cnv_review_v1.test_review -v
```

The synthetic Qt checks exercise actual canvas signals, navigation, region
editing, classification, save/reopen, uncertainty retention, old-file protection,
automatic-source replacement, draft preservation and source mismatch rejection.
`verify_real_data.py` performs read-only integration checks and renders previews;
its outputs are in `outputs/cnv_review_v1/verification`.
