# octa-auto_cnv_v2 — integrated lesion review

All 17 selected TS267 acquisitions processed and verified. Experimental development pilot; human candidate review remains pending.

Open **OPEN_OCTA_AUTO_CNV_V2.cmd**. One window provides structural en face, geometry/structural evidence, selectable quantitative maps, and native B-scans with the established boundary editor. **RUN_PILOT.cmd --resume** resumes processing. **VERIFY.cmd** runs synthetic GUI/scientific tests and the saved-data audit. All v2 writes stay here.

## Measured result and limitations

- Location agreement: **7/7** reviewed manual-mask components within 75 um, versus **0/7** in v1. D7: 5/5; D28: 2/2. Components may be disconnected fragments of one lesion, not distinct lesions. Borders are approximate.
- D14 A-line 85 / B-scan 230 is now candidate **7**, despite unavailable thickness and no default reference support. No coordinate-specific rule or human annotation was created.
- Review burden: **220 candidates**, versus 13 in v1; 77 explicitly uncertain/artifact challenges. Several large candidates follow vessels or field artifacts. More coverage can itself improve location agreement: candidate and 75-um tolerance field fractions are reported for every scan. This is not validated sensitivity or precision.
- **8/17 default background fits are insufficient** after candidate/halo exclusion. Other scans can have supported background elsewhere while the candidate itself has no measurable deficit. A zero observed supported footprint is not a zero lesion area. Missing or unsupported regions never count as zero deficit.
- There are **no reviewed-normal pixels** in this pilot reference set. False-candidate performance and review rejection rate are unavailable until genuine review occurs. D0 is a challenge, not a confirmed negative.

## D14 structural inspection

The raw neural ILM crosses RNFL/GCL by 13.76 px; INL/OPL crosses OPL/ONL by 50.25 px; PR/RPE crosses outer RPE by 10.36 px at the supplied point. These are crossings, not nonfinite or out-of-crop positions. ILM and outer RPE fail because they cross intermediate surfaces, even though ILM remains above outer RPE. Vessel, shadow, low-signal, and automatic trace-loss flags are absent at this point.

Linked native B-scans 227, 230 and 233 show a localized disturbance of retinal band structure with unstable inner and outer neural traces. The appearance persists across the neighborhood, so it merits lesion review; neural curves are visibly unreliable there and do not establish lesion anatomy or recovered tissue thickness. See `verification/D14_linked_bscans.png` and `verification/D14_regression.json`.

## How to review

1. Select a candidate on a map or in the region list. Orange is the immutable automatic core; cyan is the existing manual comparison. Inspect the linked B-scans and reason panel. Use scan/B-scan selectors or native-map clicks; the same crosshair is shared.
2. Choose **Structural footprint** or **Candidate core**. Draw region adds a missed region; Redraw replaces the selected target. Paint/Erase use the established round brush; Split by stroke cuts a structural region into components. Core cutting preserves the structural footprint. Merge with joins selected regions. Undo/Redo retain masks, decisions and edit provenance.
3. **Approve footprint** explicitly approves the current structural footprint as Full Lesion. For Normal/Other, choose the category (explain Other), then **Complete region review**. Changing a category alone stays a draft. **Reject candidate** retains its original seed and rejection record. No action labels tissue outside the reviewed region.
4. Save all or Ctrl+S; scan changes and closing also save actual edits. Opening, navigating, selecting, or switching map variants writes no annotations. Reload saved supports resolving disk conflicts; a changed automatic seed is blocked for explicit reconciliation rather than transferring old approvals.
5. Select background variants to inspect 10/20/30% contours, reference sensitivity, and sample/support regions. The automatic core list cannot change. **Recompute assisted from reviewed footprints** uses current saved boundary corrections and footprint decisions: rejected/Normal regions stop excluding background, approved lesions add exclusions. Its candidate output remains the original automatic set. Assistance hashes and measurements are saved separately under `assisted_review/`; unchanged saved assisted results reload, stale ones are not reused.

Numeric contours, candidate cores and structural footprints are independent. Painting a footprint never changes a numerical contour. Quantitative recomputation is explicit and assisted. Pink outlines indicate missing thickness, blue vessel/shadow, lavender selected uncertain margins, mustard low signal, and gray reference-support edges. Clipping is reported per candidate. The background map includes explicitly labeled extrapolations; these never enter supported deficits or area summaries. No actual OCTA projection is loaded, so no view is labeled OCTA.

## Method and measurement contract

First-stage evidence uses every pair of eight raw neural boundaries, with exact crossing masks and violation sizes plus per-boundary nonfinite/out-of-crop masks. Connected geometry/automatic-trace loss, structural departures (robust local en-face residual), and measurable local thickness departures form interpretable proposals. Two-pixel closing connects fragments only for candidate geometry; a proposal requires at least 24 observed pixels over at least three B-scans. Isolated failures remain available as evidence. Geometry requires neither thinning nor structural confirmation to remain a tentative candidate. Vessel/shadow, low signal and row-seam evidence affect priority, never erase a candidate. A structural-only alternative uses z>=4; z>=2.5 with >=12 um local measured departure is another alternative. These are exploratory thresholds, not calibrated diagnostic probabilities. Closing can join adjacent abnormalities and vessel artifacts; split/merge review is essential.

