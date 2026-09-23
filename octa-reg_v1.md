# octa-reg_v1 — implementation prompt

Implement and run the following registration-only pipeline in `G:\OCT_TreeShrew\octa`. Carry the work through implementation, testing, a bounded smoke run, full-cohort execution, and a reviewable report. Do not stop after writing a design or launching a background process. This document is an implementation request for a future execution task; its creation did not run registration.

## Objective

Locate overlapping OCT acquisitions in a shared retinal coordinate system for each animal and eye, first within sessions and then across dates. Produce mosaics with individual scan footprints, inspectable vessel alignment, and links back to original scan coordinates. OD and OS must remain separate; never register different animals together. Use animal number rather than sex letters for identity.

The release name is **octa-reg_v1**, the Python module is `code/octa_reg_v1`, and all run products belong under `outputs/octa-reg_v1`. Existing source images, annotations, segmentation releases, and atlas outputs are read-only. Read the repository's `AGENTS.md`, `README.md`, and `PIPELINE.md` before implementation. Preserve unrelated uncommitted changes.

The immediate experiment is **vessel-supported registration without CNV inputs**. Do not wait for CNV completion, train segmentation models, regenerate layer measurements, reconstruct `.RAW` files, or perform thickness analyses. Keep CNV support as an explicit future extension.

## Verified starting state — September 20, 2026

- No `octa_reg_v1` or `retina_registration_v1` implementation or corresponding run folder was found during inspection.
- The older `control_map_v1` status records 72/314 prepared scans. Its recorded PID is absent and its registration directory is empty. Its stale `running` status is not evidence of an active run. Preserve this work.
- `outputs/octa-auto_cnv_unet_v6/all_samples/inventory.json` contains 324 distinct processed acquisitions, 19 animal–eye groups, and 3,695 possible within-eye pairs. Recalculate counts from the input snapshot; these are expected counts, not hard-coded loop limits.
- The selected vessel/ONH export is `outputs/octo-vessel_onh_v2/final_output_v1`. Its verified snapshot contains 314 acquisitions: 58 saved manual records and 256 frozen v1 proposals. It includes two explicitly excluded scans for visual completeness only. Saved manual records can include drafts and untouched automatic pixels; 314 exported masks does not mean 314 human-validated segmentations.
- The directory name `octo-vessel_onh_v2` does **not** mean its learned v2 predictions should be used. Its release notes reject replacing frozen v1 with that learned model. The selected `final_output_v1` export deliberately uses no learned v2 predictions.
- CNV v9 currently provides a 50-acquisition model-comparison/review release; it is not yet a chosen, fully reviewed cohort-wide CNV mask source. No CNV completeness or model-selection assumption belongs in this registration baseline.

## Input adapter and source selection

### Structural images and acquisition identity

Use the v6 all-samples inventory and compact image caches under `outputs/octa-auto_cnv_unet_v6/all_samples/inputs`. Each optical cache has `optical[0]` for structural en-face and `optical[1]` for OCT-A. Read caches and sidecars directly; do not call the CNV GUI/model loaders, which may regenerate other outputs.

Verify scan ID, animal, eye, date, source identity, native grid, cache hashes, and orientation provenance. Keep actual `days_post_laser` when known rather than inferring dates from nominal folder labels. Preserve unavailable acquisitions in the inventory without trying to reconstruct them.

Use native `[B-scan, A-line]` coordinates: rows are B-scans, columns are A-lines, x increases right, y increases down. Never silently transpose, flip, or resize masks. Existing en-face masks do not need a depth-axis flip. If a missing optical cache must be regenerated, read only the processed volume with the established `detect_orientation`/`prepare_bscan` path and save an isolated registration cache; never trust old sample orientation flags.

Use validated per-scan lateral calibration where available, otherwise the approximate 1,460 µm field divided by the actual grid dimensions. Record calibration provenance and its approximate status. `X500um` is galvo amplitude, not retinal extent.

### Vessel and ONH selection

1. Primary source: `outputs/octo-vessel_onh_v2/final_output_v1/manifest.json`, `VERIFIED.json`, and `masks/<scan_id>.npz`. Reuse or adapt its `load_masks.py` identity/hash/grid checks. Load Boolean `vessel_mask` and `onh_mask`, plus available uncertainty, brush, edge, and scalar metadata. Do not extract masks from colored overlay PNGs.
2. Preserve the export's selection exactly when an acquisition is present, including an explicitly empty mask or draft. Do not replace an empty selected mask with an automatic one. Missing input and reviewed absence are different states.
3. Only for acquisitions absent from that export—currently ten—use the existing `vessel` array from the geometry file referenced by that acquisition's v6 input sidecar, after verifying identity, grid, and hash. Mark this `legacy_geometry_fallback`, automatic/unreviewed. Do not substitute learned v2 masks. Missing ONH fields mean unavailable, not absent.
4. If neither source is usable, retain the acquisition and mark affected pairs blocked with an explicit reason. Do not silently manufacture zero masks or run a new segmenter.
5. Honor `excluded_from_analysis` and its reasons before pair matching. At inspection these exclude `TS241_OS_2024-09-11_D28_s04_104606` and `TS247_OD_2024-11-06_D21_s02_103301`. Reconcile flags with the source manifest at execution. Excluded scans remain listed but do not contribute to transforms or mosaics used for analysis.
6. Preserve vessel and ONH review status independently. A vessel review does not confirm an ONH assessment. Draft/unreviewed vessel masks may support experimental proposals, with their status prominently reported; do not call them ground truth.

