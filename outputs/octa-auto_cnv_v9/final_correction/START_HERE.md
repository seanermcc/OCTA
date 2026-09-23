# Final CNV correction

Open **OPEN_FINAL_CNV_CORRECTION.cmd**. This is a separate copy of the current
desktop CNV correction editor, including its September 22 performance fixes.

Your final assessment flagged **15 entries across 14 acquisitions**. This queue
contains those 14 acquisitions, starting from the exact footprint you flagged:
manual training, Model 2, Model 3 or previously corrected Model 3, as appropriate.
No previous correction or training label is overwritten.

TS267_OD_2025-02-19_D0_s02_112013 was flagged in both its manual and corrected
versions. It appears once here, starting from the corrected version. Toggle
**Reference: assessment versions** to inspect both original footprints. The
manual version's 3,832 unknown pixels remain Unsure until explicitly resolved.
Both flagged entry IDs are preserved in the queue provenance.

Select an orange region, Paint / Erase its boundary, and use **Keep CNV** or
**Remove**. Use **Add CNV** for missed lesions. Inspect the whole field and click
**Confirm entire image**. Save alone retains a draft. **Next pending** advances
through unresolved cases; reopening resumes edits. For a genuine negative,
remove the proposals and any uncertain areas, check **No-CNV present**, and
confirm the image. Unsure / excluded pixels are ignored, never negative.

The optional OCTA and Structural B-scan views are the established editor's
native image providers; this queue does not change layer segmentation.

## Accepted cohort and final export

Your message accepting everything else is recorded verbatim in
`queue/acceptance.json`, together with the saved assessment snapshot. It accepts
**203 positive acquisitions and 105 confirmed negatives**. Two prior poor-image
samples retain their exclusion status and are not converted to negative labels:

- TS325_OD_2026-05-26_6mo_s05_120658
- TS328_OD_2026-04-29_D21_s04_105712

After confirming corrections, click **Export final dataset + sizes**. This
refreshes `dataset/manifest.json` with exactly one record per acquisition and
`dataset/summary.json` with current completion counts. The initial export has
308 confirmed, 14 pending and two excluded acquisitions. New corrections
supersede both flagged versions where a duplicate existed. If all 14 are
resolved as positive or negative, there will be **322 labeled acquisitions and
two explicitly excluded poor-image acquisitions**. Further deferrals remain
explicit exclusions. Uncertain pixels can remain masked within labeled images.

Only use target paths referenced by confirmed records in the manifest; never
glob target folders. Each target contains `target`, `known`, `ignored`,
`instances`, `scan_id` and `axis_order`. Manual unknown pixels retain their
original status. Retained training exposure is not an independent evaluation
split. No new model is trained by this workflow.

New human corrections are written only by the editor's Store to
`review/regions`, with revision history. Queue preparation creates no human
annotation files. The accepted frozen targets and exports are derived artifacts
with source provenance. The earlier HTML assessment remains a snapshot and does
not automatically display newly edited masks.

The queue is frozen deliberately. Later flags added to the HTML assessment
require reconciliation before they can join this queue. Source identity, exact
mask checks, synthetic confirmation/export tests, native image alignment and
isolated GUI save/resume results are recorded in `verification/results.json`.
Activate the octa conda environment before running Python tools.
