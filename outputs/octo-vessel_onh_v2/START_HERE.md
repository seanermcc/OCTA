# Major vessels and ONH — experimental learned v2

**Release status: complete.** 312/312 eligible predictions verified; 2 excluded; gallery verified: True. `RUN_OR_RESUME.cmd` continues a matching interrupted run.

Annotation snapshot: 2026-09-14T23:21:37-04:00. Human annotations and frozen v1 outputs remain external read-only sources; the exact annotation bytes are archived in `data/source_annotations_snapshot.zip`.

## Annotation inventory

42 saved records: 40 eligible vessel reviews and 38 assessable ONH reviews (22 visible/partial and 16 reviewed absence). Two explicitly poor-quality acquisitions are excluded from all training, tuning, evaluation and analysis. Cannot judge is not absence.

## Independent development evaluation

Each row uses a network trained without the evaluated animal or its calibration animal. Calibration selects checkpoints, thresholds and ONH component filtering. Final all-label predictions are never included in these accuracy figures.

| Evaluated animal | Calibration animal | Vessel cases | v1 vessel Dice | Learned vessel Dice | ONH positive Dice | ONH false detections / absent cases |
|---|---|---:|---:|---:|---:|---:|
| TS165 | TS169 | 2 | 36.2% | 84.5% | 92.1% | 0/0 |
| TS169 | TS241 | 4 | 40.9% | 68.6% | 42.5% | 3/3 |
| TS241 | TS247 | 11 | 27.8% | 38.8% | 42.1% | 5/7 |
| TS247 | TS267 | 8 | 30.9% | 64.4% | 49.8% | 0/3 |
| TS250 | TS241 | 10 | 37.7% | 79.1% | 48.9% | 0/0 |
| TS267 | TS169 | 5 | 37.3% | 83.0% | 52.4% | 1/3 |

### Counts by model role

| Held-out animal | Training vessel / ONH | Calibration vessel / ONH | Evaluation vessel / ONH |
|---|---:|---:|---:|
| TS165 | 34 / 33 | 4 / 4 | 2 / 1 |
| TS169 | 25 / 23 | 11 / 11 | 4 / 4 |
| TS241 | 21 / 20 | 8 / 7 | 11 / 11 |
| TS247 | 27 / 26 | 5 / 5 | 8 / 7 |
| TS250 | 19 / 17 | 11 / 11 | 10 / 10 |
| TS267 | 31 / 29 | 4 / 4 | 5 / 5 |

The separate final model uses all 40 eligible vessel and 38 eligible ONH reviews. Its fit is not evaluated as independent accuracy.

Equal-animal vessel Dice: **35.1% v1 → 69.7% learned**. Pooled-pixel Dice: 32.9% → 61.4%.
Paired equal-animal improvement: 34.6 percentage points. Exploratory animal bootstrap interval: 23.9 to 43.8 points. Only six animals; this is not a prospective validation guarantee.
Vessel scoring covers **7.6% of the 40 reviewed images** (793,364 pixels), concentrated on brush edits. These are conditional correction-region metrics, not exhaustive vessel recall, capillary density, or whole-image precision.
ONH positive-case mean Dice: **49.8%** across 22 cases. Reviewed-absence false detections: **9/16**; total false area 42,008 native pixels. Absence detection means any surviving predicted ONH in the reviewed negative region.

## Baseline assistance and interpretation

Frozen v1 had existing human ONH exclusions on 0/40 evaluation scans. Its broader batch can use human ONH assistance, but no evaluated scan in this snapshot received it. It is not an automatic ONH method. The learned evaluation uses its own ONH predictions. Both vessel masks are scored on identical supervision. The supplementary common-ONH-exclusion vessel-head comparison is saved separately in metrics.json; it excludes reviewed/frozen ONH from both scorings and does not alter either original mask.

## Supervision policy

Vessels: positive = completed review AND recorded direct brush footprint AND final vessel. Negative = completed review AND recorded brush footprint AND final non-vessel. Uncertain areas, ONH pixels and ONH-derived-only removal pixels are excluded. Untouched automatic pixels are ignored even under a completed review flag. Inherited brush provenance remains recorded and cannot be reconstructed. This conservative policy does not infer a caliber cutoff from ambiguous small branches.
ONH: completed visible/partial reviews provide their footprint and reviewed complement, minus uncertain regions. Completed Outside image provides negatives. Unreviewed, Not assessed and Cannot judge provide no ONH targets. Excluded scans provide no target for either head. Saved masks never substitute for model predictions.
Every supervision archive contains explicit positive, negative and ignored arrays. Images are reduced 512→256 by area averaging; supervision retains separate positive and negative pixel mass in every 2×2 block. Thus an unknown pixel does not become a negative when resizing. Full-field dihedral and mild intensity augmentation are applied only to training animals.

## Important failures to inspect

### Lowest vessel scores

