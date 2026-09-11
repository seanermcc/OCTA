Run every available acquisition through the frozen **octa-seg_v1** model, generate quantitative QC reports, and prepare the results for preliminary analysis in octa-thick.

The TS267/TS328 longitudinal assessment looks good enough for preliminary analysis, particularly for good-quality acquisitions. Proceed with the full batch. I want quantitative measures that I can compare with my own qualitative assessments of scan quality.

## Scope and organization

- Read `AGENTS.md`, `README.md`, `PIPELINE.md`, and the octa-layer-segmentation skill before starting.
- Put this run in its own folder: **`outputs/octa-seg_v1_batch/`**.
- Keep its manifest, supporting scripts, logs, segmentations, QC tables, figures, review configuration, and reports inside that folder. Do not add run-specific files to the main octa folder or general code folder.
- Preserve existing releases, the ten-volume assessment, the longitudinal assessment, and all human annotations.
- Process **every available `*_processedVolumes.mat` acquisition**, including every repeat, both eyes, and every available timepoint—not one representative scan per visit.
- Reconcile the index with files on disk first. The project previously reported 314 processed acquisitions; verify the current count.
- List unavailable or unreconstructed acquisitions separately. Never reconstruct from `.RAW`.
- Process all available scans regardless of quality. Do not silently exclude poor-quality scans.

## Frozen model and processing

- Use the frozen octa-seg_v1 position and state checkpoints in:
  `outputs/octa-seg/octa-seg_v1/models/ALL_LABELLED/`
- Match the processing that produced the **v1 outputs** in `outputs/longitudinal_assessment/v1/`.
- The longitudinal runner is now at `outputs/longitudinal_assessment/code/longitudinal_assessment.py`. Inspect it for reusable preparation and octa-thick compatibility work, but do not run its paired v1/v2 workflow unchanged.
- Do not retrain, refit priors, change thresholds, or apply octa-seg_v2 reporting rules.
- Keep segmentation-model versions separate from thickness-viewer versions. This is an **octa-seg_v1 batch**.
- Process every native B-scan and A-line. Preserve canonical orientation, crop offsets, source identity, and checkpoint provenance.
- Retain raw model positions, reported positions, uncertainty states, contextual estimates, and shadow masks separately.
- Preserve existing handling of human denials, exclusions, and missing measurements. Never create human annotations from automatic outputs.
- These are preliminary automatic results for review, not a new validation or accuracy claim.

## Quantitative QC outputs

Create:
- `scan_qc.csv`: one row per acquisition.
- `boundary_qc.csv`: one row per acquisition and boundary.
- `layer_qc.csv`: one row per acquisition and layer.
- Readable per-scan summaries with diagnostic figures.
- A metric dictionary documenting definitions, units, denominators, masking rules, interpretation, and limitations.

Keep acquisition quality, model support, and segmentation irregularity as separate dimensions.

### Boundary-level measures

For every boundary, report:
- Percent reported, uncertain, and not traceable.
- Finite raw-position and contextual-estimate coverage.
- Distributions of traceability/reliability probabilities and positional entropy.
- Adjacent-A-line and adjacent-B-scan jumps, including robust summaries and upper percentiles.
- Crossings, invalid geometry, and out-of-crop positions.

Label model traceability as a **model assessment**, not confirmed human visibility or a calibrated probability of correctness. Report explicit human visibility judgments separately where available.

### Layer-level measures

For every available layer measurement, report:
- Finite measurement coverage and eligible sample counts.
- Mean, median, standard deviation, IQR, MAD, and selected percentiles.
- Local thickness discontinuities separately from overall spatial variation.

Compute statistics over eligible finite measurements without filling missing values. Keep statistics from segmentation-reported thickness separate from statistics using octa-thick’s preliminary measurement policy, and identify the policy explicitly.

Large thickness variation may reflect real CNV pathology. Within-scan standard deviation is not measurement uncertainty. Report unavailable or unreliable layer measurements explicitly rather than silently dropping them.

### Independent acquisition QC

Use the existing scan-quality workflow to include:
- Retinal/vitreous contrast.
- Low-signal coverage.
- Striping and adjacent-B-scan continuity.
- Shadow coverage.
- Same-session repeat agreement, interpreted only when `repeat_comparable` is true.

Do not use legacy `quality_confidence` or segmentation-support rankings as acquisition-quality labels.

Where suitable annotations exist, provide separate summaries for CNV, vessel-shadow, and other eligible regions. Document overlap and exclusion rules, and distinguish human annotations from automatic proposals.

For coverage metrics, distinguish the full native grid from eligible non-excluded regions. Include missing-data reasons. State whether larger values indicate stronger signal, greater irregularity, or simply greater biological variation.

## Comparison with my qualitative assessments

- Create a separate table for my **Good / Usable / Poor / Unsure** scan ratings and comments.
- Do not populate human ratings automatically or treat generic segmentation acceptance as a scan-quality rating.
- If compatible explicit ratings already exist, preserve their provenance and identify which are being used.
- When ratings are available, compare individual metrics against them using distributions, plots, and appropriate association measures such as Spearman correlation for ordered ratings.
- Treat Unsure separately from the ordered categories. Account for repeated acquisitions from the same animal and flag missing or sparse ratings.
- If ratings are unavailable, finish the batch and leave the comparison ready for later input.
- Do not invent a combined quality score, tune thresholds to these ratings, or exclude scans based on uncalibrated metrics.

## Execution and resumption

- Actually run the entire batch, not just prepare commands or a sample.
- Activate the `octa` conda environment correctly.
- Make execution resumable, with durable logs, per-scan completion markers, and a failure report.
- Reuse existing outputs only after verifying matching sources, native grids, checkpoints, input masks, and processing policies. Record reused artifacts and their provenance.
- Use safe parallel processing where useful, with protection against duplicate writes to a scan.
- Resolve recoverable failures and continue other scans when one fails. Never count partial or failed scans as complete.

## Octa-thick handoff

- Make every completed volume compatible with the existing preliminary octa-thick workflow.
- Store this batch’s thickness selection, configuration, and exports inside `outputs/octa-seg_v1_batch/`.
- Add an **`octa-thick_batch_v1.cmd`** launcher inside the existing `outputs/octa-thick_v1/` folder, pointing to this batch.
- Preserve the existing preliminary thickness policy and existing longitudinal launchers. Do not introduce a new measurement policy.

## Completion checks and delivery

Verify native coordinates, full-volume coverage, output integrity, masking, metric calculations, and compatibility with the actual octa-thick engine.

Deliver a concise report inside `outputs/octa-seg_v1_batch/` covering:
- Expected, completed, reused, failed, and unavailable acquisitions.
- Verification results and material limitations.
- Locations of the QC tables, diagnostic figures, and qualitative-rating table.
- Exact **Anaconda Prompt** commands for opening this batch in octa-thick and resuming processing.

Keep progressing autonomously until every available acquisition has either completed processing and QC or has a clearly documented, investigated failure.