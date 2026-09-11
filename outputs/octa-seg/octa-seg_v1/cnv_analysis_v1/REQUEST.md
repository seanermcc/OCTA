# CNV thickness analysis: spatial and longitudinal

## Summary and staged runs

Build two analysis families—distance from CNV and change over time—with separate manual-mask and automatic-mask releases.

- **v1:** Run after the full octa-seg batch passes `FINAL_VERIFIED.json`, using your manually labeled CNVs.
- **v2:** Rerun when `octa-auto_cnv_v1` outputs are ready, using automatic **candidate cores**. Include broader thinning footprints as a sensitivity comparison.
- Save under `outputs/octa-seg/octa-seg_v1/cnv_analysis_v1/` and `cnv_analysis_v2/`. Preserve v1.
- Use the same frozen thickness inputs and analysis settings for both releases so differences primarily reflect CNV labeling. Report matched-scan comparisons separately from expanded coverage.
- The automatic workflow currently starts with TS267. Report its actual coverage and extend v2 as additional animals become available; do not describe a pilot as a complete cohort.

Each release gets one numbered `fig/` folder, one `FIGURE_CAPTIONS.md`, numerical tables, maps, registration records, configuration, and a reproducibility manifest.

## Measurements and distance analysis

Use octa-thick’s current `exclude_unreliable_um` policy and eight measurements: full retina, RNFL, GCL, IPL, INL, OPL, photoreceptor composite, and RPE band. Full retina is ILM to outer RPE edge; isolated ONL is unavailable. Keep experimental measurement status explicit.

**Distance definition:** For each lesion, calculate equivalent-area diameter, \(D=2\sqrt{A/\pi}\), using physical pixel dimensions. Measure shortest distance outward from its actual outline.

Report the lesion interior separately, followed by six bands:

| Band | Distance beyond lesion edge |
|---|---|
| 1 | 0–0.5D |
| 2 | 0.5–1D |
| 3 | 1–1.5D |
| 4 | 1.5–2D |
| 5 | 2–2.5D |
| 6 | 2.5–3D |

- Calculate arithmetic mean thickness and available area for every lesion, visit, layer, and band. Retain distances in µm as well.
- Preserve shadow, exclusion, unreliable-endpoint, and invalid-geometry NaNs. Do not remove tissue merely because it is unusually thin or thick.
- Exclude other lesion interiors and ONH tissue from surrounding bands. Where bands overlap, assign tissue to the nearest lesion edge in physical distance; record the lost/shared area.
- Recover clipped lesion outlines through verified same-session overlap when possible. Otherwise flag diameter as incomplete and exclude that lesion from normalized-distance summaries; retain available absolute-distance measurements.
- Report field-of-view coverage and valid measurement coverage separately. Mark partial bands visibly, leave empty bands blank, and provide a complete-band sensitivity summary.

**Figures:**

- Per-animal, all-layer thickness-versus-distance figures pooling every eligible **post-D0** visit.
- Corresponding cohort summaries with equal animal weighting.
- Layer-by-distance heatmaps and concentric-ring summary maps, explicitly labeled as schematic averages.
- Observed lesion-centered spatial maps, normalized by diameter, with accompanying coverage maps. Preserve angular information only where alignment is supported.

Average repeat observations within each lesion/visit, visits within tracked lesions, lesions within eyes, and eyes within animals. Average animals equally for cohort summaries. Show contributing animals, lesions, and visits; use animal-cluster bootstrap intervals for cohort uncertainty. Unmatched observations remain visible but are excluded from summaries requiring unique lesion identity.

## ONH location and longitudinal analysis

**ONH and orientation**

Share the control-map approach: fit visible ONH outlines/edges, transfer coordinates through verified same-eye registration, then estimate off-image ONH position from independent vessel-branch convergence.

- Use rigid translation/rotation with physical scale preserved. Match vessels and structural features while masking lesions and artifacts.
- Store localization uncertainty, registration diagnostics, and editable alignment separately from source annotations.
- Provisionally use image N/S/E/W → **D*/V*/N*/T***, with the provisional-orientation explanation on anatomical figures. Propagate alignment consistently through registered scans.
- Ambiguous localization remains unavailable for ONH analyses while retaining local CNV measurements.

Produce all-layer thickness versus **lesion-centroid distance from ONH center**, separated by distance band, and thickness by lesion DVNT sector. Also produce an ONH-centered map of lesion locations colored by surrounding thickness. These are descriptive associations; retain day, lesion size, and eye in the underlying tables.

**Longitudinal figures**

Track lesions within each animal and eye using registered location and footprint agreement. Save proposed identities and registration overlays for correction. Flag ambiguous matches, splits, and mergers rather than silently joining trajectories.

Produce both:

1. **Fixed tissue:** Anchor each lesion to its first usable post-laser footprint and diameter, then transfer those regions to registered visits.
2. **Changing lesion:** Recalculate footprint, diameter, and bands independently at each labeled visit.

Sample thickness in native grids by transforming region coordinates; do not smooth thickness maps or fill absent measurements.

For each animal and region definition, create:

- **Full-retina figure:** day on x, thickness in µm on y; separate panels for lesion interior and six bands. Show every lesion–visit mean and an animal mean line, balancing eyes.
- **Other-layer figure:** the same panels with seven colored layer-mean lines, without individual points.

Fixed-region plots may include registered visits without a new lesion outline; changing-lesion plots require a visit-specific mask. Missing detections do not establish lesion disappearance. Show contributing lesion counts so changing coverage is apparent.

Use actual `days_post_laser` where known; otherwise label days as nominal. Do not convert “6mo” to an invented day number. Display such visits categorically until timing is established. Include registered D0/prelaser observations separately when available, without assuming D0 is prelaser.

## Implementation, provenance, and validation

Add a resumable analysis runner with `inventory`, `register`, `measure`, `figures`, and `run` stages, parameterized by release and annotation source. Completion checks gate v1 and v2 independently.

- Read existing manual footprints and later GUI classifications with revision provenance. Explicit “Normal” or “Other” reclassification overrides an inherited CNV outline; missing review is not absence.
- Keep automatic proposals, assisted proposals, and human corrections distinguishable. Never write human annotation files from analysis scripts.
- Export one row per lesion–visit–layer–band, including identities, day basis, mask source, diameter, mean thickness, coverage, registration state, and measurement revision.
- Flag prelaser scans containing CNV annotations for review; exclude them from post-D0 pooling.
- Record that automatic cores depend partly on thickness, so v2 thickness patterns are not independent validation of lesion detection.

Validate irregular and circular lesions, exact bin boundaries, physical calibration, overlapping bands, clipped fields, missing layers, known image transforms, failed matches, and duplicate scans. Confirm that extra repeats do not increase an animal’s cohort weight.

Check real measurements against octa-thick, inspect registration and ring overlays, and verify every numbered figure against its table and caption. Source annotations and segmentation outputs must remain unchanged.

## Additional analyses to consider next

- **Change from prelaser baseline:** absolute and percentage thickness change in registered tissue.
- **Distance of recovery:** where surrounding thickness approaches a supported local reference.
- **Lesion size versus surrounding effect:** whether larger lesions accompany broader or deeper thickness changes.
- **Directional asymmetry:** ONH-facing versus ONH-away tissue around the same CNV.
- **Layer contributions:** which layers account for full-retina thinning or thickening.
- **Lesion interactions:** isolated CNVs versus neighboring lesions with overlapping surroundings.

The first release focuses on thickness. Vessel density remains a separate follow-up.