- TS241_OS_2024-09-11_D28_s03_103730: learned Dice 23.0%, v1 34.2%, scored area 16.7%.
- TS241_OS_2024-09-04_D21_s02_105432: learned Dice 26.2%, v1 20.7%, scored area 17.7%.
- TS241_OS_2024-08-21_D7_s04_111135: learned Dice 28.3%, v1 18.8%, scored area 14.2%.
- TS247_OD_2024-10-17_beforelaser_s01_103017: learned Dice 31.3%, v1 12.9%, scored area 11.6%.
- TS241_OD_2024-08-21_D7_s08_123208: learned Dice 33.4%, v1 22.9%, scored area 34.8%.
- TS241_OS_2024-09-25_D42_s03_104848: learned Dice 33.6%, v1 20.2%, scored area 14.6%.

### Lowest positive ONH scores

- TS241_OS_2024-09-11_D28_s03_103730: Partially visible — outlined, Dice 0.0%.
- TS247_OD_2024-11-20_D35_s01_112538: Partially visible — outlined, Dice 0.0%.
- TS250_OD_2026-03-20_D24_s03_142449: Visible — outlined, Dice 16.4%.
- TS241_OS_2024-09-04_D21_s04_110832: Partially visible — outlined, Dice 17.6%.
- TS267_OD_2025-02-19_D0_s02_112013: Partially visible — outlined, Dice 27.2%.
- TS247_OD_2024-10-17_beforelaser_s07_111201: Partially visible — outlined, Dice 31.4%.

## Visual review and release decision

**Do not replace frozen v1 with this U-Net release.** The improved score on sparse brush-edited regions does not establish better whole-image masks. Browser inspection found substantial added vessel false positives in background texture and acquisition borders, along with poor partial-ONH detection. The user also reports that the new masks look worse than frozen v1 overall.
Representative comparisons: TS165_OS_2025-04-29_WT_s06_123911 shows a good held-out central ONH match; TS241_OS_2024-09-11_D28_s03_103730 misses a partial ONH and adds border/background vessel predictions; TS169_OD_2025-01-14_D35_s05_113034 has false ONH regions despite reviewed absence; TS336_OD_2026-06-16_D42_s05_134542 shows extensive vessel predictions in background texture on an animal absent from training. These are qualitative observations, not new whole-image accuracy measurements.
The practical next step discussed with the user is to finish correcting the flagged frozen-v1 queue and review the remaining v1 proposals for acceptance as major-vessel masks. Human-corrected, explicitly accepted automatic and still-unreviewed masks must retain distinct provenance. Vessel acceptance does not establish a completed ONH assessment. The two explicitly rejected scans remain excluded. No acceptance flags, annotations, composite analysis inputs or downstream releases have been changed by this run.

## Model and deployment limits

A compact U-Net with separate vessel/ONH outputs learns directly from the structural en-face images; no automatic masks are used as targets or inputs. It starts from random weights. The sparse-mask loss computes errors only on supplied evidence. Architecture background: [original U-Net paper](https://arxiv.org/abs/1505.04597).
Native 512×512 coordinates are preserved in exported masks. Raw sigmoid outputs are stored as float16 on the 256×256 model grid and restored with bilinear interpolation, align_corners=False. This introduces limited numerical quantization and a resolution tradeoff; the exact stored arrays regenerate the delivered masks. ONH takes precedence over vessels after the calibrated ONH component filter.
The six reviewed animals and issue-selected review queue do not represent all 11 cohort animals or all acquisition qualities. Ten of 22 ONH-positive cases are TS250. Narrow vessels and seams can be confused; correction-region metrics cannot establish exhaustive generalization. The model has no validated acquisition-quality rejection mechanism. Poor results remain experimental predictions and are not promoted into downstream analyses.
0 annotation records were added or changed after the frozen snapshot; those later revisions are not silently included. See annotation_changes_since_snapshot.json.

## Files and launch

- `index.html`: all 314 acquisitions; original, v1, final automatic, held-out and human comparison views.
- `OPEN_GALLERY.cmd`: open the gallery in the default browser; no server needed.
- `RUN_OR_RESUME.cmd`: activate octa and resume matching stages. Do not start a second copy.
- `protocol.json`: frozen settings, partitions and implementation hashes.
- `models/held_TS*/`: six evaluation networks, histories, calibration trials and checkpoint provenance.
- `models/all_eligible/`: separate inference model; all eligible reviewed animals entered its training.
- `evaluation/`: original animal-held-out predictions and metrics. These remain independent of the final all-label predictions.
- `predictions/` and `records/`: final automatic outputs and per-scan source/model fingerprints.
- `audit_manifest.json`, `exclusions.json`, `data/`: review inventory, exclusions and derived supervision.
- `metrics.json`: target-specific per-animal and aggregate evaluation.
- `FINAL_VERIFIED.json`: completion verification; inspect its status before using the release.

No layer segmentation, octa-seg export, human review decision, or downstream analysis is changed.
