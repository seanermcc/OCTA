# Stage A readability/ordering — complete development tables

Experimental. Ground truth is frozen manual segmentation only. Unavailable cells have no measured evidence.

## Headline comparison

| Method | Supported measured / 34,809 | Coverage | Leakage / 17,096 | Leakage | Boundary median / p95 (um) | Gross / measured | Worst run |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Epoch 124 existing | 33090 | 95.06% | 3159 | 18.48% | 2.10 / 9.41 | 658 / 33090 | 44 |
| Readability alone | 28655 | 82.32% | 1193 | 6.98% | 2.06 / 9.37 | 594 / 28655 | 44 |
| Ordered alone | 30280 | 86.99% | 1272 | 7.44% | 2.13 / 7.92 | 192 / 30280 | 29 |
| Readability + ordered | 26121 | 75.04% | 616 | 3.60% | 2.08 / 7.84 | 153 / 26121 | 13 |
| Entropy + signal | 26099 | 74.98% | 646 | 3.78% | 1.93 / 7.39 | 79 / 26099 | 19 |
| Entropy + signal + ordered | 25503 | 73.27% | 504 | 2.95% | 2.05 / 7.50 | 42 / 25503 | 27 |

## Boundary errors

Each cell: median / p95 um; gross >25 um count / retained count (eligible denominator).

| Surface/band | Epoch 124 existing | Readability alone | Ordered alone | Readability + ordered | Entropy + signal | Entropy + signal + ordered |
| --- | --- | --- | --- | --- | --- | --- |
| GCL_IPL | 1.96 / 7.37; 87/4263 (4580) | 1.83 / 7.56; 80/3686 (4580) | 1.90 / 6.71; 28/3952 (4580) | 1.79 / 6.77; 28/3412 (4580) | 1.85 / 5.72; 5/3380 (4580) | 1.85 / 5.72; 0/3299 (4580) |
| ILM | 1.53 / 11.12; 134/3450 (3517) | 1.58 / 8.55; 109/3058 (3517) | 1.13 / 5.60; 67/3026 (3517) | 1.22 / 4.96; 31/2647 (3517) | 1.43 / 5.15; 26/2480 (3517) | 1.12 / 4.64; 34/2457 (3517) |
| INL_OPL | 3.16 / 13.81; 96/4354 (4580) | 3.39 / 15.41; 96/3782 (4580) | 3.25 / 10.96; 10/3952 (4580) | 3.36 / 11.34; 10/3412 (4580) | 2.93 / 9.14; 0/3371 (4580) | 3.08 / 10.64; 0/3299 (4580) |
| IPL_INL | 2.46 / 19.66; 147/4231 (4580) | 2.18 / 18.83; 127/3660 (4580) | 2.24 / 8.07; 24/3952 (4580) | 2.14 / 7.21; 24/3412 (4580) | 2.11 / 8.16; 31/3370 (4580) | 2.21 / 7.47; 0/3299 (4580) |
| OPL_ONL | 2.19 / 6.98; 47/4296 (4580) | 2.15 / 7.07; 43/3718 (4580) | 2.24 / 6.48; 10/3952 (4580) | 2.16 / 6.17; 10/3412 (4580) | 2.08 / 5.94; 4/3388 (4580) | 2.15 / 5.87; 0/3299 (4580) |
| PR_RPE | 2.19 / 8.87; 29/4293 (4580) | 2.22 / 9.23; 29/3715 (4580) | 2.19 / 8.34; 10/3952 (4580) | 2.23 / 8.74; 10/3412 (4580) | 1.97 / 8.43; 0/3388 (4580) | 2.10 / 8.07; 0/3299 (4580) |
| RNFL_GCL | 2.47 / 10.49; 118/4391 (4580) | 2.41 / 10.25; 110/3813 (4580) | 2.34 / 8.60; 43/3952 (4580) | 2.27 / 8.58; 40/3412 (4580) | 2.29 / 8.25; 13/3381 (4580) | 2.25 / 8.17; 8/3299 (4580) |
| RPE | 1.22 / 4.69; 0/3812 (3812) | 1.17 / 4.56; 0/3223 (3812) | 1.12 / 4.48; 0/3542 (3812) | 1.12 / 4.48; 0/3002 (3812) | 1.21 / 4.43; 0/3341 (3812) | 1.12 / 4.48; 0/3252 (3812) |

## Thickness errors

Each cell: median / p95 um; gross >25 um count / retained count (eligible denominator).

