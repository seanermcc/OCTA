# Major-vessel segmentation pilot — 2026-09-09

A no-training contrast-and-shape method produced proposals for six scans. It is a useful starting mask, but does not yet replace human review. Only clearly visible major vessels are the target; capillaries and faint branches are outside this pilot.

![Six proposals](overview.png)

## Saved human work

Both new masks were found in `outputs/cnv_labels`: TS165 OD WT s06, saved 10:12, and TS165 OS WT s02, saved 10:18. They are two eyes of one animal from one session. No human annotation was written or edited; saved hashes were checked after the run. Four additional scans from TS247, TS267, TS305 and TS325 have no reviewed vessel masks, so their accuracy cannot be scored.

## Measurements

Dice measures area overlap (1 = identical). These are development comparisons against freehand brush masks, not independent accuracy estimates. Both labeled images informed the preprocessing and threshold choice. Differences include vessel location, width, missing branches, and extra detections; a single Dice number does not separate them. The brush masks were not altered to agree with the algorithm.

| Scan | Dice | Precision | Recall | ONH handling |
|---|---:|---:|---:|---|
| TS165_OD_2025-04-29_WT_s06_114517 | 0.724 | 0.728 | 0.719 | none |
| TS165_OS_2025-04-29_WT_s02_121711 | 0.730 | 0.684 | 0.782 | human area mask |

The OS comparison excludes the existing human ONH area, including 186 pixels where vessel and ONH brush masks overlap. This is not automatic ONH detection. Without that human ONH exclusion, full-grid Dice is 0.724 (OD) and 0.710 (OS). The outer ten pixels are unassessed because of image-frame artifacts; labeled vessel pixels there still count as misses in the reported Dice/recall.

The final shared threshold is 0.18, selected by mean Dice on the two masks over 0.08–0.40 in steps of 0.02. Threshold transfer between eyes gives 0.730 at threshold 0.18, 0.724 at threshold 0.18. This remains a same-animal development diagnostic; it is not a held-out test.

## What the images show

Large vessel trunks are recovered in several different appearances. Remaining errors include missed lower-contrast stretches, incorrect widths, extra small branches, and false positives at acquisition seams, lesion margins and the optic disc. TS267 D56 is a deliberately difficult example with motion streaks and lesion disruption; its proposal needs substantial correction. Inspect all six, including the failures.

## Method and provenance

The input is the original processed-volume structural projection, not a screenshot: mean 20*log10(amplitude) over the same stored retinal band used by the GUI. No retinal surfaces define the projection. The depth average is invariant to depth reversal; no stored orientation flag is used and the native [B-scan, A-line] grid is retained. Source MATLAB files are opened read-only.

Processing: remove abrupt intensity jumps shared by more than 85% of a row/column when the median jump exceeds 0.05 dB and the net-to-total derivative ratio over 49 pixels exceeds 0.75 (to retain the opposing edges of straight vessels); reflect the interior across a 10-pixel frame; smooth at 1.2 pixels; subtract from a 24-pixel background; combine local darkness with a scale-normalized Hessian ridge response at sigma 2.5, 4, 6, 8 and 11 pixels (eigenvalue-ratio weight beta 0.5). Normalize each response by its interior 98th percentile, take the geometric mean, threshold, open/close with radius 2, remove components smaller than 150 pixels and fill holes smaller than 40 pixels. Very broad dark structures could still be affected by step correction. The evidence array is a filter response, not a calibrated probability or an acquisition-quality score.

No network, forest, or learned segmentation weights were trained. Threshold selection still uses labels and is therefore calibration. The four additional scans use the same method and threshold. The green mask is reused human ONH annotation; ONH segmentation is not solved by this experiment.

## How much labeling next

The 32 scans belong to the existing general review queue (16 low, 8 medium, 8 high); 32 is not a measured vessel-training requirement. Pause full tracing. A practical next pilot is 4–6 additional reviewed/corrected vessel masks from several other animals, spanning clean, low-contrast, motion-affected and lesion-containing scans. That is 6–8 total, a staged effort budget rather than a promise of sufficiency. Check completion/correction time and missed major branches, alongside overlap. Keep new animals separate while tuning and testing; random patches from the same scan are not independent test examples. Add more only when new scans expose errors or the learning curve still improves.

If these rules need too much correction, the next candidate is a small pixel classifier (random forest using multiscale intensity, edge and ridge features) with vessel/background/artifact examples. It can use sparse annotations. A compact 2D U-Net is a later option if spatial context is still necessary; the current two same-animal masks cannot establish its performance or sample requirement. Structural vessel shadows are the current target, not OCTA capillary flow or CNV vessel density.

Sources: [scikit-image ridge filters](https://scikit-image.org/docs/0.25.x/auto_examples/edges/plot_ridge_filter.html); [ilastik pixel classification](https://www.ilastik.org/documentation/pixelclassification/pixelclassification).

## Review files

- [TS165_OD_2025-04-29_WT_s06_114517](TS165_OD_2025-04-29_WT_s06_114517.png)
- [TS165_OS_2025-04-29_WT_s02_121711](TS165_OS_2025-04-29_WT_s02_121711.png)
- [TS247_OD_2024-10-30_D14_s05_105423](TS247_OD_2024-10-30_D14_s05_105423.png)
- [TS267_OD_2025-04-16_D56_s03_102014](TS267_OD_2025-04-16_D56_s03_102014.png)
- [TS305_OD_2025-08-07_D35_s01_114451](TS305_OD_2025-08-07_D35_s01_114451.png)
- [TS325_OD_2026-03-03_D98_s01_131308](TS325_OD_2026-03-03_D98_s01_131308.png)

`proposals/*_proposal.npz` are automatic proposals with explicit provenance, native-grid masks, unassessed border, raw unassisted mask and human ONH dependency. They are not labels and are not used by the training pipeline. `metrics.json`, `threshold_sweep.csv`, `threshold_transfer.json` and the cached projections preserve the quantitative audit.

Reproduce from the project directory after activating the `octa` environment: `python code/vasculature_baseline.py`. This writes only to the pilot output directory.