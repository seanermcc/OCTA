This analysis reads completed octa-thick exports and saved annotations. It never
changes segmentation, model parameters, or human labels. By default, cohort analysis
requires the batch's successful `FINAL_VERIFIED.json`; an existing `COMPLETE.json`
is insufficient. The user-authorized `--skip-batch-audit` option starts from the
completed exports without that cohort audit. It records `skipped_by_user` in the
manifest and run status, and retains per-export input-integrity checks.

Open [figures](fig/), [ordered captions](fig/FIGURE_CAPTIONS.md),
[configuration](config.json), [manifest and figure/data mapping](manifest.json),
[tables](tables/), [native maps](maps/), [registration](registration/),
[validation](qc/), and [run status](logs/run_status.json).

Run `RUN_CONTROL_MAP_V1.cmd run --wait` to wait for final batch verification and
then process or resume. `run` alone fails immediately if the gate is absent;
`test` runs synthetic implementation checks; `audit-figures` checks the registry.
For the user-authorized unaudited run, use
`RUN_CONTROL_MAP_V1.cmd run --skip-batch-audit`. All required acquisition files must
exist; this option never manufactures an audit marker or calls unaudited data verified.
The launcher activates the octa environment. Only one atlas worker may run at a time.
Two acquisitions are prepared concurrently by default (`scan_workers`); this is
configurable. Exact masked neighborhood median/MAD calculations are expensive:
a synthetic 512×512 full-grid screen with the default 500 µm neighborhood took
171 seconds on this workstation during implementation. There are two candidate
screens and one B screen per acquisition. This is a resumable analysis that can
take many hours; the timing is computational, not a quality measurement.

Configuration is saved before work begins. Edits invalidate affected stages through
configuration, code, and full-file input hashes. Preparation, same-eye registration,
and each eye's summaries have independently verified artifact markers. Figure and
cohort summaries are rebuilt deterministically after those stages. Interrupted files
are replaced atomically; incomplete stages rerun. A stale worker lock is never
silently removed. Inspect its PID before removing `logs/atlas.lock` after a crash.

All eight existing measurements are retained, including unavailable rows. **Full
retina is ILM→RPE**, and the **photoreceptor composite includes ONL**. Neither
isolated ONL nor ILM→BM is created. Values come only from `exclude_unreliable_um`;
the available-position pilot policy is preliminary and does not make v1 reliable.
Source metadata, endpoint provenance/reasons, shadow NaNs, native coordinates,
human image exclusions, and upstream geometry restrictions are preserved.

Version A excludes saved and proposed CNV, buffered CNV, major vessels, ONH where
its size is established, and unavailable measurements. Each layer keeps its own
availability. B applies one shared full-retina screen before summarizing any layer:
the default **500 µm diameter** disk uses a masked median and exact neighborhood
MAD; robust SD is max(1.4826×MAD, 1.12 µm), and the threshold is three SD.
At least half the full disk must contain eligible full-retina measurements.
Off-image space counts as unavailable; unresolved B locations remain blank.

CNV clearance is one maximum Feret diameter beyond the lesion edge. Feret spans
the physical pixel-cell corners; dilation is conservatively rasterized with at
most one pixel diagonal excess. A 10 µm diameter lesion therefore gets 10 µm
clearance, not a 10 µm final radius. Vessel clearance is half the diameter estimated
from the nearest major-vessel skeleton radius. The ONH exclusion radius is one
full disc diameter from its center (disc radius plus half-diameter clearance).
Inferred centers supply no size; a visible same-eye estimate may supply it.

Automatic CNV candidates use localized full-retina deviations or outer-composite
deviations, with configurable robust thresholds and minimum physical area. Missing
outer measurements are unavailable evidence, not lesions. Saved outlines and
automatic candidates remain separate bits and arrays. Same-session verified
vessel matches transfer lesion extent and physical buffers. Extent recovery checks
the boundary of the combined observed field; incomplete extents stay flagged.
No lesion mask propagates into earlier dates. Repeat records flag CNV history.

ONH centers use sufficiently long visible edges, followed by transfer through
verified rigid vessel matches, then independent sufficiently straight vessel
branches. Short visible arcs, parallel/curved branch ambiguity, inconsistent
centers/registration loops, and excessive uncertainty remain unresolved. Circle
uncertainty uses spatial arc-block resampling; convergence uses branch resampling.
Rigid transformations are in physical µm and never rescale a scan or optimize
thickness similarity. Structural feature matching near major vessels must pass
overlap, structural correlation, independent branch, and vessel-agreement tests.
Automatic vessel proposals can still contain artifacts; passing these tests is
experimental support, not independent registration ground truth.

Every native pixel retains image x/y, ONH-centered x/y where resolved, continuous
distance, and angle. Image x increases right and y down; angle is 0° right and 90°
up. The configurable provisional image N/S/E/W mapping is D*/V*/N*/T*. Relative
rotations come from vessel registration; disconnected components retain provisional
native axes. Orientation is configuration, not segmentation; correcting it reruns
analysis only. Physical scale uses saved annotation calibration, per-scan configured
overrides if supplied, or the approximate 1,460 µm field. Galvo X500 is never used
as retinal extent.

Native masks remain exact. Atlas display bins default to 25 µm and average only
observed eligible pixels; they do not fill unobserved bins or interpolate across
exclusions. A partly observed bin summarizes its eligible fraction; inspect native
maps for sub-bin holes. Polar tables use 250 µm radial bands and 30° sectors.
Aggregation gives acquisitions equal weight within dates, dates equal weight within
eyes, eyes equal weight within animals, then animals equal weight. Cell-specific
acquisition, eye-date, eye, and animal counts are reported. Summed observed area is
sampling exposure across acquisitions, not a claim of unique retinal area.

Repeated tissue requires verified vessel registration. Pair maps sample the other
acquisition at nearest native pixels without interpolation, preserve all exclusions,
and report overlap, signed B−A difference, SD and range for all measurements and A/B.
Repeated-component tables additionally sample a 25 µm physical point lattice
(not a pooled 25 µm tissue bin). Same-session statistics compare repeats within a
date; across-date statistics compare date means. Registration error limits spatial
identity precision. ONH coordinates alone never establish repeated tissue.

Figures are numbered by inventory, localization/registration, per-eye coverage,
per-eye thickness, cohort composites, repeated tissue, A/B comparisons, then
validation/sensitivity. All figures live in one `fig/` directory. The manifest
records the actual selected scans, sample counts, captions, and data files.

Limitations and validation are separate: localization crop errors use the full-view
edge fit as a reference, not anatomical truth; registration residuals measure matched
features, not external landmark accuracy; missing/unreviewed annotations do not
establish absence; preliminary thickness availability does not establish acquisition
quality. Unlocalized scans remain in inventory and local summaries. CNV and major
vessel proposals require review, and incomplete ONH or lesion exclusions remain
flagged. The name “control map” and B's “locally normal-appearing” screen do not
establish healthy tissue or healthy animals. All dates are included according to
their local exclusions; actual `days_post_laser` is retained.