| Surface/band | Epoch 124 existing | Readability alone | Ordered alone | Readability + ordered | Entropy + signal | Entropy + signal + ordered |
| --- | --- | --- | --- | --- | --- | --- |
| GCL | 2.46 / 9.05; 56/4217 (4580) | 2.54 / 9.07; 52/3640 (4580) | 2.46 / 8.29; 15/3952 (4580) | 2.59 / 8.14; 12/3412 (4580) | 2.33 / 8.16; 8/3380 (4580) | 2.36 / 8.29; 8/3299 (4580) |
| INL | 3.95 / 17.33; 98/4182 (4580) | 3.85 / 16.73; 82/3611 (4580) | 3.84 / 12.54; 20/3952 (4580) | 3.87 / 12.08; 20/3412 (4580) | 3.68 / 12.73; 29/3370 (4580) | 3.76 / 11.89; 6/3299 (4580) |
| IPL | 3.28 / 17.24; 133/4167 (4580) | 3.13 / 16.24; 105/3607 (4580) | 3.09 / 9.89; 8/3952 (4580) | 2.94 / 9.22; 8/3412 (4580) | 2.92 / 10.34; 33/3363 (4580) | 2.89 / 9.11; 0/3299 (4580) |
| OPL | 3.47 / 10.37; 28/4237 (4580) | 3.65 / 10.93; 28/3676 (4580) | 3.45 / 10.09; 0/3952 (4580) | 3.64 / 10.57; 0/3412 (4580) | 3.42 / 8.89; 0/3371 (4580) | 3.43 / 10.26; 0/3299 (4580) |
| PHOTORECEPTOR | 2.92 / 10.53; 8/4257 (4580) | 2.76 / 10.95; 8/3679 (4580) | 2.96 / 9.15; 0/3952 (4580) | 2.79 / 9.77; 0/3412 (4580) | 2.76 / 9.45; 0/3388 (4580) | 2.82 / 8.92; 0/3299 (4580) |
| RNFL | 2.69 / 17.80; 129/3361 (3517) | 2.65 / 14.50; 103/2969 (3517) | 2.61 / 9.94; 51/3026 (3517) | 2.52 / 8.56; 15/2647 (3517) | 2.44 / 9.26; 30/2480 (3517) | 2.47 / 9.12; 41/2457 (3517) |
| RPE | 2.20 / 9.82; 0/3793 (3812) | 2.15 / 10.76; 0/3215 (3812) | 2.22 / 10.08; 0/3542 (3812) | 2.17 / 11.20; 0/3002 (3812) | 2.10 / 10.40; 0/3341 (3812) | 2.18 / 11.11; 0/3252 (3812) |
| TOTAL | 2.16 / 6.39; 27/2782 (2782) | 2.20 / 5.97; 2/2390 (2782) | 2.24 / 6.41; 36/2639 (2782) | 2.24 / 5.61; 0/2260 (2782) | 2.14 / 6.05; 26/2433 (2782) | 2.24 / 6.32; 34/2410 (2782) |

## Animal and available quality strata

Leakage = measured / explicit-negative surface-columns; supported = measured / eligible manual positions. TS336 has no accuracy evidence.

| Method | Axis | Group | Supported measured/eligible | Leakage measured/denominator | Median/p95 um | Worst run |
| --- | --- | --- | --- | --- | --- | --- |
| Epoch 124 existing | animal | TS169 | 7492/7508 | 654/4336 | 2.18/8.90 | 11 |
| Epoch 124 existing | animal | TS325 | 25598/27301 | 2505/12760 | 2.06/9.84 | 44 |
| Epoch 124 existing | animal | TS336 | 0/0 | 0/0 | unavailable/unavailable | 0 |
| Epoch 124 existing | qc | high | 7492/7508 | 654/4336 | 2.18/8.90 | 11 |
| Epoch 124 existing | qc | low | 21459/23064 | 974/9272 | 1.93/9.90 | 44 |
| Epoch 124 existing | qc | medium | 4139/4237 | 1531/3488 | 3.05/9.61 | 19 |
| Ordered alone | animal | TS169 | 6978/7508 | 160/4336 | 2.24/8.88 | 8 |
| Ordered alone | animal | TS325 | 23302/27301 | 1112/12760 | 2.05/7.67 | 29 |
| Ordered alone | animal | TS336 | 0/0 | 0/0 | unavailable/unavailable | 0 |
| Ordered alone | qc | high | 6978/7508 | 160/4336 | 2.24/8.88 | 8 |
| Ordered alone | qc | low | 19711/23064 | 392/9272 | 1.89/7.31 | 13 |
| Ordered alone | qc | medium | 3591/4237 | 720/3488 | 2.99/8.66 | 29 |
| Readability alone | animal | TS169 | 6335/7508 | 94/4336 | 2.12/8.70 | 11 |
| Readability alone | animal | TS325 | 22320/27301 | 1099/12760 | 2.03/9.90 | 44 |
| Readability alone | animal | TS336 | 0/0 | 0/0 | unavailable/unavailable | 0 |
| Readability alone | qc | high | 6335/7508 | 94/4336 | 2.12/8.70 | 11 |
| Readability alone | qc | low | 19470/23064 | 738/9272 | 1.92/10.13 | 44 |
| Readability alone | qc | medium | 2850/4237 | 361/3488 | 3.10/9.31 | 4 |
| Readability + ordered | animal | TS169 | 5942/7508 | 72/4336 | 2.24/8.64 | 8 |
| Readability + ordered | animal | TS325 | 20179/27301 | 544/12760 | 2.01/7.78 | 13 |
| Readability + ordered | animal | TS336 | 0/0 | 0/0 | unavailable/unavailable | 0 |
| Readability + ordered | qc | high | 5942/7508 | 72/4336 | 2.24/8.64 | 8 |
| Readability + ordered | qc | low | 17767/23064 | 296/9272 | 1.88/7.49 | 13 |
| Readability + ordered | qc | medium | 2412/4237 | 248/3488 | 2.94/8.36 | 0 |
| Entropy + signal | animal | TS169 | 7464/7508 | 240/4336 | 2.18/8.88 | 8 |
| Entropy + signal | animal | TS325 | 18635/27301 | 406/12760 | 1.83/6.77 | 19 |
| Entropy + signal | animal | TS336 | 0/0 | 0/0 | unavailable/unavailable | 0 |
| Entropy + signal | qc | high | 7464/7508 | 240/4336 | 2.18/8.88 | 8 |
| Entropy + signal | qc | low | 15633/23064 | 104/9272 | 1.71/6.29 | 4 |
| Entropy + signal | qc | medium | 3002/4237 | 302/3488 | 2.71/8.11 | 19 |
| Entropy + signal + ordered | animal | TS169 | 6978/7508 | 160/4336 | 2.24/8.88 | 8 |
| Entropy + signal + ordered | animal | TS325 | 18525/27301 | 344/12760 | 1.92/6.90 | 27 |
| Entropy + signal + ordered | animal | TS336 | 0/0 | 0/0 | unavailable/unavailable | 0 |
| Entropy + signal + ordered | qc | high | 6978/7508 | 160/4336 | 2.24/8.88 | 8 |
| Entropy + signal + ordered | qc | low | 15577/23064 | 104/9272 | 1.76/6.52 | 0 |
| Entropy + signal + ordered | qc | medium | 2948/4237 | 240/3488 | 2.80/8.06 | 27 |

