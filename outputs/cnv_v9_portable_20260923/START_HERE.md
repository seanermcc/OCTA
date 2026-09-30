# Portable CNV inspection in the current v9 editor

Open `OPEN_CNV_V9_PORTABLE.cmd` with E: connected. This uses the repository's
current final-correction v9 editor, with a cache-only provider for all 62 completed
portable acquisitions. Search the sample dropdown or filter by animal/day.
Click the structural image to select a B-scan; use the slider for rows 0–511.
Scroll to zoom; middle-drag to pan; Fit views resets the view.

The source snapshot contains 59 confirmed positives, one confirmed negative,
and two pending corrections. Pending footprints stay orange. The footprint
bands on B-scans represent lateral overlap, not axial lesion segmentation.
OCTA is unavailable because its channel is absent from this portable cache.

This launcher is for inspection: no annotation decisions or human label files
are created. Original masks, source statuses, and layer reviews remain unchanged.
The final CNV context snapshots are from September 23, 2026. There are another
52 selected acquisitions whose full volumes were not transferred; those are not
included. This adapter does not synthesize missing channels or scan volumes.

Small metadata and mask files are checked against the portable manifest SHA-256
hashes for every sample. All image array headers and sizes are checked at startup;
the complete image hash is checked on first loading each volume per session.
Only inspection session metadata is saved in this launcher's `review` folder.
