# Model 3 correction queue

Open **OPEN_MODEL3_CORRECTION.cmd**. This adapts the latest desktop CNV editor
(v8 manual-review editor, September 18) to the v9 Model 3 gallery selections.

Of 67 samples with Review Model 3 checked, 10 also had Confirm Model 2 CNVs
checked and are excluded. The queue contains the remaining **57 samples**, in
gallery order. Original review notes appear verbatim in the read-only text box
above the images; long notes can be scrolled. Notes and the complete original
decision are also preserved in the frozen queue and each saved correction's context.

Orange outlines are the exact displayed, adjusted Model 3 candidates. Select a
region and use Paint / Erase, Keep CNV, Remove, or Unsure. Use Add CNV for missed
lesions. The optional Model 3 reference includes hidden candidates.
After resolving drafts and checking the whole field, use Confirm entire image.
For an assessable negative field, remove proposals, check No-CNV present, and
confirm. Next pending advances through this queue; Save and autosave preserve
edits, and restarting resumes the last sample.

**Performance update (September 22):** editing now caches validated progress,
reuses the B-scan image while painting, and limits preview redraws. Autosave
still writes reviews and revision history immediately after the idle delay.
Use **Export confirmed sizes** to refresh derived measurements; that export
runs in the background. Reports are no longer regenerated on every autosave.
The existing review format and queue are unchanged. The pre-update reviews and
editor source are backed up in `backups/before_lag_fix_20260922_033803/`.

New corrections live in `review/regions`, with revision history. Saved edits
take priority over automatic proposals. Gallery decisions, notes, original
labels and frozen predictions remain unchanged. No approvals are generated
by queue preparation. No training starts automatically.

The frozen queue includes the ten excluded acquisition IDs and their source
decisions for audit. `reports/setup.json` records counts; `verification/results.json`
records exact-mask and note checks and isolated GUI save/resume checks.
