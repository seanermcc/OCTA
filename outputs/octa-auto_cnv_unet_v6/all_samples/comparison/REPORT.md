# Six-model comparison

324 acquisitions have all six outputs. 11 animals. These are descriptive expanded-cohort predictions, not independent validation.

| Model | Suggestions | No-suggestion scans | Median count | Total suggested area mm² |
|---|---:|---:|---:|---:|
| B_267 | 1512 | 18 | 4 | 9.7285 |
| B_268 | 870 | 53 | 2 | 14.1385 |
| B_269 | 496 | 121 | 1 | 3.5065 |
| C_267 | 1027 | 67 | 3 | 11.1612 |
| C_268 | 1544 | 37 | 4 | 15.7240 |
| C_269 | 1855 | 3 | 5 | 16.5318 |

[Navigable overlays](index.html) · [Every paired comparison](pairwise_spatial_agreement.csv) · [Inconsistent suggestions](inconsistent_suggestions.csv) · [Review queue](review_queue.csv)

Both-empty spatial comparisons are recorded as empty, with Dice/IoU undefined. All native predictions and components remain available; no lesion size, count or shape filters are applied. Total suggested area sums acquisition footprints, including repeated tissue; it is not unique disease burden. Seed variability includes both learned weights and each seed’s original validation-selected threshold (B: 0.7 / 0.1 / 0.8; C: 0.5 / 0.5 / 0.5 for seeds 267 / 268 / 269). Thresholds were not harmonized or tuned on these scans.

Area and boundary-distance units use the frozen approximate lateral scale of 1460 micrometers across 512 pixels; no per-animal magnification recalibration was performed.

Audited existing annotations support comparisons on 31 scans; 14 have v5 whole-field completion. Missing annotations never represent negative labels. Legacy references are positive-only and use connected footprint components when original instance identity is unavailable.

On positive-only references, high known-pixel overlap can mean that the prediction covers the labeled lesion; unreviewed surrounding tissue cannot establish false-suggestion or outline accuracy. Use the annotation-completeness strata when interpreting these values.

Evaluation follows the frozen v6 ignored-region, one-to-one matching and boundary definitions at IoU 0.1/0.25/0.5. Additions, removals and outline corrections in evaluation tables are comparison-derived proxies. No observed human actions or time savings are inferred. Some completed OS references have brief historical review times; their completion metadata is retained from v6, without new adjudication.

Seeds, repeated acquisitions and repeated visits are not independent animals. Pilot train, validation and development-holdout scans are identified separately. New acquisitions of TS267 retain exposure to the CNV training animal. The upstream ALL_LABELLED layer model contains all historically imaged animals; per-scan exposure and unknown values are retained.

Mean projections discard axial position and layer relationships. Disagreement alone cannot establish that depth is needed. Review native B-scans for persistent misses, artifacts, low support and field edges before proposing architectural expansion. The GUI supports every native B-scan; exported depth thumbnails are illustrative rows, not a substitute for whole-field review.
