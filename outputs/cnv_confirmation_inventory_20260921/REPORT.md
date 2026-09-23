# Consolidated manual CNV confirmation inventory

Snapshot: 2026-09-21T04:22:00.371089+00:00

**103 unique acquisitions have a current whole-field confirmation**, including **73 CNV-positive scans**, **28 confirmed no-CNV scans**, and **2 completed fields containing only uncertain regions**.

The confirmed positive scans contain **156 kept lesion observations**. These are annotation regions across acquisitions/visits, not unique biological lesions. **23 additional acquisitions have partial, deferred or correction-requested records.**

## By version, before deduplication

| Version | Saved scans | Whole-field completed | CNV-positive | No CNV | Uncertain only | Kept regions in completed scans | Pending |
|---|---:|---:|---:|---:|---:|---:|---:|
| v1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| v2 | 1 | 0 | 0 | 0 | 0 | 0 | 1 |
| v3 | 1 | 0 | 0 | 0 | 0 | 0 | 1 |
| v4 | 1 | 0 | 0 | 0 | 0 | 0 | 1 |
| v5 | 15 | 14 | 9 | 3 | 2 | 25 | 1 |
| v6 | 2 | 0 | 0 | 0 | 0 | 0 | 2 |
| v7 | 41 | 37 | 30 | 7 | 0 | 62 | 4 |
| v8 | 30 | 29 | 21 | 8 | 0 | 44 | 1 |
| v9 | 50 | 33 | 23 | 10 | 0 | 45 | 17 |

## Interpretation and checks

- Current real review records were read directly. Historical revisions, copied v6 records, demonstration data, synthetic tests and automatic proposals do not add samples.
- The consolidated view uses the newest version for each exact acquisition. A newer deferred/incomplete review blocks automatic fallback to an older confirmation. All older source paths and statuses remain in inventory.json.
- V7/v8 confirmation signatures and stored positive/background/ignored masks were recomputed. V9 decision tokens, candidate masks, prediction files and checkpoint hashes were verified against the current gallery.
- V5 uses its explicit whole-field completion flags; it has no v7-style signature. Two completed fields contain only uncertain regions and must not be used as clean negatives.
- V6 reviews concern model errors and do not certify whole-field background. Their two scans are flagged for reconciliation in the inventory even where a v5 completion exists.
- V9: 26 Model 1 approvals, 31 Model 2 approvals, 24 approved both. Count each acquisition once; choose approved Model 2 where available, otherwise approved Model 1. 17 scans request Model 2 correction.
- 103 unique acquisitions have a confirmation in at least one version's current head; the current consolidated total above honors newer deferrals.
- Original labels remain in place. This folder is a read-only-source index/report, not a newly authored ground-truth dataset or training export.
- Validation errors: 0.

## Current counts by animal

| Animal | Completed | Positive | No CNV | Uncertain only | Lesion observations | Pending |
|---|---:|---:|---:|---:|---:|---:|
| TS169 | 11 | 8 | 3 | 0 | 19 | 1 |
| TS241 | 11 | 6 | 5 | 0 | 10 | 2 |
| TS247 | 8 | 4 | 4 | 0 | 12 | 3 |
| TS250 | 9 | 9 | 0 | 0 | 17 | 3 |
| TS267 | 25 | 12 | 11 | 2 | 34 | 1 |
| TS283 | 7 | 5 | 2 | 0 | 11 | 1 |
| TS305 | 10 | 9 | 1 | 0 | 19 | 1 |
| TS325 | 7 | 6 | 1 | 0 | 11 | 4 |
| TS328 | 7 | 6 | 1 | 0 | 10 | 4 |
| TS336 | 8 | 8 | 0 | 0 | 13 | 3 |

## Confirmed acquisitions

