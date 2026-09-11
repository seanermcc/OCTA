# octa-auto_cnv_v3

Implemented on all 17 selected TS267 acquisitions. **29 proposals**, down from **220** in v2; each acquisition has **0–4**, with no forced minimum. Location agreement against the existing D7/D28 manual components is **6/7 within 75 um** using candidate cores alone. One lower D7 manual location remains missed; review it rather than treating the new rules as validated. D14 A-line 85 / B-scan 230 remains a proposed focus despite unavailable thickness. Default background is sufficient on **17/17** scans.

## Open and use

**OPEN_OCTA_AUTO_CNV_V3.cmd** opens the integrated GUI. Saved manual outlines are cyan and selectable in the new **Saved manual** dropdown. **OPEN_SAVED_MANUAL_D7.cmd** jumps directly to existing D7 work. **OPEN_MANUAL_REVIEW.cmd** starts D14 with automatic proposals hidden for new drawings. See **MANUAL_ANNOTATIONS.md** for all six TS267 annotation files and where new work saves.

Paint, erase, redraw, split/merge, approval/rejection, undo/redo and revision checking remain integrated. Structural footprints, candidate cores and numerical contours remain separate. The **Excluded / extra evidence (not CNV)** switch exposes screened shapes and geometry failures, with reasons at the cursor; it is off by default. Those outlines are not presented as CNVs. Geometry alone cannot create a primary CNV proposal. No view is labeled OCTA because no actual OCTA projection was loaded.

## Revised rules

- Require a compact round or roughly oval focus: area >=250 native pixels, equivalent diameter <=120 pixels (~342 um), axis ratio <=2, solidity >=0.70, and Crofton circularity >=0.48. These exploratory thresholds need manual calibration.
- Favor spaces between major vessel trunks. Long connected vessel structures are separated from compact islands in the upstream vessel mask, because some small lesion-like islands were themselves labeled as vessels. A focus cannot be centered on a trunk corridor; trunk overlap is limited to 12%. This does not establish vascular anatomy from a mask.
- Require structural corroboration: at least half the focus exceeds the local structural-departure threshold. Geometry failures, automatic trace loss, and local measured thickness departures remain supporting evidence. Background support never enters detection.
- Reject diffuse, elongated, weakly supported and clipped shapes from the main list; preserve them separately for inspection. Field-edge candidates have uncertain roundness and may require manual addition.
- Nearby fragments can join only across <=50 um gaps when the inferred envelope remains rounded, compact, and off trunks. The envelope is an editing proposal, not an anatomical border.
- Typically expect 1–2 lesions; show at most four qualifying foci in the main queue. Any additional qualifying focus is explicitly retained as extra evidence, rather than silently labeled absent. No scan is assigned lesions merely to reach an expected count.

This reduces review burden but can miss small, clipped or irregular true lesions. More coverage made v2's 7/7 location figure misleading; v3 reports candidate-core area and tolerance coverage alongside hits. Sparse manual components are not confirmed independent lesion counts, and uncertain manual borders are not exact ground truth. Nominal D0 is not a confirmed negative. A saved D98 OS reviewed absence exists on repeat 5, outside this pilot's repeat 1; no performance claim is transferred across that mismatch.

## Measurement and provenance

Full retina remains ILM to outer RPE edge ×1.12 um/pixel. Signed deficit remains 100×(reference−measured)/reference. Native coordinates, missing values, vessel/shadow exclusions, six background variants and assisted-recomputation provenance are preserved. Quantitative areas describe supported measured pixels, not recovered tissue or complete lesion area.

Frozen v2 input arrays are reused with source hashes checked; v2 detector outputs and human CNV masks do not enter the v3 rules. Current matching manual annotations are read only for comparison. V1/v2 implementation and labels remain untouched. New human annotations are written only by GUI actions under this v3 folder. Automatic-seeded reviews are distinguished from newly hand-drawn reference regions. These rules were developed on TS267 examples; the upstream segmentation model also trained on TS267. Other animals remain reserved for subsequent detector evaluation. No visits are registered and no longitudinal lesion-change claim is made.

## Results and review next

`summary.csv`, `candidates.csv`, `screened_evidence.csv`, `sensitivity.csv`, `manual_location_comparison.csv` and per-scan maps/provenance contain the numerical results. `REVIEW_ATLAS.html` shows examples. `verification/` contains synthetic, editing, native-coordinate and saved-array checks. Run **RUN_PILOT.cmd** to recompute, and **VERIFY.cmd** for verification.

A few new manual examples would now be useful: D14, the missed lower D7 region, and genuine vessel/edge negatives. Draw without automatic footprints visible when possible. Review D7's five saved components as well: they exceed the usual count expectation and should not be silently collapsed into assumed lesion counts.

| Scan | v2 | v3 | Manual locations hit/available | Background support |
|---|---:|---:|---:|---:|
| TS267_OD_2025-02-19_D0_s02_112013 | 20 | 2 | 0/0 | 25.1% |
| TS267_OS_2025-02-19_D0_s01_113115 | 4 | 1 | 0/0 | 47.8% |
| TS267_OD_2025-02-26_D7_s01_102519 | 18 | 4 | 4/5 | 56.5% |
| TS267_OS_2025-02-26_D7_s01_104111 | 8 | 1 | 0/0 | 58.0% |
| TS267_OD_2025-03-05_D14_s01_104048 | 9 | 3 | 0/0 | 34.3% |
| TS267_OS_2025-03-05_D14_s01_110309 | 22 | 0 | 0/0 | 57.9% |
| TS267_OD_2025-03-19_D28_s01_101503 | 12 | 2 | 2/2 | 36.8% |
| TS267_OS_2025-03-19_D28_s01_103036 | 15 | 1 | 0/0 | 53.3% |
| TS267_OD_2025-03-26_D35_s01_101127 | 12 | 0 | 0/0 | 21.0% |
| TS267_OS_2025-03-26_D35_s01_103011 | 7 | 1 | 0/0 | 55.9% |
| TS267_OD_2025-04-02_D42_s01_102101 | 10 | 1 | 0/0 | 13.5% |
| TS267_OS_2025-04-02_D42_s01_103648 | 17 | 1 | 0/0 | 57.6% |
| TS267_OD_2025-04-09_D49_s01_101649 | 12 | 3 | 0/0 | 20.2% |
| TS267_OS_2025-04-09_D49_s01_103712 | 8 | 2 | 0/0 | 51.8% |
| TS267_OD_2025-04-16_D56_s01_100746 | 13 | 3 | 0/0 | 31.5% |
| TS267_OD_2025-05-26_D98_s01_105602 | 19 | 3 | 0/0 | 37.5% |
| TS267_OS_2025-05-26_D98_s01_112209 | 14 | 1 | 0/0 | 58.0% |
