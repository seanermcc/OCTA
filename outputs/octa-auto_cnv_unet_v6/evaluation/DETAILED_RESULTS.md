# Detailed development comparison

These summaries use the primary seed (267) and the same prespecified 0.1 IoU one-to-one matching. All stricter 0.25/0.5 sensitivity results remain in `comparison.csv` and `per_scan.csv`. Empty-negative Dice is undefined; false-positive area/count is reported instead.

| Model | Holdout mean matched border error (µm) | Mean absolute count error / scan | Mean absolute area error / scan (mm²) | Merges | Splits |
|---|---:|---:|---:|---:|---:|
| A | 17.20 | 0.67 | 0.0047 | 0 | 0 |
| B | 20.01 | 1.67 | 0.0077 | 0 | 0 |
| C | 16.68 | 0.67 | 0.0058 | 0 | 0 |
| v3 | 8.17 | 0.33 | 0.0107 | 0 | 0 |

Border errors include only matched pairs whose reference outline is wholly reviewed and not FOV-clipped, and whose prediction does not touch ignored pixels. This conditional error excludes missed lesions and should be read with recall. Merges/splits use the prespecified overlap graph.

| Model | Recall in low-availability lesions | Recall in other lesions |
|---|---:|---:|
| A | 3/4 | 2/2 |
| B | 4/4 | 2/2 |
| C | 4/4 | 2/2 |
| v3 | 2/4 | 1/2 |

Low availability means a mean available fraction below 0.5 across all eight layers within the reviewed footprint. It is a descriptive measurement-support stratum, not scan-quality ground truth.

| Model | False suggestions | Mean vessel fraction | Mean shadow fraction | Mean low-signal fraction |
|---|---:|---:|---:|---:|
| A | 3 | 0.0% | 5.6% | 0.0% |
| B | 5 | 14.2% | 16.9% | 0.0% |
| C | 2 | 0.0% | 7.6% | 1.0% |
| v3 | 4 | 0.0% | 0.7% | 0.0% |

These are average spatial overlaps with automatic artifact masks, not adjudicated error causes. Per-component fractions and sizes are in `false_positive_artifacts.csv`. B-scan inspection is provided in the depth atlas.

All six holdout lesion entries are OD. The one completed OS holdout field has zero primary-seed A/B/C suggestions and one v3 suggestion; this does not rule out an eye shortcut. Numeric eye/visit/animal/coordinate channels were excluded, but image anatomy and acquisition appearance can encode them.

Human review actions and times have not been collected for these model suggestions. Existing historical GUI times are preserved in the annotation audit but cannot measure the new models’ review burden.
