# Three-seed sensitivity check

The recipe, visit partitions, sampling budget and architecture were unchanged. Seeds 267, 268 and 269 were each trained independently for A, B and C. Each checkpoint and threshold was selected using D49 only. Repeating seeds does not provide additional independent animals or lesion instances.

| Model / seed | Holdout recalled entries | False suggestions | Known-pixel Dice | Correction proxy |
|---|---:|---:|---:|---:|
| A / 267 | 5/6 | 3 | 0.700 | 5 |
| B / 267 | 6/6 | 5 | 0.638 | 6 |
| C / 267 | 6/6 | 2 | 0.744 | 6 |
| A / 268 | 5/6 | 12 | 0.664 | 5 |
| B / 268 | 6/6 | 2 | 0.712 | 6 |
| C / 268 | 6/6 | 2 | 0.698 | 6 |
| A / 269 | 6/6 | 3 | 0.670 | 6 |
| B / 269 | 5/6 | 0 | 0.402 | 5 |
| C / 269 | 6/6 | 6 | 0.757 | 5 |

Mean and range below describe optimization variability on these same three scans; they are not confidence intervals.

| Model | Dice mean (range) | Mean missed entries | Mean false suggestions |
|---|---:|---:|---:|
| A | 0.678 (0.664–0.700) | 0.67 | 6.00 |
| B | 0.584 (0.402–0.712) | 0.33 | 2.33 |
| C | 0.733 (0.698–0.757) | 0.00 | 3.33 |

These are within-TS267 development results. B vs A tests availability plus shadow together; C vs B adds observed thickness. Border correction and artifact errors remain, and practical time savings are unmeasured. No seed was selected using holdout performance; the primary delivered overlays remain seed 267.
