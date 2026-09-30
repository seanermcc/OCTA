# CNV-Core and Full-CNV Lesion — September 29, 2026

Open `OPEN_BOUNDARY_REVIEWER.cmd` (or the spelling-compatible
`OPEN_BOUNDRY_REVIEWER.cmd`) on Windows. On Apple Silicon macOS open
`OPEN_BOUNDRY_REVIEWER_MAC.command`.

The same row now contains **CNV-Core**, **Full-CNV Lesion (RPE-Disrupt)**,
and a circled **i** that expands these definitions:

> CNV-Core is defined as the region where RPE is non-traceable with a loss of contrast (dark) blood-vessel invasion from the RPE

> Full-CNV Lesion is defined by regions where the RPE is clearly disrupted, and this should not depend on the hyper-reflective dots above the RPE

Select a category and left-drag across the B-scan to mark its lateral extent.
Each category is saved separately as full-depth columns. They may overlap.
Erase (E) removes only the selected category. Ctrl+drag also erases on Windows;
Command+drag erases on Mac. Mac shortcut labels use Command and Option.

**Colors:** CNV-Core is purple; Full-CNV is cyan; the separate octa-auto_CNV
context is pink. **Show auto-CNV (pink)** independently hides/shows the automatic
context in both the B-scan and en-face navigator, without changing any saved
mask, annotation, or reliability judgment. CNV edge and Hyper_Ref remain separate tools.

The requested migration maps lead's old CNV Region to CNV-Core and Shichu's
old CNV Region to Full-CNV. The opposite category is empty. Original events,
layer coordinates, exclusions, reliability judgments, review times, CNV edges,
and Hyper_Ref paint are preserved. No new human confirmation or negative label
is manufactured; use Confirm entire B-scan after reviewing both new categories.
Migration records form an undo floor. Older revisions remain in journal history
and the dated archive, and new strokes support normal undo/redo.

On My Passport (F:), the original reviewer sets stay under `octa/reviewers`.
The Windows app saves to `octa/For_Segmentation/Reviews/reviewers`.
Lead's more recent live work is preserved there. Shichu's migrated review set is
also available there, under her own reviewer ID.

Mac scan caches remain on the external drive. Existing Mac behavior saves new
reviews locally in `~/Documents/OCTA_Boundary_Reviews/portable-20260923/Reviews`.
The first launch seeds missing local review storage from the Passport. Existing
local lead/Shichu journals migrate through the GUI writer when opened; they are
never overwritten with the Windows copy. Native Mac execution was not tested
from Windows.

Previous GUI code and launchers: `archived/cnv_gui_before_20260929` on the
Passport, and `outputs/archived/cnv_gui_before_20260929` in the D: project.
The Passport archive includes exact original journal backups. Read
`CNV_DISTINCTIONS_MIGRATION.json` for the per-file audit. The source and data
used by octa-auto_CNV remain separate and unchanged.