Pin the source manifests and hashes for the run. Treat the selected export as a frozen snapshot; do not silently absorb later GUI edits or rebuild that export. A later source snapshot produces a new configuration/signature and invalidates affected outputs.

## Existing algorithm to reuse and its limits

Inspect `code/control_map_v1/geometry.py`, `pipeline.py`, `__init__.py`, and their focused tests. Reuse pure registration/geometry functions without invoking the complete atlas runner or modifying its legacy behavior.

The existing process normalizes structural intensity; detects ORB descriptors near vessels; masks unsafe descriptor neighborhoods; matches descriptors; fits a physical rigid transform with RANSAC; and checks overlap, structural correlation, vessel Dice, and junction proximity. It then constructs a minimum-error spanning forest and checks other edges for loop disagreement. This is not joint global optimization.

Freeze these matching defaults for the initial experiment:

| Setting | Value |
| --- | --- |
| Feature proximity to vessel mask | 35 µm |
| Minimum feature inliers | 8 |
| RANSAC residual threshold | 15 µm |
| Minimum usable overlap | 0.15 |
| Minimum vessel Dice | 0.35 |
| Minimum structural correlation | 0.25 |
| Minimum nearby junction matches | 3 |
| Random seed | 1701 |

Record all remaining imported matching parameters and implementation hashes. These are exploratory gates, not calibrated accuracy guarantees. Automatic junction proximity is an internal check, not independent human validation.

Use translation and rotation only. Do not introduce scale, reflection, shear, or deformable warps in this first release. Structural images drive descriptors; selected vessel masks constrain and assess matches. Keep OCT-A for review, without a second matching method in this baseline.

This release changes preprocessing relative to the old atlas: selected vessel masks replace its older geometry masks, and **no CNV masks, lesion buffers, or thickness-derived lesion screens are used**. Mask nonfinite image data, explicit image exclusions, and explicit uncertain regions where available. Use completed, assessable ONH footprints as disc-interior exclusions; show unreviewed/draft ONH footprints as proposals rather than hard exclusions. Do not automatically exclude every vessel shadow, because structural vessel evidence can live there. Record absent exclusion information as unknown.

If valid image inputs trigger a software error, fix the error and record the change; do not relax thresholds to increase match counts. Rejecting every pair is an experimental result, not permission to silently change the algorithm. Separate algorithm rejection from implementation failure.

## Vessel structure and ONH requirements

Use ONH, optic disc, and optic disk as synonymous display/search terms for this task. Vessel geometry is the primary spatial evidence. The eventual matching model should use constellations of branch points, crossings, bends, curvature changes, distances between neighboring vessels, landmark angles, centerline path lengths, and branching topology. A distinctive sequence of bends and branches can identify a vessel even when the disc is outside the field. Distinguish crossings from true bifurcations when supported; preserve ambiguity otherwise.

For this first run, the existing ORB/vessel/junction method is the fixed baseline. Do not claim it explicitly models bend descriptors or full vascular topology. Provide centerline/junction overlays and failure examples that let us decide whether those extensions are necessary before implementing a new matcher.

Reuse visible-boundary ONH circle fitting when reviewed evidence supports it, and retain its arc coverage, residual, and uncertainty checks. The inherited defaults require 150° visible arc, residual at most 25 µm, and center uncertainty at most 150 µm. A clipped image border is not a disc boundary. Unreviewed ONH fits remain proposals and cannot become confirmed anatomical anchors.

Reuse the existing vessel-convergence estimator as a separate exploratory proposal: at least three sufficiently long, relatively straight segments, with conditioning and uncertainty checks. The inherited branch length threshold is 100 µm and curvature ratio limit is 0.12. Several fragments of one trunk are not necessarily independent anatomical evidence; expose branch overlays and this limitation.

Major retinal vessels connect through the disc region, but local tangents along curved or peripheral branches need not point to the disc center. Convergence is a soft constraint, never a requirement that all vessels be radial. A center alone cannot determine rotation or establish shared tissue. Do not use inferred convergence to bridge disconnected components.

Keep ONH localization status separate from relative registration status. ONH disagreement must be reported for review without automatically destroying an otherwise vessel-consistent component. Registration loop disagreement does withhold a component from accepted mosaics. Adapt the old localization wrapper as needed to maintain this separation, documenting and testing that change.

## Execution, coordinates, and outputs

Provide `python -m octa_reg_v1 inventory|run|report` from the `code` directory, with `--output`, `--inventory`, and `--vessel-export` overrides. Add release launchers `RUN_OR_RESUME.cmd` and `OPEN_GALLERY.cmd`; activate `octa` before invoking Python. Never call the conda environment's interpreter without activation.