Afterward, candidates and 90/150/210 um halos are excluded from background sampling. The preserved robust tile-quantile plane/quadratic fitter additionally excludes coherent low residual areas. Local coverage in at least three quadrants and >=8% of a 350 um neighborhood replaces v1's tile-center convex-hull support. Minimum fit sample fraction remains 8%, with sufficient populated tiles. This conservative rule often sacrifices measurements; a broad smooth halo can still contaminate a fitted reference. Six variants measure sensitivity to halo size, tile quantile and polynomial choice, not statistical uncertainty. Shared thinning footprints are possible and should not be summed as independent lesions.

Full retina is exactly **ILM to outer RPE edge ×1.12 um/pixel**, unchanged from v1. Signed deficit is **100 × (expected background − measured thickness) / expected background**. All maps retain native [B-scan,A-line] coordinates; lateral scale is approximately 1460/512 um per pixel. Missing measurements, shadows and unsupported estimates remain unavailable. Vessel and low-signal pixels are also excluded from quantitative deficit summaries. A fitted background is not recovered tissue. Supported observed contour/footprint area is partial coverage, not total anatomical lesion area.

The automatic branch removes target-specific position edits, human state denials and regional feedback where separable, retaining frozen neural predictions and automatic acquisition masks. Automatic geometry and human-assisted missingness are distinct. Upstream ALL_LABELLED segmentation training includes **TS267**; vessel context may include manual assistance. This is not independent detector validation. Other animals remain reserved for subsequent detector evaluation, distinct from their pre-existing upstream segmentation training exposure. No visits are registered and no longitudinal lesion-change claim is made. Day labels remain nominal.

## Files and next step

- `summary.csv`: v1/v2 location agreement, review burden, field coverage and reference availability.
- `candidates.csv`: native candidate locations, persistence, artifact fractions, boundary failures and measurable core coverage.
- `manual_location_comparison.csv`: per-component location agreement without treating borders as exact truth.
- `sensitivity.csv`: six reference variants, supported observed contour areas, common-support agreement and deficit changes.
- `scans/<scan>/maps.npz`, `provenance.json`, `overview.png`: automatic and clearly prefixed assisted results, masks, source hashes and images.
- `review/regions`: RegionStore-compatible human GUI records with draft category, edited-pixel runs, separate core runs, explicit reviewed/unreviewed runs, seed hashes and revision history. `review/surface_labels` uses the existing embedded boundary GUI. No old labels or released models are modified.
- `verification`: scientific/GUI tests, all-17 native and missing-data checks, D14 evidence, GUI captures, and v1 source-hash preservation.

**Next review:** inspect D14 candidate 7 first, then D7/D28 manual locations, D0 candidates, and broad vessel/seam candidates. Reject artifacts, inspect uncertain/clipped margins, approve only the footprint actually reviewed, then recompute the assisted reference. Do not use automatic proposal pixels as ground truth or report complete lesion area from the partial quantitative maps.

| Scan | v1 candidates | v2 candidates | Locations hit/available | Default support | Observed footprint mm² |
|---|---:|---:|---:|---:|---:|
| TS267_OD_2025-02-19_D0_s02_112013 | 2 | 20 | 0/0 | 0.0% | unavailable |
| TS267_OS_2025-02-19_D0_s01_113115 | 0 | 4 | 0/0 | 16.1% | 0.00002 |
| TS267_OD_2025-02-26_D7_s01_102519 | 0 | 18 | 5/5 | 0.0% | unavailable |
| TS267_OS_2025-02-26_D7_s01_104111 | 0 | 8 | 0/0 | 45.0% | 0.00001 |
| TS267_OD_2025-03-05_D14_s01_104048 | 1 | 9 | 0/0 | 0.0% | unavailable |
| TS267_OS_2025-03-05_D14_s01_110309 | 0 | 22 | 0/0 | 27.4% | 0.00000 |
| TS267_OD_2025-03-19_D28_s01_101503 | 0 | 12 | 2/2 | 23.4% | 0.00000 |
| TS267_OS_2025-03-19_D28_s01_103036 | 0 | 15 | 0/0 | 41.4% | 0.00000 |
| TS267_OD_2025-03-26_D35_s01_101127 | 3 | 12 | 0/0 | 0.0% | unavailable |
| TS267_OS_2025-03-26_D35_s01_103011 | 0 | 7 | 0/0 | 41.3% | 0.00000 |
| TS267_OD_2025-04-02_D42_s01_102101 | 3 | 10 | 0/0 | 0.0% | unavailable |
| TS267_OS_2025-04-02_D42_s01_103648 | 0 | 17 | 0/0 | 27.8% | 0.00006 |
| TS267_OD_2025-04-09_D49_s01_101649 | 2 | 12 | 0/0 | 0.0% | unavailable |
| TS267_OS_2025-04-09_D49_s01_103712 | 0 | 8 | 0/0 | 32.1% | 0.00000 |
| TS267_OD_2025-04-16_D56_s01_100746 | 2 | 13 | 0/0 | 0.0% | unavailable |
| TS267_OD_2025-05-26_D98_s01_105602 | 0 | 19 | 0/0 | 0.0% | unavailable |
| TS267_OS_2025-05-26_D98_s01_112209 | 0 | 14 | 0/0 | 44.8% | 0.00088 |
