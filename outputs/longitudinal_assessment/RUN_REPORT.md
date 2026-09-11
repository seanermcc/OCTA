# Longitudinal assessment — completed

All 22 selected full acquisitions are exported in v1 and v2 (44 versioned volumes, 11,264 native B-scans per version).

Use octa-thick_long_v1.cmd / octa-thick_long_v2.cmd in outputs/octa-thick_v1 for thickness review, or OPEN_LONGITUDINAL_SEG_v1.cmd / v2.cmd for segmentation review.

| Animal | Eye | Date | Nominal visit | v1 / v2 |
|---|---|---|---|---|
| TS267 | OD | 2025-02-19 | D0 | Ready / Ready |
| TS267 | OS | 2025-02-19 | D0 | Ready / Ready |
| TS267 | OD | 2025-02-26 | D7 | Ready / Ready |
| TS267 | OS | 2025-02-26 | D7 | Ready / Ready |
| TS267 | OD | 2025-03-05 | D14 | Ready / Ready |
| TS267 | OS | 2025-03-05 | D14 | Ready / Ready |
| TS267 | OD | 2025-03-19 | D28 | Ready / Ready |
| TS267 | OS | 2025-03-19 | D28 | Ready / Ready |
| TS267 | OD | 2025-03-26 | D35 | Ready / Ready |
| TS267 | OS | 2025-03-26 | D35 | Ready / Ready |
| TS267 | OD | 2025-04-02 | D42 | Ready / Ready |
| TS267 | OS | 2025-04-02 | D42 | Ready / Ready |
| TS267 | OD | 2025-04-09 | D49 | Ready / Ready |
| TS267 | OS | 2025-04-09 | D49 | Ready / Ready |
| TS267 | OD | 2025-04-16 | D56 | Ready / Ready |
| TS267 | OD | 2025-05-26 | D98 | Ready / Ready |
| TS267 | OS | 2025-05-26 | D98 | Ready / Ready |
| TS328 | OD | 2026-04-09 | before laser | Ready / Ready |
| TS328 | OD | 2026-04-29 | D21 | Ready / Ready |
| TS328 | OD | 2026-06-02 | D49 | Ready / Ready |
| TS328 | OD | 2026-06-09 | D56 | Ready / Ready |
| TS328 | OD | 2026-06-16 | D63 | Ready / Ready |

Verification covered all exports in the octa-thick engine, native image rows 0/256/511, version-matched neural predictions, provider coordinates, shadow NaNs, and point/map units. Both segmentation viewers and both thickness versions were rendered read-only on a completed volume.

TS267 OS D56 has no processed source volume. Missing visits were not synthesized. Actual laser-day offsets are unavailable in the index; labels remain nominal. These are experimental automatic segmentations awaiting human review, not validated longitudinal change measurements. See START_HERE.md for scope and limitations.
