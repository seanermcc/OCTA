# CNV region reviewer — separate GUI

Launch [OPEN_CNV_REVIEW.cmd](../../code/cnv_review_v1/OPEN_CNV_REVIEW.cmd).
The existing GUI and original labels are unchanged.

1. Select a scan, then click a region or **Draw region**.
2. Select a yellow manual-stroke row on either en face image, click a saved
   B-scan in the list, or use the B-scan number/slider.
3. Choose **Full Lesion**, **Normal**, or **Other**. Write a separate note for
   each region; Other needs an explanation to become a completed classification.
4. Edit boundaries directly in the lower panel: select a boundary and left-drag.
   The existing local uncertainty and exclusion gestures remain available.
5. Use **Save all / Ctrl+S**. Boundary edits also save when changing rows;
   region notes/categories autosave. New files stay in this output folder.

Vessels stay visible in both en face views and as blue projected columns in the
B-scan. The blue columns locate the en face footprint; vessel depth is unknown.
The toolbar identifies whether the vessel mask is saved/reviewed or an automatic
proposal. Reload sources picks up newly saved vessel work from the old GUI.

The newest full-cohort automatic predictions cover four scans. The other 28
use the clearly named existing cascade fallback. **Choose newer auto folder…**
lets a future full-volume export take priority without changing manual traces.

See the [full guide and automatic-export contract](../../code/cnv_review_v1/README.md).
Verification evidence is in [verification/](verification/).

Implementation note: a programmatic checkbox-restoration problem found during
initial verification was corrected and covered by a regression test. Its one
unintended new-folder artifact was quarantined with a `.not-human` extension;
it is not in the active label folder and is not a human annotation. Original
annotations were unchanged. The final read-only verification checks both original
hashes and absence of new label writes.