Compute all same-eye candidate pairs, prioritizing same-session pairs before across-date pairs. Keep a record for pairs involving excluded/blocked scans rather than losing them from the denominator. Currently 3,695 is the candidate universe before these exclusions, not a promise of 3,695 fitted transforms.

Save per-scan preparation and per-pair results atomically with source, code, and configuration hashes. Continue past isolated input/pair failures. Resume matching artifacts only; regenerate components/reports when upstream pair results change. Use one writer and at most two compute workers by default. Record elapsed time, progress, errors, and a final complete/complete-with-blocked-inputs/failed status; do not equate completion with registration success.

Construct components from passing vessel-supported matches using the existing forest approach. Check non-tree connections and flag inconsistent components. Leave disconnected components independently positioned; never tile them as if their mutual anatomical placement were known. Preserve singletons.

Save 3×3 native-physical-to-component transforms and inverses, pixel spacing, reference scan, component ID, transformed image footprints, and pair directions. Include the pixel-to-physical conversion explicitly and test composition. Keep anatomical directions unknown. Reserve a separate optional component-to-fundus reference transform so future fundus images/notes can add orientation and localization without changing native data.

Deliver:

- A frozen input/configuration manifest and acquisition inventory, including selected mask provenance, review state, fallback source, exclusions, and missing data.
- Per-pair transforms and diagnostics: feature matches/inliers, residual, overlap, vessel Dice, structural correlation, junction count/error, cycle disagreement, runtime, and rejection/block reasons. Call passing results automatic proposals, not human-verified registrations.
- Component transforms/footprints and separate ONH localization/proposal records.
- A local offline gallery: animal/eye/component navigation, date filters, structural/OCTA switch, original scan outlines/IDs, selected vessel/ONH overlays, pair alpha/flicker comparisons, junction/centerline display, and visible provenance/status. Clicking a footprint or point must identify the originating scan and native B-scan/A-line coordinate. Excluded and unresolved acquisitions remain discoverable.
- Mosaics per session and across-date coordinate maps, with imagery kept date-specific. Do not average lesion evolution across visits, interpolate unobserved retina, or hide registration seams behind seamless blending. Diagnostic inconsistent mosaics must be visibly flagged.
- `START_HERE.md` and `RUN_REPORT.md` with actual counts, coverage, runtime, representative successes/failures, limitations, and prioritized next improvements.

## CNV integration later

Default configuration is `cnv_mode: off`. Do not read historical CNV masks, choose between v9 models, use CNV predictions to fit transforms, exclude possible lesions from this first run, or delay the run for CNV review. Explicitly record that lesion-related structural features can still influence the current descriptors despite vessel gating.

Document a future adapter contract accepting scan ID, source identity, native mask/grid, model/review provenance, revision/hash, and coverage/unknown status from `outputs/octa-auto_cnv_v9` or its later verified export. Import final policy-aware masks when available, not gallery display thresholds or browser preferences. Preserve a slot in the input signature for an optional CNV snapshot; do not implement speculative v9 parsing now.

Later, CNV masks can be overlaid in registered coordinates and tested as exclusions from alignment to assess lesion-induced bias. This must be a separately versioned comparison against the saved vessel-only baseline. Do not use evolving lesions as primary across-date landmarks, propagate lesion masks into other dates, or treat missing masks as lesion absence.

## Verification and completion

Run meaningful existing geometry tests without invoking the heavyweight atlas CLI. Add targeted tests for the new adapter, source precedence/empty masks, fallback-only-for-missing behavior, hash/grid mismatch, exclusions, and missing/uncertain ONH. Test rigid transform recovery, unequal pixel spacing, inversion/composition, no overlap, empty masks, singleton/disconnected components, loop inconsistency, and the separation of ONH uncertainty from registration validity. Verify the inherited matcher returns identical results for identical arrays/settings.

Test resume and invalidation after changed input hashes, and ensure per-pair exceptions are recorded without aborting unrelated eyes. Verify no annotation or upstream model files are changed. Check gallery coordinate mapping using known landmarks and visually inspect actual overlap and failure panels.

After a bounded smoke run on one eye, execute the full eligible cohort automatically. Report primary-export versus fallback performance separately, as well as review-state and within-/across-session breakdowns. Do not silently tune the baseline after inspecting results.

Prepare a human-review queue containing the highest-, median-, and lowest-Dice passing pairs per eye, deduplicated, plus examples of each failure reason. Include independent landmark locations to be annotated later; do not fabricate human accuracy measurements. Residuals, Dice, and loops are internal support measures only.

Success means a reproducible completed experiment with every acquisition and candidate pair accounted for, inspectable transforms/mosaics, preserved originals, and clear failure analysis. It does not require forcing all scans into one component. Finish by opening the gallery and reporting where results live, how many scans connected, what remains unresolved, and whether the next measured improvement should target masks, curved-vessel/topology matching, ONH localization, motion artifacts, or global optimization.
