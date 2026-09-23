# Model 3 completed

Trained on the requested **101 unique acquisitions: 73 confirmed positive and 28 confirmed no-CNV scans**, containing **156 kept CNV region observations**. All 101 scans were sampled. The inventory snapshot, source hashes, exact native targets and ignored-pixel masks are saved in `data/`.

Both Model 2 and Model 3 completed inference on **all 324 processed acquisitions**. Open **OPEN_GALLERY.cmd** for the separate comparison at http://127.0.0.1:8803. Manual confirmed CNVs have an independent overlay checkbox. The new **no CNVs present** checkbox saves a whole-field absence verdict to a separate review namespace.

Model 3 is a fresh retraining of Model 2’s 30-channel architecture using its unchanged loss, seed, optimizer, 100 epochs / 3,200 steps, animal-balanced sampling and thresholds. Normalization uses only the specified training scans. Three additional animal-excluded networks supply predictions to fit the new candidate scorer; they are not an independent evaluation of the final adjusted model.

| Inference output | Model 2 | Model 3 |
|---|---:|---:|
| Raw candidates | 906 | 606 |
| Displayed adjusted candidates | 445 | 428 |
| Scans with no displayed candidates | 101 | 106 |

These are prediction counts, not confirmed lesion counts or accuracy estimates. The gallery explicitly marks training scans. All raw probabilities and down-ranked candidates remain available.

Verification passed for 324 native grids, both models’ candidate-mask parity, all 101 manual-reference overlays, training/scorer provenance and unchanged source annotations. Frozen Model 2 predictions also matched the 50 existing comparison predictions.

Historical vessel-context exclusions were retained as missing context for two scans. One belongs to the explicit user-selected 101-scan cohort; its confirmed CNV-negative target is included as requested. The older excluded vessel annotations were not consumed. No model-finalization decision has been made.

Weights, normalization, scorer and training contract: `bundles/v9_m3/`. Resume checkpoints and complete logs: `fits/`. Verification: `FINAL_VERIFIED.json`.
