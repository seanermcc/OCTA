# octa-auto_cnv_v1 — TS267 experimental pilot

Completed 17/17 selected longitudinal v2 acquisitions. Outputs and future review are isolated here.

Open **OPEN_OCTA_AUTO_CNV_V1.cmd** for native maps, background selection, selectable 10/20/30% contours, reference sensitivity and linked B-scans. Use **Edit proposals** to open the established region annotation GUI with separate, unclassified automatic seeds. Redraw, remove, or classify a region there; only explicit GUI actions save review. **RUN_PILOT.cmd** reruns this pilot, preserving review files. Maps are frozen snapshots; rerun after upstream corrections change.

## Measurement and method

Full retina exactly preserves the thickness viewer's ILM → outer RPE edge definition, ×1.12 µm/px. Coordinates are native [B-scan,A-line], with no image rotation or resampling. Area uses the approximate 1460 µm field in both directions. Signed deficit is 100 × (reference − thickness) / reference. Missing values remain NaN. Neither a fitted reference nor a missing core is recovered tissue thickness.

The main branch starts from saved neural positions, discards target-specific position corrections, context estimates, human state denials and regional feedback, and retains automatic trace denial, geometry checks and shadows. The separately named assisted branch uses the actual current viewer's default map. Automatic uncertainty is retained as a separate flag: this pilot follows the viewer's preliminary available-position policy, not a validated reliability claim. The viewer does not directly honor v2 regional reason 15 as an unreliability exclusion; that existing behavior is recorded, not changed here.

The reference fits a robust quadratic surface to 48-pixel tile 60th percentiles. It excludes borders, low signal, vessels/shadows plus 25 µm, and iteratively excludes coherent >7% thinning plus a 150 µm buffer. Suspected halos cannot re-enter the reference. At least 8% of pixels and 18 populated tiles are required. Support is confined to the tile-center convex hull and within 350 µm of retained samples. Extrapolated reference values are visible estimates; deficits outside support stay NaN. 0 scans have insufficient background. A broad, smoothly varying halo can still be absorbed by the fit; sensitivity and manual background inspection are essential.

Cores require ≥1600 µm² coherent ≥30% thinning, or clustered automatic trace/invalid-geometry loss (3-pixel connectivity) next to ≥15% thinning, with a local structural departure in at least 10% of core pixels. Vessels, shadows, low signal and borders suppress cores. These heuristic gates can miss lesions, including vessel-crossing and peripheral lesions. Unconfirmed severe regions and clustered loss are retained separately. The footprint is the measurable ≥10% component associated with a core; a 3-pixel closing is used only for connectivity. Missing/vessel gaps are never turned into measured footprint. Multiple cores may share a footprint. Contours are descriptive deficit extents, not CNV anatomy.

Six reference variants vary halo exclusion (90/150/210 µm), tile quantile (50/60/70%), and plane versus quadratic fit. Saved area changes and per-pixel spans are sensitivity measurements, not statistical confidence intervals. Variant-specific support is saved; support differences must be considered when comparing areas.

## Pilot measurements

Location agreement: 0/7 reviewed manual components intersect a proposal within 75 µm. This tolerance measures approximate location agreement, not exact border accuracy. Unreviewed regions are never confirmed negatives. Where reviewed unaffected scans/regions are absent, false-positive performance is unavailable; baseline candidate counts remain review candidates. Other TS267 manual masks on unselected repeat acquisitions were not transferred to this grid.

| Scan | Cores | Footprint mm² | Reference support | Manual locations hit/total |
|---|---:|---:|---:|---:|
| TS267_OD_2025-02-19_D0_s02_112013 | 2 | 0.0576 | 47.1% | 0/0 |
| TS267_OS_2025-02-19_D0_s01_113115 | 0 | 0.0000 | 48.5% | 0/0 |
| TS267_OD_2025-02-26_D7_s01_102519 | 0 | 0.0000 | 65.6% | 0/5 |
| TS267_OS_2025-02-26_D7_s01_104111 | 0 | 0.0000 | 79.6% | 0/0 |
| TS267_OD_2025-03-05_D14_s01_104048 | 1 | 0.0109 | 59.9% | 0/0 |
| TS267_OS_2025-03-05_D14_s01_110309 | 0 | 0.0000 | 67.9% | 0/0 |
| TS267_OD_2025-03-19_D28_s01_101503 | 0 | 0.0000 | 39.6% | 0/2 |
| TS267_OS_2025-03-19_D28_s01_103036 | 0 | 0.0000 | 65.9% | 0/0 |
| TS267_OD_2025-03-26_D35_s01_101127 | 3 | 0.1198 | 55.8% | 0/0 |
| TS267_OS_2025-03-26_D35_s01_103011 | 0 | 0.0000 | 55.2% | 0/0 |
| TS267_OD_2025-04-02_D42_s01_102101 | 3 | 0.0892 | 42.6% | 0/0 |
| TS267_OS_2025-04-02_D42_s01_103648 | 0 | 0.0000 | 74.7% | 0/0 |
| TS267_OD_2025-04-09_D49_s01_101649 | 2 | 0.0309 | 37.3% | 0/0 |
| TS267_OS_2025-04-09_D49_s01_103712 | 0 | 0.0000 | 55.9% | 0/0 |
| TS267_OD_2025-04-16_D56_s01_100746 | 2 | 0.0831 | 45.5% | 0/0 |
| TS267_OD_2025-05-26_D98_s01_105602 | 0 | 0.0000 | 39.3% | 0/0 |
| TS267_OS_2025-05-26_D98_s01_112209 | 0 | 0.0000 | 79.0% | 0/0 |