| Acquisition | Selected version | Status | Kept regions | Source |
|---|---|---|---:|---|
| TS169_OD_2025-01-14_D35_s01_110623 | v7 | positive | 1 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v7\review\regions\TS169_OD_2025-01-14_D35_s01_110623.json>) |
| TS169_OD_2025-01-14_D35_s02_111434 | v9 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS169_OD_2025-01-14_D35_s02_111434.json>) |
| TS169_OD_2025-01-14_D35_s03_112013 | v7 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v7\review\regions\TS169_OD_2025-01-14_D35_s03_112013.json>) |
| TS169_OD_2025-01-14_D35_s04_112507 | v9 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS169_OD_2025-01-14_D35_s04_112507.json>) |
| TS169_OD_2025-01-14_D35_s05_113034 | v8 | positive | 3 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v8\manual_review\review\regions\TS169_OD_2025-01-14_D35_s05_113034.json>) |
| TS169_OD_2025-01-14_D35_s07_114301 | v7 | positive | 3 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v7\review\regions\TS169_OD_2025-01-14_D35_s07_114301.json>) |
| TS169_OD_2025-01-14_D35_s08_114921 | v8 | positive | 3 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v8\manual_review\review\regions\TS169_OD_2025-01-14_D35_s08_114921.json>) |
| TS169_OD_2025-01-14_D35_s09_115440 | v9 | positive | 3 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS169_OD_2025-01-14_D35_s09_115440.json>) |
| TS169_OS_2025-01-14_D35_s01_120129 | v7 | negative | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v7\review\regions\TS169_OS_2025-01-14_D35_s01_120129.json>) |
| TS169_OS_2025-01-14_D35_s02_120614 | v8 | negative | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v8\manual_review\review\regions\TS169_OS_2025-01-14_D35_s02_120614.json>) |
| TS169_OS_2025-01-14_D35_s03_121018 | v9 | negative | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS169_OS_2025-01-14_D35_s03_121018.json>) |
| TS241_OD_2024-08-21_D7_s04_115950 | v8 | negative | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v8\manual_review\review\regions\TS241_OD_2024-08-21_D7_s04_115950.json>) |
| TS241_OD_2024-08-28_D14_s05_115807 | v7 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v7\review\regions\TS241_OD_2024-08-28_D14_s05_115807.json>) |
| TS241_OD_2024-09-04_D21_s01_111543 | v9 | positive | 1 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS241_OD_2024-09-04_D21_s01_111543.json>) |
| TS241_OD_2024-09-04_D21_s05_115407 | v9 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS241_OD_2024-09-04_D21_s05_115407.json>) |
| TS241_OD_2024-09-11_D28_s06_113443 | v9 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS241_OD_2024-09-11_D28_s06_113443.json>) |
| TS241_OD_2024-09-25_D42_s01_110248 | v9 | positive | 1 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS241_OD_2024-09-25_D42_s01_110248.json>) |
| TS241_OD_2024-09-25_D42_s06_112743 | v8 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v8\manual_review\review\regions\TS241_OD_2024-09-25_D42_s06_112743.json>) |
| TS241_OS_2024-08-28_D14_s03_105429 | v9 | negative | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS241_OS_2024-08-28_D14_s03_105429.json>) |
| TS241_OS_2024-09-04_D21_s01_104822 | v7 | negative | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v7\review\regions\TS241_OS_2024-09-04_D21_s01_104822.json>) |
| TS241_OS_2024-09-11_D28_s01_102112 | v8 | negative | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v8\manual_review\review\regions\TS241_OS_2024-09-11_D28_s01_102112.json>) |
| TS241_OS_2024-09-19_D35_s05_114334 | v7 | negative | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v7\review\regions\TS241_OS_2024-09-19_D35_s05_114334.json>) |
| TS247_OD_2024-10-30_D14_s04_110100 | v9 | positive | 3 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS247_OD_2024-10-30_D14_s04_110100.json>) |
| TS247_OD_2024-11-06_D21_s01_102655 | v8 | positive | 3 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v8\manual_review\review\regions\TS247_OD_2024-11-06_D21_s01_102655.json>) |
| TS247_OD_2024-11-06_D21_s02_103301 | v7 | negative | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v7\review\regions\TS247_OD_2024-11-06_D21_s02_103301.json>) |
| TS247_OD_2024-11-06_D21_s05_104915 | v9 | positive | 3 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS247_OD_2024-11-06_D21_s05_104915.json>) |
| TS247_OD_2024-11-20_D35_s02_113316 | v7 | negative | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v7\review\regions\TS247_OD_2024-11-20_D35_s02_113316.json>) |
| TS247_OD_2024-11-26_D42_s07_115937 | v8 | positive | 3 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v8\manual_review\review\regions\TS247_OD_2024-11-26_D42_s07_115937.json>) |
| TS247_OS_2024-11-26_D42_s01_120410 | v9 | negative | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS247_OS_2024-11-26_D42_s01_120410.json>) |
| TS247_OS_2024-11-26_D42_s03_121152 | v9 | negative | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS247_OS_2024-11-26_D42_s03_121152.json>) |
| TS250_OD_2026-03-03_D7_s03_120036 | v8 | positive | 1 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v8\manual_review\review\regions\TS250_OD_2026-03-03_D7_s03_120036.json>) |
| TS250_OD_2026-03-20_D24_s02_141857 | v9 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS250_OD_2026-03-20_D24_s02_141857.json>) |
| TS250_OD_2026-03-20_D24_s03_142449 | v7 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v7\review\regions\TS250_OD_2026-03-20_D24_s03_142449.json>) |
| TS250_OD_2026-03-20_D24_s04_143137 | v7 | positive | 3 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v7\review\regions\TS250_OD_2026-03-20_D24_s04_143137.json>) |
| TS250_OD_2026-03-23_D27_s03_113853 | v7 | positive | 3 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v7\review\regions\TS250_OD_2026-03-23_D27_s03_113853.json>) |
| TS250_OS_2026-03-20_D24_s01_143551 | v9 | positive | 1 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS250_OS_2026-03-20_D24_s01_143551.json>) |
| TS250_OS_2026-03-20_D24_s03_144927 | v8 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v8\manual_review\review\regions\TS250_OS_2026-03-20_D24_s03_144927.json>) |
| TS250_OS_2026-03-23_D27_s01_114326 | v9 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS250_OS_2026-03-23_D27_s01_114326.json>) |
| TS250_OS_2026-03-23_D27_s02_114805 | v8 | positive | 1 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v8\manual_review\review\regions\TS250_OS_2026-03-23_D27_s02_114805.json>) |
| TS267_OD_2025-02-19_D0_s02_112013 | v5 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v5\review\regions\TS267_OD_2025-02-19_D0_s02_112013_regions.json>) |
| TS267_OD_2025-02-26_D7_s01_102519 | v5 | positive | 3 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v5\review\regions\TS267_OD_2025-02-26_D7_s01_102519_regions.json>) |
| TS267_OD_2025-03-05_D14_s01_104048 | v5 | positive | 3 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v5\review\regions\TS267_OD_2025-03-05_D14_s01_104048_regions.json>) |
| TS267_OD_2025-03-19_D28_s01_101503 | v5 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v5\review\regions\TS267_OD_2025-03-19_D28_s01_101503_regions.json>) |
| TS267_OD_2025-03-26_D35_s01_101127 | v5 | positive | 3 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v5\review\regions\TS267_OD_2025-03-26_D35_s01_101127_regions.json>) |
| TS267_OD_2025-04-02_D42_s01_102101 | v5 | positive | 3 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v5\review\regions\TS267_OD_2025-04-02_D42_s01_102101_regions.json>) |
| TS267_OD_2025-04-09_D49_s01_101649 | v5 | positive | 3 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v5\review\regions\TS267_OD_2025-04-09_D49_s01_101649_regions.json>) |
| TS267_OD_2025-04-09_D49_s02_102203 | v7 | positive | 3 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v7\review\regions\TS267_OD_2025-04-09_D49_s02_102203.json>) |
| TS267_OD_2025-04-16_D56_s01_100746 | v5 | positive | 3 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v5\review\regions\TS267_OD_2025-04-16_D56_s01_100746_regions.json>) |
| TS267_OD_2025-04-16_D56_s03_102014 | v8 | positive | 3 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v8\manual_review\review\regions\TS267_OD_2025-04-16_D56_s03_102014.json>) |
| TS267_OD_2025-05-26_D98_s01_105602 | v5 | positive | 3 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v5\review\regions\TS267_OD_2025-05-26_D98_s01_105602_regions.json>) |
| TS267_OD_2025-05-26_D98_s02_110033 | v7 | positive | 3 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v7\review\regions\TS267_OD_2025-05-26_D98_s02_110033.json>) |
| TS267_OS_2025-02-26_D7_s01_104111 | v5 | uncertain_only | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v5\review\regions\TS267_OS_2025-02-26_D7_s01_104111_regions.json>) |
| TS267_OS_2025-03-05_D14_s01_110309 | v5 | negative | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v5\review\regions\TS267_OS_2025-03-05_D14_s01_110309_regions.json>) |
| TS267_OS_2025-03-05_D14_s04_111737 | v8 | negative | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v8\manual_review\review\regions\TS267_OS_2025-03-05_D14_s04_111737.json>) |
| TS267_OS_2025-03-19_D28_s02_103446 | v7 | negative | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v7\review\regions\TS267_OS_2025-03-19_D28_s02_103446.json>) |
| TS267_OS_2025-03-19_D28_s04_104308 | v9 | negative | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS267_OS_2025-03-19_D28_s04_104308.json>) |
| TS267_OS_2025-03-26_D35_s01_103011 | v9 | negative | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS267_OS_2025-03-26_D35_s01_103011.json>) |
| TS267_OS_2025-04-02_D42_s01_103648 | v5 | negative | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v5\review\regions\TS267_OS_2025-04-02_D42_s01_103648_regions.json>) |
| TS267_OS_2025-04-02_D42_s02_104209 | v9 | negative | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS267_OS_2025-04-02_D42_s02_104209.json>) |
| TS267_OS_2025-04-09_D49_s01_103712 | v5 | uncertain_only | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v5\review\regions\TS267_OS_2025-04-09_D49_s01_103712_regions.json>) |
| TS267_OS_2025-04-09_D49_s02_104205 | v9 | negative | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS267_OS_2025-04-09_D49_s02_104205.json>) |
| TS267_OS_2025-05-26_D98_s01_112209 | v5 | negative | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v5\review\regions\TS267_OS_2025-05-26_D98_s01_112209_regions.json>) |
| TS267_OS_2025-05-26_D98_s02_112628 | v8 | negative | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v8\manual_review\review\regions\TS267_OS_2025-05-26_D98_s02_112628.json>) |
| TS267_OS_2025-05-26_D98_s03_113101 | v9 | negative | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS267_OS_2025-05-26_D98_s03_113101.json>) |
| TS283_OD_2025-01-22_D0_s02_111740 | v8 | negative | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v8\manual_review\review\regions\TS283_OD_2025-01-22_D0_s02_111740.json>) |
| TS283_OD_2025-01-29_D7_s03_124106 | v8 | positive | 3 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v8\manual_review\review\regions\TS283_OD_2025-01-29_D7_s03_124106.json>) |
| TS283_OD_2025-02-05_D14_s01_101911 | v7 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v7\review\regions\TS283_OD_2025-02-05_D14_s01_101911.json>) |
| TS283_OD_2025-02-05_D14_s02_102709 | v9 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS283_OD_2025-02-05_D14_s02_102709.json>) |
| TS283_OD_2025-02-05_D14_s03_103825 | v7 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v7\review\regions\TS283_OD_2025-02-05_D14_s03_103825.json>) |
| TS283_OD_2025-02-05_D14_s05_104826 | v8 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v8\manual_review\review\regions\TS283_OD_2025-02-05_D14_s05_104826.json>) |
| TS283_OS_2025-02-05_D14_s01_105246 | v7 | negative | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v7\review\regions\TS283_OS_2025-02-05_D14_s01_105246.json>) |
| TS305_OD_2025-07-17_D14_s01_111200 | v8 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v8\manual_review\review\regions\TS305_OD_2025-07-17_D14_s01_111200.json>) |
| TS305_OD_2025-07-17_D14_s02_111813 | v9 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS305_OD_2025-07-17_D14_s02_111813.json>) |
| TS305_OD_2025-08-07_D35_s02_115200 | v9 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS305_OD_2025-08-07_D35_s02_115200.json>) |
| TS305_OD_2025-08-07_D35_s03_115616 | v8 | positive | 3 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v8\manual_review\review\regions\TS305_OD_2025-08-07_D35_s03_115616.json>) |
| TS305_OD_2025-08-07_D35_s06_121225 | v7 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v7\review\regions\TS305_OD_2025-08-07_D35_s06_121225.json>) |
| TS305_OD_2025-08-21_D49_s01_115255 | v7 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v7\review\regions\TS305_OD_2025-08-21_D49_s01_115255.json>) |
| TS305_OD_2025-08-21_D49_s04_120934 | v9 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS305_OD_2025-08-21_D49_s04_120934.json>) |
| TS305_OD_2025-09-04_D63_s04_113622 | v9 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS305_OD_2025-09-04_D63_s04_113622.json>) |
| TS305_OD_2025-09-04_D63_s05_114053 | v7 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v7\review\regions\TS305_OD_2025-09-04_D63_s05_114053.json>) |
| TS305_OS_2025-09-04_D63_s01_114928 | v8 | negative | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v8\manual_review\review\regions\TS305_OS_2025-09-04_D63_s01_114928.json>) |
| TS325_OD_2025-12-04_D14_s01_115930 | v7 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v7\review\regions\TS325_OD_2025-12-04_D14_s01_115930.json>) |
| TS325_OD_2026-01-05_D42_s02_125842 | v9 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS325_OD_2026-01-05_D42_s02_125842.json>) |
| TS325_OD_2026-01-05_D42_s03_130313 | v8 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v8\manual_review\review\regions\TS325_OD_2026-01-05_D42_s03_130313.json>) |
| TS325_OD_2026-01-22_D56_s01_141225 | v8 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v8\manual_review\review\regions\TS325_OD_2026-01-22_D56_s01_141225.json>) |
| TS325_OD_2026-02-05_D70_s01_143507 | v7 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v7\review\regions\TS325_OD_2026-02-05_D70_s01_143507.json>) |
| TS325_OD_2026-02-05_D70_s03_145300 | v9 | negative | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS325_OD_2026-02-05_D70_s03_145300.json>) |
| TS325_OD_2026-05-26_6mo_s03_115732 | v8 | positive | 1 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v8\manual_review\review\regions\TS325_OD_2026-05-26_6mo_s03_115732.json>) |
| TS328_OD_2026-04-09_beforelaser_s01_130813 | v8 | negative | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v8\manual_review\review\regions\TS328_OD_2026-04-09_beforelaser_s01_130813.json>) |
| TS328_OD_2026-04-29_D21_s02_104608 | v8 | positive | 3 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v8\manual_review\review\regions\TS328_OD_2026-04-29_D21_s02_104608.json>) |
| TS328_OD_2026-06-02_D49_s01_145923 | v9 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS328_OD_2026-06-02_D49_s01_145923.json>) |
| TS328_OD_2026-06-09_D56_s01_144038 | v7 | positive | 1 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v7\review\regions\TS328_OD_2026-06-09_D56_s01_144038.json>) |
| TS328_OD_2026-06-16_D63_s02_121743 | v9 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS328_OD_2026-06-16_D63_s02_121743.json>) |
| TS328_OD_2026-06-16_D63_s03_122456 | v7 | positive | 1 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v7\review\regions\TS328_OD_2026-06-16_D63_s03_122456.json>) |
| TS328_OD_2026-06-16_D63_s04_123218 | v8 | positive | 1 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v8\manual_review\review\regions\TS328_OD_2026-06-16_D63_s04_123218.json>) |
| TS336_OD_2026-05-22_D21_s01_111458 | v9 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS336_OD_2026-05-22_D21_s01_111458.json>) |
| TS336_OD_2026-05-22_D21_s04_114008 | v8 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v8\manual_review\review\regions\TS336_OD_2026-05-22_D21_s04_114008.json>) |
| TS336_OD_2026-06-02_D28_s02_160031 | v9 | positive | 1 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS336_OD_2026-06-02_D28_s02_160031.json>) |
| TS336_OD_2026-06-02_D28_s03_160423 | v8 | positive | 1 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v8\manual_review\review\regions\TS336_OD_2026-06-02_D28_s03_160423.json>) |
| TS336_OD_2026-06-09_D35_s02_153916 | v8 | positive | 1 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v8\manual_review\review\regions\TS336_OD_2026-06-09_D35_s02_153916.json>) |
| TS336_OD_2026-06-16_D42_s05_134542 | v9 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS336_OD_2026-06-16_D42_s05_134542.json>) |
| TS336_OD_2026-07-28_D56_s03_144933 | v7 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v7\review\regions\TS336_OD_2026-07-28_D56_s03_144933.json>) |
| TS336_OD_2026-08-12_D92_s04_152529 | v7 | positive | 2 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v7\review\regions\TS336_OD_2026-08-12_D92_s04_152529.json>) |

