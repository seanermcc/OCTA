# octa-reg_v3 review

Open `OPEN_REVIEWER.cmd` for the save-enabled reviewer on port 8774. The v2 reviewer on 8771 is preserved. Choose an animal and eye; imaging dates remain pooled with individual day checkboxes.

The TS165 OD/OS starting positions, seven flagged categories, individual confirmations and OD ONH correction are inherited from the exact saved v2 reviews. They are documented as inherited records, not new approvals. Neither montage was whole-montage confirmed at the snapshot. All other v3 placements need human review.

Pink outlines show the selected CNVs from the latest v9 Model3 release. Toggle **Show CNV outlines** to hide them. Select a field to see whether its CNV mask is a manual correction, frozen manual reference, confirmed model result, partial edit or unconfirmed prediction. Eight unfinished correction fields contribute only explicitly kept regions with reduced weight; draft regions are not accepted CNVs. Empty unconfirmed masks do not establish absence.

Select a scan to move, rotate, confirm or change its category. Drag rows between Supported, Flagged and Excluded, or use the category selector. Notes save with the scan. Confirmation does not promote a flagged scan. Original source exclusions stay locked.

**Move ONH** changes the orange origin marker and rebases reported coordinates; images retain their relative placements. The display uses the reference image's x-right/y-down axes. Anatomical nasal/superior/east/west labels remain unverified.

Changes autosave into this v3 folder with revision history. **Retry save** resends pending edits after a failure. **Export review JSON** downloads a backup, including pending edits; it does not write that backup to the server and there is no import button. Stale tabs cannot overwrite newer reviews.

Use `octa_reg_v3.review_server.analysis_inputs(folder)` for downstream analysis. It requires whole-montage confirmation, excludes flagged scans by default, never returns excluded scans, and includes notes and effective ONH-relative transforms. `include_flagged=True` is an explicit opt-in. Read-only inspection of unfinished reviews can use `require_confirmed=False`; it does not grant approval.

PNG previews and coverage reflect the v3 release, including inherited TS165 corrections. Later reviewer changes remain in `human_review.json`; they do not retroactively regenerate those PNGs or coverage numbers.