Every scan has an overview, numerical maps, sensitivity variants, candidates and detailed provenance under `scans/`. Pink missing centers, blue vessel exclusions, gray unsupported reference and zero-candidate/low-support cases are deliberately included as failure examples. See `summary.csv` for apparent misses and reviewed-normal counts.

## Circularity and limitations

No target CNV footprint enters the detector or reference fit. Frozen raw positions match the pre-v2 baseline exactly. Inspection of `octa_seg_v1.predict.one` and v2 inference shows that CNV masks do not enter inference; vessel masks enter the state head. The upstream ALL_LABELLED models were trained on TS267 as well as the other labeled animals. This is a development pilot with training overlap, not independent detection validation or cross-animal performance. Existing manual vessels can still assist the state predictions. Human-derived missing regions may drive the assisted branch and must not be credited as automatic detections.

`provenance.json` records source hashes, original reasons, human guard records and current correction hashes. `unavailable_cause_bits` allows overlapping causes; viewer reason 23 cannot alone distinguish not-visible from image exclusion/rejection, so original guard provenance is retained. No human labels or released models are modified. The three supplied screenshots were inspected as visual background examples; their crop lacks scan IDs, so no scan identity or background training annotation was inferred.

Visits are not registered; no longitudinal lesion change is claimed. Day labels are nominal because actual laser intervals are unavailable. Next review: inspect baseline candidates and manual-location misses, reject artifacts, inspect reference regions on broad halos, and review uncertain/clipped margins. Only then consider other animals; all current upstream model training overlaps must remain disclosed.

## Area stability and priority examples

Reference variants produce the following footprint ranges. These are within-scan sensitivity ranges, not longitudinal change or confidence intervals. `sensitivity.csv` also reports contour Jaccard agreement on common supported pixels; empty unions are unavailable, not perfect agreement. `candidates.csv` records native centers, areas, missing fractions and uncertain/clipped flags.

Variants with insufficient background have unavailable area (blank/null), never zero area, and are excluded from the range. Support still varies among the remaining fits. Manual-mask component counts include disconnected fragments; they are not independently confirmed lesion counts.

| Scan | Default footprint mm² | Variant range mm² |
|---|---:|---:|
| TS267_OD_2025-02-19_D0_s02_112013 | 0.0576 | 0.0555–0.0584 |
| TS267_OS_2025-02-19_D0_s01_113115 | 0.0000 | 0.0000–0.0000 |
| TS267_OD_2025-02-26_D7_s01_102519 | 0.0000 | 0.0000–0.0000 |
| TS267_OS_2025-02-26_D7_s01_104111 | 0.0000 | 0.0000–0.0000 |
| TS267_OD_2025-03-05_D14_s01_104048 | 0.0109 | 0.0074–0.0213 |
| TS267_OS_2025-03-05_D14_s01_110309 | 0.0000 | 0.0000–0.0000 |
| TS267_OD_2025-03-19_D28_s01_101503 | 0.0000 | 0.0000–0.0762 |
| TS267_OS_2025-03-19_D28_s01_103036 | 0.0000 | 0.0000–0.0000 |
| TS267_OD_2025-03-26_D35_s01_101127 | 0.1198 | 0.0218–0.1238 |
| TS267_OS_2025-03-26_D35_s01_103011 | 0.0000 | 0.0000–0.0000 |
| TS267_OD_2025-04-02_D42_s01_102101 | 0.0892 | 0.0838–0.0950 |
| TS267_OS_2025-04-02_D42_s01_103648 | 0.0000 | 0.0000–0.0000 |
| TS267_OD_2025-04-09_D49_s01_101649 | 0.0309 | 0.0000–0.0369 |
| TS267_OS_2025-04-09_D49_s01_103712 | 0.0000 | 0.0000–0.0000 |
| TS267_OD_2025-04-16_D56_s01_100746 | 0.0831 | 0.0595–0.1203 |
| TS267_OD_2025-05-26_D98_s01_105602 | 0.0000 | 0.0000–0.0000 |
| TS267_OS_2025-05-26_D98_s01_112209 | 0.0000 | 0.0000–0.0000 |

The region editor groups disconnected proposal islands by nearest core solely for editing convenience. No foreground pixels are added, no border is claimed as truth, and the seeds remain Unclassified. Review files stay in `review/`; background exclusions create assisted estimates in `background_review/`. Existing annotations are comparison evidence only.

[D0 challenge: 2 candidates; nominal D0 alone does not certify unaffected tissue](scans/TS267_OD_2025-02-19_D0_s02_112013/overview.png)

[D7 manual-location challenge: inspect misses and quantitative contours](scans/TS267_OD_2025-02-26_D7_s01_102519/overview.png)

[D28 manual-location challenge: conservative core rule may fail](scans/TS267_OD_2025-03-19_D28_s01_101503/overview.png)

[D56: 2 proposed cores; left lesion-like structural focus outside supported reference](scans/TS267_OD_2025-04-16_D56_s01_100746/overview.png)

[D0 OS: zero candidates; not automatically a reviewed negative](scans/TS267_OS_2025-02-19_D0_s01_113115/overview.png)

Validation results: `verification/tests.json`, `verification/native_checks.json`, and GUI captures in `verification/`. Scientific performance remains limited by sparse review and model training overlap.
