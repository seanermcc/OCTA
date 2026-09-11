# Thickness distribution comparison

These are automatic-model diagnostics before human overrides, with invalid/crossing and shadowed columns excluded and counted. The original-four range is descriptive; lying outside it is not an error definition.

| Layer | Original four median range (µm) | TS328 median / SD / IQR (µm) | TS328 valid % | TS336 median / SD / IQR (µm) | TS336 valid % |
|---|---:|---:|---:|---:|---:|
| RNFL | 45.0–88.7 | 71.2 / 36.4 / 40.7 | 78.2 | 73.2 / 33.6 / 41.0 | 82.0 |
| GCL | 11.8–13.6 | 12.3 / 7.7 / 2.9 | 76.9 | 13.1 / 9.6 / 4.8 | 75.7 |
| IPL | 52.6–61.4 | 58.0 / 7.5 / 4.3 | 76.2 | 57.4 / 13.6 / 8.9 | 75.2 |
| INL | 30.8–38.8 | 38.5 / 7.6 / 3.5 | 76.3 | 35.9 / 6.6 / 5.6 | 79.1 |
| OPL | 17.5–20.3 | 17.0 / 5.8 / 1.7 | 77.1 | 18.6 / 6.6 / 2.9 | 82.2 |
| PHOTORECEPTOR | 25.9–29.4 | 33.7 / 4.5 / 3.0 | 77.0 | 27.7 / 6.1 / 5.8 | 82.0 |
| RPE | 20.3–21.3 | 21.2 / 3.3 / 2.1 | 77.4 | 22.1 / 9.4 / 6.4 | 85.0 |
| TOTAL | 207.1–253.7 | 252.5 / 34.0 / 38.2 | 75.5 | 246.9 / 40.0 / 45.4 | 72.0 |
| INNER_RETINA | 110.2–156.1 | 141.4 / 35.8 / 40.4 | 76.1 | 144.4 / 36.4 / 43.6 | 73.5 |

Every layer is retained. Primary RNFL, TOTAL and INNER_RETINA remain unavailable because v1 withholds ILM. Primary and diagnostic results must not be combined.

Use thickness_contexts.csv to compare the same joint signal/vessel/CNV/ONH strata. The new acquisitions lack annotated ONH locations, so eccentricity matching to TS165 or TS283 is unavailable. Apparent layer-distribution differences cannot be separated fully from location or annotation availability in this pilot.

Native per-boundary median/P95 entropy for every 64-column strip is in strip_boundary_entropy.csv.