## Exact common-support comparisons

| Exact common columns | n | Median A / B (um) | p95 A / B (um) | MAE A / B (um) | Gross A / B |
| --- | --- | --- | --- | --- | --- |
| Epoch 124 existing → Ordered alone | 29939 | 1.99 / 2.11 | 7.80 / 7.84 | 3.26 / 3.47 | 136 / 92 |
| Epoch 124 existing → Readability + ordered | 25824 | 1.95 / 2.06 | 7.70 / 7.79 | 3.26 / 3.51 | 96 / 53 |
| Entropy + signal → Readability + ordered | 21577 | 1.85 / 1.96 | 7.08 / 7.44 | 2.49 / 2.57 | 7 / 8 |
| Readability alone → Readability + ordered | 25824 | 1.95 / 2.06 | 7.70 / 7.79 | 3.26 / 3.51 | 96 / 53 |

## Approximate readable-gate coverage match

| Method | Training quantile | Actual readable gate coverage | Supported coverage | Leakage | p95 (um) | Worst run |
| --- | --- | --- | --- | --- | --- | --- |
| learned | 0.99 | 95.22% | 91.05% | 8.77% | 9.28 | 44 |
| simple | 0.98 | 94.61% | 83.35% | 5.65% | 7.51 | 19 |

## Readability supervision audit

| Split | B-scans | Weak positive | Explicit negative | Unknown | Strong local positive |
| --- | --- | --- | --- | --- | --- |
| train | 72 | 4548 | 7586 | 24730 | 0 |
| validation | 38 | 2782 | 2137 | 14537 | 0 |

## Useful supported positions lost by combined method

| Surface | Supported lost | Old error ≤5 um lost | Due to readability | Another boundary fails entropy |
| --- | --- | --- | --- | --- |
| GCL_IPL | 884 | 684 | 486 | 189 |
| ILM | 818 | 613 | 335 | 278 |
| INL_OPL | 986 | 646 | 477 | 166 |
| IPL_INL | 865 | 365 | 258 | 107 |
| OPL_ONL | 937 | 719 | 481 | 236 |
| PR_RPE | 944 | 785 | 532 | 222 |
| RNFL_GCL | 1022 | 649 | 417 | 229 |
| RPE | 810 | 769 | 560 | 209 |

## Machine-readable detail

`boundary_thickness_by_stratum.csv` includes all surfaces, bands, animal/QC/biology/scope strata, signed biases, coverage, gross and failure-or-withheld fractions. `per_bscan_surface_and_thickness.csv` includes worst-run start/end coordinates. `paired_common_support.csv` includes every layer on identical endpoint sets. `coverage_error_curves.csv` contains all 36 fixed-grid points; `matched_coverage.csv` reports achieved matches and mismatches on three separate coverage axes. `per_bscan_summary.csv` retains rejected/ineligible cases rather than excluding them.
