# CNV v8 exploratory comparison

Open `OPEN_OCTA_AUTO_CNV_V8.cmd` for the read-only, shared 30-acquisition viewer. This release predicts native en-face CNV footprints, not axial lesion volumes.

**Scope:** 10 training/reference acquisitions and 20 acquisitions excluded from fitting and historical CNV-label sources. All ten non-WT animals have training exposure. There is no cross-validation, held-out validation study, cohort-wide new inference, improved-accuracy claim, or new-animal generalization claim.

Frozen supervision: 67 native acquisitions; selected source counts {'v7': 37, 'original': 16, 'v5': 14}. The v7 contribution is 30 confirmed positives and seven confirmed negatives; four deferred acquisitions block fallback and are excluded. Two v7 Unsure areas remain unknown. Older incomplete fields provide confirmed positive pixels only. Source documents, hashes, revisions, eye, animal and visit are retained in data/manifest.json and data/sources/.

Precedence selects one source per acquisition: valid v7 > valid v5 > v4 > v3 > reviewed original. V7 draft/deferred records block older fallback. Disagreements are not silently unioned. V6 predictions and ratings never supply target labels. Actual sampling chooses animals uniformly, then uniformly among acquisitions eligible for the requested patch category; each model complete.json includes realized per-animal and per-acquisition counts.

The historical v6 release trained A/B/C configurations at seeds 267/268/269 using within-TS267 visit partitions and validation-selected checkpoints/thresholds. V8 uses the frozen C/267 output as comparison context and trains two fresh models at seed 267 on the expanded manual dataset. C/267 is the requested context, not a best-seed claim.

| Property | Frozen v6 | V8 Model 1 | V8 Model 2 |
|---|---|---|---|
| Training evidence | Nine labeled training acquisitions, all TS267; visit-based validation/checkpoint selection | Expanded multi-animal audited manual evidence, including v7 whole-field confirmations | Same audited evidence and animal balancing |
| Input | C: structural OCT, actual OCTA, automatic availability/shadow and thickness | Same 19-channel C recipe; fresh weights | Five adjacent native structural B-scans only; fresh weights |
| Network | Compact U-Net 16/32/64/128/256, GroupNorm | Same compact U-Net | Distinct four-stage 16/32/64/128 CNN, GroupNorm, SiLU, stagewise axial attention pooling and 1D head |
| Selection | Validation-selected checkpoint and threshold | Scheduled epoch 100; provisional threshold 0.70 | Scheduled epoch 100; threshold 0.50 |
| Display | Frozen C/267 context | One-pixel disk opening, then remove 8-connected components below 64 pixels | No component size/shape filter |

Both models used seed 267, AdamW (learning rate 0.001, weight decay 0.0001), 100 epochs, 32 optimizer steps per epoch and effective batch size four. Mixed precision uses microbatch one and four-step accumulation. Checkpoints retain optimizer, scaler and Python/NumPy/PyTorch/CUDA/sampler RNG states. The final scheduled checkpoint is used; there was no early stopping or preview-based threshold tuning.

Model 1 uses masked BCE with positive weight 1 and negative weight 2, plus 0.5 masked Dice on positive patches. Requested patch proportions are 50% positive, 25% ordinary reviewed background and 25% frozen-v6 difficult reviewed background. Difficult patches contain no confirmed positives; unavailable difficult pools fall back to ordinary background. V6 supplies sampling locations only.

Model 2 uses masked BCE plus masked Dice, equal positive/background patch sampling, lateral flips, neighbor-order reversal and modest intensity changes. No axial flips or rotations are augmentations. Canonical orientation comes from established detect_orientation/prepare_bscan functions. Full depth and original axial resolution are retained; no RPE flattening or layer-based crop is applied. Its input tensors contain no en-face projections, OCTA, thickness, retinal surfaces, v6 predictions, or handcrafted candidates.

Automatic measurements retain NaNs. Model 1 alone fills unavailable normalized thickness with neutral zero and supplies availability channels. Exclusion masks affect the loss only. Both normalizations were fitted only to training inputs; structural normalization uses a fixed regular subsample of full-depth training volumes.

The fixed Model 1 display policy would remove 438 of 175,684 known positive training pixels (0.25%) if applied to those footprints. This is a diagnostic: human targets were never filtered. Per-acquisition effects are in reports/display_policy_training_impact.json. Legitimate small or irregular lesions can be suppressed. Unusual shape alone is not proof of a false detection. Scores, pre-filter threshold masks, removed-pixel reason maps and removed components remain available.

The intended structural evidence includes RPE disruption/displacement, nearby hyperreflective dots and continuity across B-scans. These are learned only through manual footprint supervision; no separate feature annotations exist. No independently validated RPE-disruption or dot detector is claimed. Attention is an explanatory aid, not axial segmentation or proof of reasoning.

Fit diagnostics only: Model 1 mean patch loss changed from 1.3166 to 0.1620; Model 2 from 1.3355 to 0.6787. These values are not validation metrics or directly comparable across loss definitions.

Training-case Dice/IoU, missed/extra components and false-positive area are recorded for the ten reference acquisitions in reports/training_case_comparisons.csv and the viewer. Scoring is restricted to reviewed coverage. Component matching uses 8-connectivity and any reviewed-pixel overlap; it does not adjudicate biological lesion identity. The twenty unlabeled acquisitions have prediction descriptions and optional reviewer observations only, never accuracy metrics.

The viewer links native B-scan navigation to all footprints and lateral bands. Manual truth is read-only. Ignored areas are hatched as unknown; predictions inside them are retained in unknown_score arrays. Browser-local comparison notes are separate and can be exported as JSON; they do not change labels or trigger retraining.

Acceptance evidence: verification/contracts.json, sanity.json, comparison_checks.json, preservation_after.json and viewer_checks.json. All old CNV release files were checked for unchanged size/mtime; old text/code/original annotations and consumed prediction/checkpoint inputs additionally have cryptographic checks. Each consumed processed source has a full SHA256 in its native cache manifest, in addition to inherited sampled source identity. New cache and predictions live only in v8; no RAW reconstruction occurred.

Training-case comparison summary: arithmetic means over the ten training/reference acquisitions only. These are descriptive fit comparisons, not validation results.

| Footprint | Mean Dice | Mean extra components | Mean false-positive pixels in reviewed coverage |
|---|---:|---:|---:|
| v6 | 0.313 | 2.3 | 5939.7 |
| model1_raw | 0.547 | 3.9 | 1829.8 |
| model1_filtered | 0.553 | 1.5 | 1771.7 |
| model2 | 0.237 | 137.1 | 17235.7 |

The structural model produces many additional fragments within reviewed training coverage at its fixed 0.50 threshold. This is a material limitation of this initial fit and a priority for human review. Its raw behavior is preserved; these observations did not alter training, thresholds or postprocessing. The twenty unlabeled acquisitions are excluded from this table and have no accuracy scores.


Next decision belongs to human review: revise a model, collect feature-specific B-scan labels, or begin formal animal-grouped validation. This release stops at the shared comparison set.

Browser acceptance passed: reference and unlabeled cases, native rows 0/511, map-click navigation, independent overlays, full-depth display, suppression reasons, and separate note persistence/export. Screenshots are in screenshots/; verification/browser_qa.json records the checks. The temporary QA note was cleared.
