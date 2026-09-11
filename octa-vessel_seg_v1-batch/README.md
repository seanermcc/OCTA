# octa-vessel_seg_v1-batch

Full-cohort run requested September 11, 2026: 314 processed acquisitions.
See `status.json` for live counts; completion is confirmed by `manifest.json`
with status `complete`, 314 complete, zero failed, and 32 exact queue matches.

## Outputs

- `proposals/`: native-grid automatic major-vessel masks (`*_proposal.npz`).
- `previews/`: structural OCT en-face overlays; blue vessels, green human ONH exclusion.
- `index.html`: browsable preview gallery, generated at batch completion.
- `projections/`: full-resolution mean-dB retinal-band structural projections.
- `records/`: per-scan provenance, hashes, component audit and errors, if any.
- `inventory.json`: all input acquisitions and recorded projection bands.

The unchanged September 9 contrast threshold (0.18) and continuous-band shape
gate are used. Startup verifies algorithm hashes against the original queue
manifest. The original 32 scans reuse their frozen ONH exclusions and projection
bands and must reproduce their masks pixel-for-pixel. Other scans use existing
acquisition-QC retinal bands and saved human ONH exclusions where available.
No layer surfaces are inferred or changed. No human labels are written.

These are automatic proposals for clearly visible major vessels in structural
OCT, not capillary-flow segmentations or independently validated human labels.
Long borders/lesion artifacts may remain, and short fragments may be lost.
The 16 index entries without processed volumes are outside this run.

## Resume

Run `RUN_OR_RESUME.cmd` after the current process has stopped. Complete outputs
are reused only when input identity and output hashes match; failures are retried.
Do not start a second copy while the first is running.
