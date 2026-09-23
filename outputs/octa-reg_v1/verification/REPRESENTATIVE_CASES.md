# Representative observed cases

These are automatic diagnostic examples, not human landmark validation. Green/red vessel differences can reflect mask disagreement, registration error or tissue differences. Original image seams are retained.

| Example | Pair | Dice | Inliers | Junction matches | Panel |
|---|---|---:|---:|---:|---|
| lowest passing Dice | TS328_OD_2026-04-29_D21_s01_103732 → TS328_OD_2026-06-09_D56_s01_144038 | 0.494288799227141 | 16 | 4 | [view](panels/case_01.png) |
| median passing Dice | TS169_OS_2025-01-14_D35_s02_120614 → TS169_OS_2025-01-14_D35_s04_121533 | 0.7351753496051402 | 14 | 3 | [view](panels/case_02.png) |
| highest passing Dice | TS283_OD_2025-02-05_D14_s03_103825 → TS283_OD_2025-02-05_D14_s05_104826 | 0.8805711280450278 | 14 | 4 | [view](panels/case_03.png) |
| rejection: branch_matches | TS247_OD_2024-11-26_D42_s06_115502 → TS247_OD_2024-11-26_D42_s07_115937 | 0.918719251038897 | 55 | 0 | [view](panels/case_04.png) |
| rejection: structural_correlation | TS267_OD_2025-04-02_D42_s02_102519 → TS267_OD_2025-04-16_D56_s01_100746 | 0.7574111496319917 | 9 | 1 | [view](panels/case_05.png) |
| rejection: vessel_dice | TS328_OD_2026-06-09_D56_s03_145555 → TS328_OD_2026-06-16_D63_s04_123803 | 0.3112864740100747 | 38 | 2 | [view](panels/case_06.png) |
| rejection: insufficient_vessel_anchored_inliers | TS165_OD_2025-04-29_WT_s01_111827 → TS165_OD_2025-04-29_WT_s03_112947 | None | 0 | 0 | [view](panels/case_07.png) |