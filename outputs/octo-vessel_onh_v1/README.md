# octo-vessel_onh_v1

Flagged major-vessel and ONH review, based on the existing en-face editor's
brush and outline controls. This version opens the cached native structural
en-face image used by the frozen vessel method, without loading entire OCT
volumes or requiring layer segmentation.

Double-click **OPEN_REVIEW.cmd**. The imported gallery queue contains 85 scans:
62 flagged for vessel issues, 35 for ONH, including 12 flagged for both.
The editor resumes at the first scan whose requested review is unfinished.
Use the scan dropdown to revisit any item.

## Editing

- Select Vessel brush or ONH brush. Left/right drag adds; Ctrl + right drag erases.
- **Erase (E)** toggles a visible eraser: select the target and left-drag to erase.
  With ONH outline selected, Erase temporarily uses a round brush.
- ONH masks take priority: ONH painting/outlining removes overlapping vessel
  pixels, and vessel painting cannot add pixels inside ONH. Undo restores both
  masks together. Erasing ONH does not automatically recreate removed vessels.
  Existing overlaps are cleaned when opened and saved through the GUI; original
  inputs remain unchanged. Derived removals are recorded in
  `vessel_removed_by_onh`, separately from direct vessel brush strokes.
- ONH outline fills a closed freehand outline drawn with the left mouse button.
- Adjust brush diameter; scroll to zoom, middle-drag to pan, F to fit.
- Show masks toggles overlays for inspecting the underlying image.
- Vessel uncertain area / ONH uncertain area paint separate exclusion masks;
  the same erase gesture removes these exclusions. They are orange.
- Undo/redo restores masks, touched areas, review decisions and exclusions.
- Choose ONH visibility: visible, partially visible, outside image or cannot judge.
- Explicitly tick Vessel mask fully reviewed and/or ONH assessment reviewed
  after completing that target. A stroke clears that target's review flag.
- Save draft, Save + next, navigation and closing preserve unfinished work.

Existing ONH edge annotations appear in green. ONH erasing also removes their
pixels. CNV annotations are preserved as inherited data and are not edited here.

## Saved data and training use

Corrections are written only by the GUI to **labels/** in this version folder.
Frozen batch outputs and old human annotation files are read-only inputs.
Saved corrections (including empty drafts) take precedence over old labels,
which take precedence over automatic vessel seeds. Explicit reviewed absence
also takes precedence. Opening an image alone creates no annotation.

Files retain the existing en-face label format with additional editor fields:
original vessel/ONH masks, actual brush footprints, original batch vessel mask,
per-target review decisions, uncertain-region masks, ONH visibility, inherited
label path/hash, exported queue/hash and editor version. Legacy stroke provenance
cannot be reconstructed; it is not invented. A thumbnail flag is not approval.

Future training must respect per-target review and exclusion masks. Unreviewed
automatic pixels are not human labels; Cannot judge does not establish ONH
absence, and partially visible ONH is a clipped footprint, not its full extent.
These files are not automatically injected into existing analysis or training.
Consumers must deliberately select the reviewed corrections and honor the new
exclusion/visibility fields (older readers may ignore those fields).

Depth orientation is inapplicable to this two-dimensional tool and explicitly
marked as such. The legacy boolean orientation field is a placeholder and must
not be used to orient B-scans. Geometry stays native [B-scan, A-line].

## Implementation and verification

app.py is the versioned queue/editor adapter. canvas.py snapshots the previous
en-face canvas and adds middle-button panning. label_store.py snapshots the
existing atomic en-face writer and adds editor provenance before atomic replace.
The existing code/eight_surface GUI is unchanged.

All 85 queue inputs load with matching source/grid geometry. GUI lifecycle
tests use temporary test output and verify empty drafts, undo/redo, explicit
review, ONH outlines, exclusions, provenance and save/reopen. No production
human labels are created by those tests. Run test_editor.py in the activated
octa environment to repeat them.