## Pending acquisitions

| Acquisition | Selected version | Status | Kept regions | Source |
|---|---|---|---:|---|
| TS169_OD_2025-01-14_D35_s06_113841 | v9 | correction_requested | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS169_OD_2025-01-14_D35_s06_113841.json>) |
| TS241_OS_2024-09-11_D28_s04_104606 | v7 | deferred | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v7\review\regions\TS241_OS_2024-09-11_D28_s04_104606.json>) |
| TS241_OS_2024-09-19_D35_s01_111559 | v9 | correction_requested | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS241_OS_2024-09-19_D35_s01_111559.json>) |
| TS247_OD_2024-10-23_D7_s05_114003 | v8 | deferred | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v8\manual_review\review\regions\TS247_OD_2024-10-23_D7_s05_114003.json>) |
| TS247_OD_2024-10-30_D14_s02_103834 | v9 | correction_requested | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS247_OD_2024-10-30_D14_s02_103834.json>) |
| TS247_OD_2024-11-20_D35_s06_115945 | v9 | correction_requested | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS247_OD_2024-11-20_D35_s06_115945.json>) |
| TS250_OD_2026-03-23_D27_s01_112447 | v9 | correction_requested | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS250_OD_2026-03-23_D27_s01_112447.json>) |
| TS250_OD_2026-03-23_D27_s02_113408 | v9 | correction_requested | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS250_OD_2026-03-23_D27_s02_113408.json>) |
| TS250_OS_2026-03-20_D24_s04_145633 | v9 | correction_requested | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS250_OS_2026-03-20_D24_s04_145633.json>) |
| TS267_OS_2025-02-19_D0_s01_113115 | v5 | partial | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v5\review\regions\TS267_OS_2025-02-19_D0_s01_113115_regions.json>) |
| TS283_OD_2025-02-05_D14_s04_104333 | v9 | correction_requested | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS283_OD_2025-02-05_D14_s04_104333.json>) |
| TS305_OD_2025-07-17_D14_s04_112929 | v9 | correction_requested | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS305_OD_2025-07-17_D14_s04_112929.json>) |
| TS325_OD_2025-12-18_D28_s04_114244 | v9 | correction_requested | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS325_OD_2025-12-18_D28_s04_114244.json>) |
| TS325_OD_2026-03-03_D98_s04_133118 | v7 | deferred | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v7\review\regions\TS325_OD_2026-03-03_D98_s04_133118.json>) |
| TS325_OD_2026-04-29_D119_s04_114330 | v9 | correction_requested | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS325_OD_2026-04-29_D119_s04_114330.json>) |
| TS325_OD_2026-05-26_6mo_s06_121256 | v9 | correction_requested | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS325_OD_2026-05-26_6mo_s06_121256.json>) |
| TS328_OD_2026-04-29_D21_s04_105712 | v9 | unconfirmed | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS328_OD_2026-04-29_D21_s04_105712.json>) |
| TS328_OD_2026-06-02_D49_s04_151618 | v7 | deferred | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v7\review\regions\TS328_OD_2026-06-02_D49_s04_151618.json>) |
| TS328_OD_2026-06-02_D49_s05_152017 | v9 | correction_requested | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS328_OD_2026-06-02_D49_s05_152017.json>) |
| TS328_OD_2026-06-09_D56_s04_150054 | v9 | correction_requested | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS328_OD_2026-06-09_D56_s04_150054.json>) |
| TS336_OD_2026-06-02_D28_s04_161256 | v9 | correction_requested | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS336_OD_2026-06-02_D28_s04_161256.json>) |
| TS336_OD_2026-06-09_D35_s03_154413 | v7 | deferred | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v7\review\regions\TS336_OD_2026-06-09_D35_s03_154413.json>) |
| TS336_OD_2026-06-09_D35_s05_155756 | v9 | unconfirmed | 0 | [record](<G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_v9\manual_review\decisions\TS336_OD_2026-06-09_D35_s05_155756.json>) |

## Additional original manual labels

Found 28 original CNV NPZ files in outputs/cnv_labels: 19 marked reviewed with nonempty CNV masks. They are preserved in the supplementary manifest; their older review flag is not counted as the newer whole-field confirmation contract.

Re-run audit.py in the activated octa environment to refresh this report. inventory.json contains exact source paths, hashes, all current records, selected acquisitions, overlap provenance and the original-label supplement.
