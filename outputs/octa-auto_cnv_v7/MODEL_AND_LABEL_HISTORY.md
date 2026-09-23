# Model and label history



Refreshed 2026-09-18T03:04:40.737196+00:00. Live source paths, SHA-256 hashes, native source identities, region decisions, uncertainty, revisions and scope are in `reports/historical_labels.json`. Precedence is in `reports/precedence.json`.



| Release | Evidence and interpretation |
|---|---|
| v1 | Thickness-deficit/background-reference pilot: 17 TS267 acquisitions, 13 proposals, 0/7 legacy locations matched within 75 µm. |
| v2 | Integrated detector/reviewer: 220 proposals, 7/7 location matches, large false-suggestion burden. |
| v3 | Stricter structural/shape heuristic: 29 proposals, 6/7 matches. Sparse development location matching is neither validated sensitivity nor exact biological lesion identity. |
| v4 / v5 | Annotation improvements over unchanged v3 suggestions; no new detector training. V5 added actual OCTA and explicit whole-field completion. This CNV footprint editor is distinct from the layer-boundary model/editor. |
| v6 | Nine independently trained compact 2D U-Nets: A/B/C × seeds 267/268/269. A: structural OCT + OCTA (2 channels); B: A + 8 availability maps + shadow (11); C: B + 8 numerical thickness maps (19). |
| v7 | Manual footprint/whole-field collection GUI. New confirmations only count toward the 30-positive-image target. No model training or new cohort inference. |


Live v5 audit: 15 saved acquisitions, 14 completed fields, 25 kept nonempty CNV entries, 8 Unsure entries, 1 incomplete field. Positive/uncertain conflicts total 34 pixels (D0 OD). These conflicts stay ignored. Twenty-five entries include repeated visits; they are not 25 independent lesions.

D0 OS remains partial. D28 OS and D35 OS have no saved v5 record. Missing files and partial unmarked fields are never negative labels. Historical reviewed absence has limited timing evidence; no new biological adjudication has occurred.

Original CNV NPZ files: 28; v3: 1; v4: 1. Original-classification records are also inventoried because explicit Normal/Other decisions can override inherited footprints.

Current v6: 2 saved acquisitions, 9 region records, 0 new explicit model ratings and 0 finished new original-prediction rating reviews. Finish this review does not certify whole-field background. Model ratings are not masks; untouched original predictions are never human truth.



## V6 training and model evidence



Widths 16/32/64/128 with a 256-channel bottleneck, GroupNorm and mirrored decoder; masked BCE/Dice, native 256-pixel tiles, overlapping full-field inference. Training visits D0/D7/D14/D28/D35/D42; validation D49; development holdout D56/D98. Nine acquisitions supplied training pixels, all TS267. Both eyes were grouped by visit; thresholds/checkpoints were validation-selected.

Across three seeds, mean holdout Dice A 0.678, B 0.584, C 0.733. C recovered all six holdout lesion entries in each seed, with false suggestions and outline errors. The same animal and repeated lesion entries were evaluated: this does not establish new-animal performance or refute excessive detections elsewhere.

B/C inference is complete on 324 acquisitions from 11 animals: 1,944 prediction sets. B thresholds are 0.7/0.1/0.8 for seeds 267/268/269; C uses 0.5 for each. Scores are uncalibrated. Inference is not validation. The optional C/267 overlay is a context choice, not a best-seed claim. Checkpoints and thresholds remain in the provenance-linked v6 models.json.

The September 13 handoff and pilot-plan statements that no U-Net existed, and their older completion counts, are historical and superseded by the implemented v6 and the live inventory.



## Source precedence and future export



Use one sample per exact native acquisition. A valid v7 whole-field revision supersedes older footprint targets for that source. A newer v7 draft/deferred record blocks automatic fallback and requires reconciliation. If no v7 record exists, prefer valid v5 > v4 > v3 > original footprint evidence with its original completion scope. Explicit original classifications and uncertainty remain constraints; v6 human error masks require adjudication against the selected footprint source. Never silently union disagreeing sources. Reports retain all superseded paths and hashes.

The optional GUI historical overlay selects one matching v5/v4/v3/original source, with uncertainty separate. It is read-only and has no automatic copying into editable regions. V6 human error records remain in the inventory for future adjudication rather than being silently combined with those references.

No transfer across repeat acquisitions without validated registration. Original labels span TS241, TS247, TS250, TS267, TS283, TS305, TS325, TS328 and TS336; evidence is context, not a prerequisite for queue membership. Original files stay unchanged.



Current v7 collection: 0 confirmed positive images; 0 confirmed no-CNV images. Synthetic tests, browsing, regions and historical approvals do not count.
