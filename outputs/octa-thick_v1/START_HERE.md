# Current pilot behavior — updated September 10, 2026

Available saved segmentation positions are assumed usable for this preliminary
analysis. Full-retina thickness uses saved U-Net ILM by default. All boundaries
may use saved model positions where reported/context positions are unavailable.
Direct human strokes take precedence without requiring a training approval.

**Include unreliable measurements** is off by default. It adds positions explicitly
marked unreliable by a human (saved reliability flags or frozen explicit-human
unreliable reason). Model uncertainty/calibration withholding alone does not
exclude a position. Dotted lines and white map stipple identify included unreliable
measurements. Color limits stay fixed when toggling.

Shadows, image exclusions, rejected rows, not-traceable endpoints, and invalid
geometry remain blank in both modes. Source labels and segmentation files are
unchanged. This is an analysis assumption, not a change to ground truth or validation.

NPZ exports now provide `exclude_unreliable_um`, `include_unreliable_um`, and
unreliable endpoint/measurement masks. Legacy array names remain as aliases;
`estimated_mask` now means explicitly unreliable measurements. Metadata records
this revised policy. Point CSV files use a new `_pilot_v2_points.csv` filename.
Previous-policy exports are flagged stale when their scan is loaded.

Current policy tests: `test_policy.py`. Historical strict-policy details below
are retained for reference and no longer describe the default behavior.

---

# octa-thick_v1 — preliminary thickness viewer

Double-click **OPEN_OCTA_THICK_V1.cmd** in this folder. The four completed
octa-seg_v1 volumes are already selected in `volumes.json`.

The application, launcher, configuration, verification results, and exports
are contained here. Existing segmentation and correction applications are
imported read-only from the project. Large source volumes are referenced,
not duplicated. No model training or inference is started.

## Trying the pilot

1. Select a scan. The default full-retina **reported** map is empty because
   the frozen model withheld ILM in all four volumes.
2. Enable **Exploratory preview (estimated)** to use the saved U-Net ILM.
   This is the current model's already-computed position branch, so an older
   U-Net fallback was unnecessary. Dotted boundaries and white map stipple
   indicate estimated positions/measurements.
3. Click either en-face panel to select an exact native B-scan and A-line.
   The lower image follows the selection and highlights the selected layer's
   endpoints. A yellow axial bracket appears where that measurement exists.
4. Select any of the eight measurements. The right panel shows all values,
   endpoint sources, depths, and missing-value explanations at the selected point.
5. Use **Export maps + displayed PNG**, or explicitly **Save this point to CSV**.
   Outputs appear in `exports/`. Numeric exports are not clipped by color limits.

**Open correction GUI** opens the existing octa-seg reviewer for the selected
scan. Its navigation controls select the exact row/column shown in the analysis
viewer. Save corrections there, then use **Reload corrections** here. The analysis
viewer never writes labels. Existing correction files retain their existing location.

## Measurement contract

Native axial endpoint difference × **1.12 µm/pixel**, without smoothing,
resampling, or filling absent data. Full retina is ILM to outer RPE edge.
RNFL, GCL, IPL, INL, OPL, photoreceptor composite, and RPE band use the existing
eight-boundary definitions. Photoreceptor composite includes ONL and other
photoreceptor structures; isolated ONL is unavailable.

Shadows, exclusions, rejected rows, not-traceable endpoints, missing positions,
out-of-crop positions, and crossings remain blank. A withheld internal boundary
does not by itself withhold full-retina thickness. Preview adds eligible saved
context, pending direct human strokes, and raw ILM only. Other raw model
boundaries are never substituted.

Human sources follow the existing reviewer priority: its own surface labels,
then the configured manual source directories in order. Exact strokes with
explicit positive visibility/reliability and position-specific approval events
can replace automatic positions. Legacy whole curves, generic acceptance,
displacement, and software taper are not treated as approved measurements.

Color limits initialize from reported 2nd–98th percentiles, falling back to
preview values only when reporting is empty. They stay fixed for each scan/layer
while navigating, toggling modes, and reloading. Manual changes last for the
current session. Reported mode remains the startup default.

## Pilot limitations

- All automatic positions and measurements are **experimental**, including
  those the frozen model calls reported. These are not validated thickness results.
- Saved contextual candidates are conservatively invalidated over an entire
  changed row and its immediate neighbors. They are never regenerated here.
- Frozen denials remain in force even if an old annotation is removed. Reload
  updates saved edits and judgments but does not rerun the model to restore a
  formerly withheld automatic position.
- Older corrections without a coordinate sidecar use the existing reviewer's
  validated scan identity, boundary naming, and native-grid convention. New
  correction sidecars are checked for source, crop, and orientation compatibility.
- The pilot only accepts completed octa-seg_v1-format volumes. It does not scan
  the whole cohort, register longitudinal visits, draw ROIs, or compute regional statistics.

## Exports and provenance

NPZ contains separate reported/estimated arrays, combined preview arrays,
finite and estimated masks, endpoint positions and source codes, shadow mask,
reason codes, and JSON metadata. Metadata includes units, boundary definitions,
model/checkpoint identity, canonical crop offset, source/correction fingerprints,
and revision identity. PNG records the displayed map and color scale; its JSON
sidecar records display options. Saved-point CSV has a metadata sidecar.

When saved corrections change, previously tracked exports are flagged with
`.stale.json` sidecars. Export again to obtain current results. Each CSV row
carries its own revision; do not combine rows from different revisions silently.

## Verification

- Ten synthetic contract tests passed: units/pairings, masks, raw-ILM isolation,
  exact pixel selection, correction approval/denial/undo, stale context, and map/point agreement.
- Four real volumes passed all-layer, both-mode map/point/NPZ agreement and
  reload checks. **107 protected files**, including cached images, measurement
  artifacts and human annotations, stayed byte-identical.
- Twelve existing reviewer regression tests passed.
- Visual checks cover all four volumes, native measurement brackets, and the
  existing correction GUI startup. See `verification/` for images and reports.

Full-retina reported coverage is 0% on all four scans. Preview finite coverage
at verification was **59.9% (TS165), 76.1% (TS247), 71.3% (TS283), and 65.0% (TS325)**.
Coverage measures availability, not correctness.

For an explicit alternative selection, pass completed volume directories to
`OPEN_OCTA_THICK_V1.cmd`, or use `--list path-to-list.json` with a JSON list of
directories. `--correction-config` selects another compatible reviewer configuration.
