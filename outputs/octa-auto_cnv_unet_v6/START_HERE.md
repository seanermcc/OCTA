# CNV U-Net v6: within-TS267 suggestion pilot

Three experiments were each trained with three random initializations: nine separate trained U-Nets. These are suggestions for human review. Later-visit evaluation observes the same animal and potentially the same lesions; it cannot establish generalization to other animals. The upstream layer model used ALL_LABELLED data including TS267.




Across three matched seeds on the same holdout scans:

| Inputs | Mean Dice (range) | Mean missed entries, of six | Mean false suggestions over three scans |
|---|---:|---:|---:|
| A | 0.678 (0.664–0.700) | 0.67 | 6.00 |
| B | 0.584 (0.402–0.712) | 0.33 | 2.33 |
| C | 0.733 (0.698–0.757) | 0.00 | 3.33 |

C recovered all six held-out lesion entries in every seed and had higher Dice than A in all three matched runs. B did not consistently improve over A. C still produced 2–6 false suggestions and 5–6 matched outlines needing correction by the predefined proxy per run. Thus C is promising for review suggestions, while adding availability and shadow without numerical thickness has no consistent benefit here. B adds availability and shadow together, so this cannot identify the effect of missingness alone.

These are the same six lesion entries repeatedly scored, not 18 independent lesions. Review corrections remain substantial, and no human time saving has been measured.

![Three-seed comparison](evaluation/seed_comparison.png)

## Saved results

[Open the review guide](review/REVIEW_GUIDE.md). Run `OPEN_REVIEW.cmd` to inspect suggestions with linked B-scans and record actual review actions and focus-active time. Predictions are separate from human annotations.

Audit: 15 saved files, 14 completed fields, 25 kept lesion entries; 14 scans provide supervision. D0 OS remains partial; D28 OS and D35 OS have no saved v5 file. Those three provide predictions but no negative training labels. D0 OD has 34 conflicting positive pixels, which are excluded. Human files remained unchanged.

## Development holdout: D56 and D98

| Model | Recall (IoU ≥ 0.1) | FP / completed scan | Precision | Known-pixel Dice | Additions* | Removals* | Outline corrections* |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 5/6 | 1.000 | 0.625 | 0.700 | 1 | 3 | 5 |
| B | 6/6 | 1.667 | 0.545 | 0.638 | 0 | 5 | 6 |
| C | 6/6 | 0.667 | 0.750 | 0.744 | 0 | 2 | 6 |
| v3 | 3/6 | 1.333 | 0.429 | 0.582 | 3 | 4 | 2 |

*Action counts are comparison-derived proxies, not observed human edits. Human review time for these new model suggestions has not yet been measured. No time saving is inferred. The reviewer records additions, removals, outline corrections, acceptances and focused review time separately.

The unchanged v3 comparison uses its saved candidate cores, which were the actual displayed suggestions. They are often smaller than full reviewed lesion footprints. Its whole-footprint Dice therefore tests that mismatch as well as detection; the v3 heuristic was not retrained or retuned.

## Training and validation

A uses structural OCT and actual OCTA (2 channels). B adds eight automatic availability masks and automatic shadow together (11). C adds eight numerical thickness maps (19). Any B–A improvement concerns the combined availability-plus-shadow inputs. Isolating missingness requires another ablation.

Each model uses four encoder stages (16/32/64/128), a 256-channel bottleneck, GroupNorm and a mirrored decoder. AdamW starts at 0.001 with 0.0001 weight decay. Native 256×256 tiles are acquisition-balanced with positive/negative sampling; inference uses 128-pixel stride and weighted overlap. There are no lesion-count caps or circularity filters.

Training visits: D0/D7/D14/D28/D35/D42; validation: D49; development holdout: D56/D98. Both eyes remain grouped by visit. Checkpoints and score thresholds use validation only. The overlapping epoch sampling schedules were verified identical across A/B/C. Primary overlays use seed 267. Matched repeats at seeds 268 and 269 are also complete; see [the three-seed report](evaluation/SEED_REPORT.md). Seeds quantify optimization variability, not independent biological replication. No seed was chosen using holdout results.

Preflight: 5 contract tests passed. The real two-tile overfit reached Dice 1.000. All-unknown losses, negative BCE, missing-thickness fill, native masks, one-to-one matching and blended full-field inference were tested.

## Input provenance and limitations

All eight thickness outputs retain their established endpoints. Full retina is ILM to the outer RPE edge; photoreceptor composite includes ONL. Saved thickness NaNs remain NaNs. Only normalized model tensors use zero fill, paired with availability channels. Finite means available under the experimental policy, not validated reliability.

Automatic thickness is recovered from the frozen raw neural branch and automatic trace-denial, crossing/out-of-crop and shadow guards. External human corrections, embedded denials, regional unreliability and contextual estimates are excluded. All 512 raw neural records per scan were compared with the preserved branch. Automatic vessel provenance and absence of human ONH influence were checked. Human CNV geometry in upstream bundles is never passed to the model.

Actual OCTA is the mean dB projection over the saved retinal depth crop, not a layer-specific slab. It shares the exact source/grid/crop with structural OCT. Cache orientation was freshly detected when created and is preserved with source and geometry fingerprints; no lateral flip/transpose is used. Independent checks on one training, validation and holdout acquisition freshly redetected orientation and reproduced the complete OCTA projection plus three structural B-scans exactly (maximum absolute difference 0 dB). Processed-volume integrity uses the upstream explicitly sampled hash; derived arrays, checkpoints and annotations have full SHA-256 hashes.

All kept CNVs are OD. See `evaluation/eye_strata.csv` for OD/OS results; good performance on OS negatives does not rule out eye-associated shortcuts. Identity, eye, visit, coordinates, heuristic masks, and human-derived region maps are not input channels.

## Thickness and missingness

See `patterns/REPORT.md` and the per-lesion/per-layer tables. Geometric interiors use 25 µm erosion with 10/50 µm sensitivity checks; they are not biological cores. Perilesional tissue is not assumed healthy. Same-field nonlesion comparisons stratify signal, shadow, vessel, position and edge proximity. Repeated lesions and pixels are not independent subjects.

## Depth review before changing architecture

See `review/DEPTH_LIMITATION.md` and the depth atlas. Mean projections collapse axial location and layer relationships, so they cannot distinguish structures that overlap laterally at different depths. Native B-scans accompany persistent errors. A human depth-dependence judgment remains separate from model disagreement; do not assume a larger 2D network supplies missing depth information.

## Next useful labels

Prioritize persistent misses, artifact-rich false suggestions, disputed outlines and image/mask model disagreements, with the fixed random sample retained. Add new animals, positive and negative eyes, poor-signal controls and lesions with unavailable thickness. Further annotation was not required to run this pilot. Any later training that uses the inspected holdout labels must call them development data.

Sigmoid scores are uncalibrated model scores, not calibrated biological certainty.

Reproduce or resume with `RUN_PILOT.cmd`. The data manifest, normalization, protocol, model configurations, optimizer/RNG checkpoints, histories, native score maps, raw components and complete per-scan metrics remain under this release.

[Border, count, area, low-availability and artifact results](evaluation/DETAILED_RESULTS.md) · [Observed thickness summaries](patterns/AVAILABLE_THICKNESS.md) · [Annotation and input audit](ANNOTATION_AND_INPUT_AUDIT.md).
