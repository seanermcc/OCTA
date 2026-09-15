# First 15 saved reviews — read-only audit, September 13, 2026

All first 15 queue entries have readable saved annotations and vessel review
marked complete. Source identity, native grid, retinal band, queue hash and
automatic seed hash match. All have zero vessel/ONH overlap and zero vessel
changes unexplained by recorded vessel brush footprints or ONH-derived removal.
Human annotation files were read only; no review decisions were changed.

Nine have ONH review checked. Entries 1 and 6 contain partial ONH masks but
ONH review remains unchecked. Entry 6 was ONH-flagged, so 14/15 have completed
the targets originally requested by the gallery flags. Entries 8, 11, 12 and
13 say Outside image but leave ONH review unchecked; this does not lose the
saved vessel corrections or prevent their vessel-only queue tasks being done.

Visual inspection of all 15 triptychs shows major trunks generally follow the
visible structures, with broad border/seam false detections removed. This is
qualitative inspection, not independent quantitative accuracy validation.

Items to revisit:
- Entry 8, TS241_OD_2024-08-21_D7_s08_123208: the central major-vessel mask has
  a gap around the horizontal acquisition seam. Check whether to connect it
  where visible or explicitly exclude the unsupported section; do not invent
  continuity through missing evidence.
- Entry 6, TS169_OS_2025-01-14_D35_s02_120614: inspect the small round lateral
  protrusion on the lower central trunk; it may be residual non-vessel signal.
- Entry 7, TS241_OD_2024-08-21_D7_s05_120651: ONH meets the left image edge;
  check whether Partially visible is more appropriate than Visible.
- Entries 1 and 6: if ONH review is finished, check ONH assessment reviewed
  and save; the drawing itself has already been saved.

## Review scope supplied by the user

The user is correcting major vessels, not systematically tracing smaller
vessels; smaller automatic branches may be left in place. Interpret the
existing vessel review flags in this scope. They do not establish exhaustive
all-caliber vascular ground truth.

For future training, do not treat every unpainted small vessel as confirmed
background or every untouched small automatic branch as confirmed human
foreground. The recorded brush provenance is useful but does not identify all
small-vessel ambiguities. A consistent major-vessel target definition and
separate reviewed/ignored support will be needed before training/evaluation.

For distance to major vessels, use a consistently selected major-vessel mask;
leaving incidental smaller branches in the measurement mask can reduce nearest
distance and make results depend on which small branches happened to be
segmented. These labels do not establish total vascular density or complete
branch counts. Do not delete small real vessels simply to clean the source
annotation; preserve them and define the downstream measurement target.

audit.json contains per-scan measurements. page_1.jpg through page_5.jpg show
original image, saved vessel/ONH masks and changes against the initial vessel
mask. Orange in these figures means removed vessel pixels; training-exclusion
regions are measured in audit.json but not overlaid in these triptychs.
