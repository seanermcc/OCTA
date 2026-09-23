# BigWarp pilot for the first eight manually reviewed montages

Prepared 2026-09-22. BigWarp source downloaded to `../tools/bigwarp`, commit
`a972209aa6e647f5ff579ddadef4d33b522de074` (pom version 9.4.1-SNAPSHOT).
The checkout is clean. This is a source download, not a built or launched Fiji installation.
No deformable registration has been fitted or applied. Original reviews, images,
masks and existing montages are unchanged; input hashes were verified after export.

## Starting data

The latest completed manual reviews are in **octa-reg_v2/all_samples**, not the
automatic v3 release. Their effective ONH-adjusted placements and categories are
read through `octa_reg_v2.review_server.analysis_inputs` with whole-montage
confirmation required and supported fields only. All categories and notes are
preserved in separate audit snapshots; no approval is assigned to a future warp.

| Eye | Review revision | Supported placed fields | Candidate overlapping pairs |
| --- | ---: | ---: | ---: |
| TS165 OD | 87 | 7 | 21 |
| TS165 OS | 62 | 6 | 6 |
| TS169 OD | 64 | 3 | 3 |
| TS169 OS | 6 | 4 | 6 |
| TS241 OD | 194 | 22 | 188 |
| TS241 OS | 128 | 10 | 16 |
| TS247 OD | 171 | 28 | 348 |
| TS247 OS | 54 | 10 | 37 |

TS250 OD was still unconfirmed and is not included. Later edits require a fresh
snapshot/export. `manifest.json` contains source hashes and exact selected pairs.
Pair selection prefers the same acquisition date, then largest geometric overlap
(at least 25%). These are convenient starting examples, not the eight worst
distortions or an automated judgment that two vessel patterns correspond.

Each eye folder contains one moving/target TIFF pair, validity masks, a red/cyan
baseline overlay, pair geometry and the full list of candidate pairs. TIFFs are
8-bit display-normalized structural projections for landmark work, not quantitative
intensity exports. Moving images are resampled using the saved rigid alignment
into the target native 512 x 512 frame; content outside that frame is clipped for
this pilot. Final montage production must sample original arrays over the full FOV.

## Assessment and proposed experiment

BigWarp is well suited to testing residual geometric mismatch after manual placement.
It is a manual landmark registration tool, not a vessel segmentation model. Better
alignment could reduce doubled vessels in the composite without improving native
vessel masks. A broad vessel can also reflect blur, shadow width, segmentation or
true biological change; narrowing it by warping is not evidence of correctness.

The baseline contact sheet shows remaining offsets in several pairs. This is visual
triage, not a measured deformation diagnosis. For example, TS241 OS has substantial
disagreement and baseline common-pixel intensity correlation of -0.0597. Correlation
is sensitive to illumination and artifacts and does not establish a wrong placement;
verify corresponding branches before using this pair. A residual warp must not be
used to conceal a false vessel correspondence.

1. Begin with one same-date pair, a fixed target and the current manual pose.
   Mark approximately 8-15 identifiable branch points or vessel bends spread across
   the overlap. Avoid lesion edges, straight unidentifiable trunks and image seams.
   Reserve several well-distributed correspondences for independent checks.
2. Compare residual rigid, similarity (uniform scale), affine (axis scale/shear),
   then thin-plate-spline fits to the SAME training landmarks. These are proposed
   experimental models, not a change to the calibrated acquisition pixel size.
   Use the simplest fit that improves the reserved landmarks.
3. Use TPS only if distributed residuals persist. Restrict its influence to supported
   overlap with a smooth mask; inspect the transition and preserve the baseline
   outside supported tissue. Do not extrapolate freely across an entire eye from
   a few points or chain unverified pairwise warps.
4. Measure reserved-landmark errors in pixels and micrometers, independent vessel
   centerline distances, displacement magnitude, Jacobian determinant and local
   stretch. Reject folds (nonpositive determinant), inspect extreme compression,
   and verify neighboring overlaps and the ONH do not worsen. Set acceptable stretch
   limits from pilot evidence rather than inventing a universal threshold.
5. Save the residual transform, landmarks, fit/validation split, direction, coordinate
   units, source revision and before/after previews as a separate unconfirmed draft.
   For cohort work, solve consistent per-field residuals around a fixed reference;
   pair-specific warps alone can give conflicting positions for the same field.

Do not use training-landmark fit error as validation: TPS can interpolate those
landmarks exactly. Across dates, stable vessels should drive the fit; CNV growth
must not be warped away. Keep vessel caliber and CNV area measurements in native
calibrated coordinates. For display, transform all colocated channels and masks
consistently (nearest-neighbor for discrete labels, suitable image interpolation
for intensities); preserve excluded/invalid regions. Quantitative warped areas
would require explicit Jacobian handling and separate validation.

## Open the pilot in Fiji

BigWarp is included in Fiji according to its official documentation. Open
`moving_manual_aligned.tif` and `target.tif` from one eye folder, then use
**Plugins > BigDataViewer > Big Warp**. Select the former as moving and the latter
as target. Both pilot images use pixel units; one target pixel is 2.8515625 um.
Use Space for landmark mode, T to toggle warping, and F2 for the transform model.
Save project/landmarks and exported transformations into a new trial subfolder.
The current download has not been built or tested in Fiji on this workstation.

`pair.json` records the composition: with manual native-to-world matrices M and
residual target-frame warp W, final moving-native coordinates map to world as
`M_target * W(inv(M_target) * M_moving * x)`. Image sampling uses the inverse map.
Verify transform direction with known landmarks; BigWarp's image/coordinate export
terminology is easy to confuse. Do not apply the original rigid transform twice.

The existing browser reviewer accepts only rigid 3x3 matrices. Integration needs
a separate residual-transform record and renderer; inserting a TPS into its current
pose field would violate its contract. No changes to that reviewer were made.

## Sources

- [BigWarp repository](https://github.com/saalfeldlab/bigwarp): downloaded source and license.
- [Official BigWarp documentation](https://imagej.net/plugins/bigwarp): Fiji entry point,
  landmark workflow, transform models, masks and export formats.

The experimental design and OCT-specific interpretation above are recommendations
from this inspection, not claims of validated improvement.
