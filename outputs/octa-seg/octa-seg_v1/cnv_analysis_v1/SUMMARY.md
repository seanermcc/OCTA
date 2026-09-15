# Summary and segmentation coverage

[Cohort summary](SUMMARY.png) · [Segmentation coverage](SEGMENTATION_COVERAGE.png) · [All figures](FIGURE_INDEX.md)

All 314 scan acquisitions have segmentation outputs and frozen thickness maps. These are acquisitions, not 314 distinct retinas. Only 19 scans had manual CNV outlines, giving 62 outlined observations from nine animals. Seven animals enter the normalized post-D0 cohort means: TS328 has only prelaser outlines and TS250 has a clipped outline. Clipped measurements remain in the absolute-distance tables.

The observed lesion maps deliberately display only the outlined lesion and its surrounding distance bands. White gaps inside that displayed region retain missing or excluded measurements. They do not by themselves show that a scan was never processed.

**SUMMARY.png:** Eight layer means versus distance beyond the lesion edge, from `tables/cohort_distance_summary.csv` (changing, normalized). Repeats, visits, tracked lesions, eyes and animals are balanced hierarchically. Shading is the 95% animal-cluster bootstrap interval. These are experimental results; the final batch audit was waived.

**SEGMENTATION_COVERAGE.png:** Every scan contributes one dot per layer. Finite measurement counts come from the frozen per-scan viewer-export metadata and are divided by the full recorded grid size. This describes available measurements, not segmentation accuracy or retinal tissue coverage alone.

Fixed-region plots currently contain reference observations only; no cross-visit fixed-tissue trajectory was verified. The changing-outline time courses can show independently outlined visits.
