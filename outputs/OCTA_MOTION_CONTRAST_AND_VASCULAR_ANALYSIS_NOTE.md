# OCT structural signal, stored OCTA motion contrast, and vascular analysis

Updated: 2026-09-03

## Bottom line

The processed volumes contain a structural OCT channel (`frame_3DAvg`) and a
stored OCTA-style motion-contrast channel (`frame_OCTAAvg`). The latter is
generated from differences between repeated, phase-corrected B-scans and is
therefore sensitive to moving blood cells. It is **not** a direct measurement
of blood-flow speed, direction, volume, or perfusion.

For this project, the stored OCTA channel must presently be treated as an
unvalidated secondary contrast channel, not as confirmed vascular flow or CNV
perfusion. Structural OCT remains the primary evidence for anatomy, CNV
footprints, and retinal-layer boundaries.

## What is in each processed volume

| Channel | MATLAB/HDF5 field | What it represents |
|---|---|---|
| Structural OCT | `frame_3DAvg` | Aligned, averaged OCT backscatter amplitude: tissue morphology and anatomical boundaries. |
| Stored OCTA | `frame_OCTAAvg` | Aligned, averaged magnitude of signal change across repeated phase-corrected B-scans: motion contrast. |

The MATLAB processing function `OCTA_Processing_Lisa.m` phase-corrects each
repeat, forms `frame_s1 - frame_s2`, takes its magnitude, and averages the
repeat-pair differences. `avgVols.m` then aligns and averages the resulting
structural and OCTA volumes across repeated volumes. Thus static tissue should
produce less OCTA contrast than rapidly changing signal, but residual motion,
registration error, shadow changes, low SNR, and other non-blood effects can
also produce contrast.

## What the visual checks showed

Two paired comparisons use the same nine processed volumes, selected near the
95th/90th/85th, 55th/50th/45th, and 15th/10th/5th percentiles of the existing
structural/acquisition QC score:

- [En-face structural OCT vs stored OCTA](figures/structural_vs_octa_qc_tiers.png)
- [Middle-B-scan structural OCT vs stored OCTA](figures/structural_vs_octa_middle_bscans_qc_tiers.png)

Both figures use the raw stored channel with simple per-panel display scaling;
no vessel enhancement, segmentation-derived slab, or flow map is applied. The
stored OCTA image is visibly different from structural OCT, but it also retains
strong effects from large vessel shadows, stripes/speckle, and acquisition
quality. These comparisons do **not** establish that a bright region is a
vessel or CNV.

The QC strata are structural/acquisition QC strata. They are not OCTA-quality
labels and must not be reported as such.

## Rules for current CNV work

1. Draw the CNV footprint from the combined en-face evidence, with structural
   OCT as the primary source. Do not call a footprint a flow area or define it
   from stored OCTA brightness alone.
2. Use the stored OCTA panel as a contextual clue only: record uncertainty in
   the annotation notes when it conflicts with structural anatomy.
3. Do not use stored OCTA to place a retinal-layer boundary. Surface edits,
   visible/not-visible decisions, and exclusions remain structural-OCT
   decisions.
4. Do not train a model to predict CNV flow or report vascular density,
   vascular area, or perfusion from this channel until it is validated.

## What would be needed before a vascular claim

Validation should be planned as a separate analysis, not folded into the CNV
footprint task. A reasonable first study would:

1. Define a reproducible retinal slab or depth range appropriate to the
   vascular question, rather than averaging the entire retinal depth.
2. Compare stored-OCTA patterns with independently identifiable vessels and
   matched structural shadows in a small, representative set of animals and
   days.
3. Quantify repeatability across same-session repeats after registration.
4. Test whether candidate metrics distinguish vessel signal from shadow,
   motion, and low-signal artifacts.
5. Hold out whole animals for evaluation. Do not split random B-scans from the
   same animal between development and validation.

Until that work is complete, describe `frame_OCTAAvg` as **stored OCTA
motion contrast**, not as blood flow.
