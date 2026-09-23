# Verification record

- 34 focused tests passed: 21 new adapter/transform/failure-isolation checks and 13 existing pure geometry checks. `unit_tests.txt` and `unit_tests.json` record the run. The heavyweight atlas CLI was never invoked.
- The TS165 OD smoke run accounted for 10 scans and 45 pairs: one automatic proposal, 44 rejections, no software failures. A repeated initial smoke run reused all 45 pair artifacts. The corrected release repeated the smoke run with the same gate outcomes.
- `verify_resume.py` uses isolated copies of two optical caches and their sidecars. It confirms exact artifact reuse on an unchanged rerun, then changes one pixel and the corresponding cache hash in the copy. The pair signature changes and matching is recomputed. Upstream files are never edited. See `resume_invalidation.json`.
- `verify_release.py` independently checks the candidate denominator, scan/component partition, animal/eye separation, explicit exclusions, artifact checksums, all passing gates, rigid matrices, inverses, transformed footprints, native pixel roundtrips, and every consumed source hash. It also recovers a synthetic 0.12 radian rotation and [26, -13] µm translation across unequal [2, 3] versus [1.5, 2] µm pixel grids. See `release_audit.json` for measured results.
- The selected export is authoritative for empty masks and drafts. Tests force hash/grid/source-identity failures and prove they cannot activate fallback. Missing ONH, separately reviewed ONH, and uncertain ONH edges are tested. ONH disagreement cannot invalidate relative registration; synthetic loop disagreement does withhold a component.
- Pair-exception isolation is tested with an injected runtime failure followed by another pair. No thresholds were relaxed, and the imported baseline matcher is the identical function object and produces identical deterministic results on identical arrays/settings.

## Browser inspection

The offline smoke gallery was opened in the Codex browser through a loopback-only local preview server. The actual TS165 OD s03→s04 passing pair was inspected with selected vessel overlays and outlines. The s01→s02 rejection was inspected with centerline/junction overlays: Dice 0.600 and structural correlation 0.555 passed their gates, but zero matched junctions rejected it. This illustrates why a promising visual overlap is not promoted by relaxing one gate.

A native single-image center click returned B-scan 255.62 and A-line 255.89, consistent with the expected [255.5, 255.5] center to within the browser click's pixel rounding. The nearest indices were [256, 256]. The numerical release audit separately tests exact transform roundtrips. Visual inspection is software/display QA, not independent anatomical landmark validation.

The final cohort gallery's TS283 OD D14 s03→s05 pair was also inspected with centerline and ONH overlays: the visible provenance correctly distinguishes reviewed vessels in both scans from their different ONH states. The structural/OCT-A switch and flicker controls were exercised. Exported `panels/case_03.png` (highest passing Dice) and `panels/case_04.png` (high-Dice junction rejection) were visually inspected at full image resolution; all four panels, labels and vessel-difference colors render correctly.

The final release audit passed: all 324 acquisitions and 3,695 candidate pairs are accounted for; all 975 consumed files retain their hashes; original annotation/proposal metadata for 314 files is unchanged across the recorded in-run integrity check; both upstream model hashes match the pinned sidecars. The maximum numerical pixel roundtrip error is 1.71e-13 pixels. The final full run completed in 445.5 seconds with zero implementation failures. Exact figures are in `release_audit.json` and the parent `status.json`.

## Correction record

The first cohort pass incorrectly treated five new TS336 inventory records as blocked because optional legacy `n_slow`/`n_fast` fields were absent. The caches and fresh-source sidecars supplied valid dimensions. This was an adapter implementation error, not acquisition failure. A regression test now accepts this documented schema variant while rejecting conflicting dimensions. The full cohort was rerun. The initial pre-fix summary is retained solely as an execution audit.

The new ONH wrapper removes uncertainty from original anatomical edges rather than creating edges around uncertainty holes. Failed-consensus RANSAC diagnostics are recovered with the same seed and settings for reporting only. Neither change modifies the baseline matcher or its gates.

The installed scikit-image returns a false-valued FailedEstimation sentinel for some poorly conditioned fits. The added diagnostic-only path initially checked only for None and raised when reading that sentinel's params. A regression test now supplies a false-valued sentinel and verifies an algorithm rejection, not an implementation failure. The final cohort was rerun after this correction; the inherited matching function remains unchanged.

## Limits

All accuracy measures are internal; independent human landmark arrays remain empty. The forest is not global optimization. Synthetic coverage does not establish accuracy on distorted retinal data. Vessel-mask quality, motion and topology explanations require measured follow-up using the saved queue. No historical CNV masks, thickness arrays, model predictions or source volumes were loaded for matching; original processed-volume identity/orientation provenance comes from the existing cache sidecars. Every consumed cache/sidecar/mask is rehashed after execution. Source annotations, legacy atlas work and unrelated working-tree edits were not changed by this implementation.
