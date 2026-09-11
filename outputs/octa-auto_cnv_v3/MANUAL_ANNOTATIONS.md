# Your saved manual annotations

Original files remain in `G:/OCT_TreeShrew/octa/outputs/cnv_labels/`. Five TS267 files contain footprints; the sixth is an explicit reviewed absence. V3 reads matching acquisitions as cyan comparison outlines and never overwrites these files.

| Acquisition | Manual work | In current pilot? | File |
|---|---|---|---|
| TS267_OD_2025-02-26_D7_s01_102519 | 5 connected components (not necessarily separate lesions) | Yes | [TS267_OD_2025-02-26_D7_s01_102519_cnv.npz](G:/OCT_TreeShrew/octa/outputs/cnv_labels/TS267_OD_2025-02-26_D7_s01_102519_cnv.npz) |
| TS267_OD_2025-03-19_D28_s01_101503 | 2 connected components (not necessarily separate lesions) | Yes | [TS267_OD_2025-03-19_D28_s01_101503_cnv.npz](G:/OCT_TreeShrew/octa/outputs/cnv_labels/TS267_OD_2025-03-19_D28_s01_101503_cnv.npz) |
| TS267_OD_2025-04-16_D56_s02_101433 | 7 connected components (not necessarily separate lesions) | No; different repeat | [TS267_OD_2025-04-16_D56_s02_101433_cnv.npz](G:/OCT_TreeShrew/octa/outputs/cnv_labels/TS267_OD_2025-04-16_D56_s02_101433_cnv.npz) |
| TS267_OD_2025-04-16_D56_s03_102014 | 5 connected components (not necessarily separate lesions) | No; different repeat | [TS267_OD_2025-04-16_D56_s03_102014_cnv.npz](G:/OCT_TreeShrew/octa/outputs/cnv_labels/TS267_OD_2025-04-16_D56_s03_102014_cnv.npz) |
| TS267_OS_2025-04-09_D49_s03_104748 | 2 connected components (not necessarily separate lesions) | No; different repeat | [TS267_OS_2025-04-09_D49_s03_104748_cnv.npz](G:/OCT_TreeShrew/octa/outputs/cnv_labels/TS267_OS_2025-04-09_D49_s03_104748_cnv.npz) |
| TS267_OS_2025-05-26_D98_s05_114216 | Reviewed: no CNV | No; different repeat | [TS267_OS_2025-05-26_D98_s05_114216_cnv.npz](G:/OCT_TreeShrew/octa/outputs/cnv_labels/TS267_OS_2025-05-26_D98_s05_114216_cnv.npz) |

D7 and D28 appear in the v3 viewer. Use **Saved manual outlines (cyan)** and the **Saved manual** dropdown to jump to each footprint. **OPEN_SAVED_MANUAL_D7.cmd** opens D7 directly. Different repeats are not transferred to the selected scan without registration. `manual_inventory.csv` records their source segmentation paths and hashes.

For new reference drawings, use **OPEN_MANUAL_REVIEW.cmd**: automatic footprints start hidden and no automatic region is selected. Draw region, assign Full Lesion / Normal / Other, then complete review and Save all. Keep Normal restricted to tissue actually inspected. Suggested next examples: D14 OD; the missed lower D7 footprint; and a D0 vessel or edge artifact confirmed not to be CNV. Three to five acquisitions are a useful first review set, not a statistically powered validation cohort.

New drawings save separately in `outputs/octa-auto_cnv_v3/review/regions/`. Original hand-drawn regions (no automatic seed) enter the reference comparison when the pilot is rerun. Corrections/approvals of automatic seeds remain assisted review evidence and are not counted as independent manual-location ground truth. All examples used to revise these rules are development examples; later validation needs different acquisitions/animals with upstream training exposure disclosed.
