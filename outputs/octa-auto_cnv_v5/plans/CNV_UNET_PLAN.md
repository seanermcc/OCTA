# Plan only: learning CNV segmentation toward full automation

Status: proposed next project. No training, model implementation, dataset export, or deployment is authorized by this GUI change. V5 is the annotation tool needed to make the next experiment measurable.

## Recommendation and objective

Build an image segmentation model for **CNV footprints**, separate from the existing retinal-boundary model. A U-Net is a convolutional image segmentation model, not an LLM. Its encoder/decoder with skip connections is a reasonable baseline for this task; its original biomedical segmentation results do not establish performance on our CNV data. [Original U-Net paper](https://arxiv.org/abs/1505.04597).

Start with a small 2D U-Net baseline, then compare a configured nnU-Net baseline if the dataset warrants it. nnU-Net provides a framework for adapting preprocessing and training to biomedical segmentation datasets; it is a comparator, not an assurance of success here. [nnU-Net paper](https://www.nature.com/articles/s41592-020-01008-z), [official implementation](https://github.com/MIC-DKFZ/nnUNet).

The eventual output is a native-grid probability map, separate connected lesion candidates with uncertainty, and a scan-level decision to accept automation or request review. The practical objective is fewer missed lesions and fewer false proposals **at a measured reduction in manual correction time**. No automatic analysis should be declared optimized based on fewer candidates alone.

## 1. Define and audit reference annotations

Use one reviewed footprint per biological CNV, plus explicit unsure/ignore areas. Keep nearby regions separate when the reviewer judges them separate. Roundness and intervascular location are useful expectations, not rules that override a human reference. Do not force 1–2 lesions, or delete a real fifth lesion merely to satisfy a count prior.

Inventory original CNV labels and v3–v5 region records by numeric animal ID, eye, acquisition, real days post laser, and exact native grid. Connected pieces in legacy masks are not automatically separate biological lesions. Same-day repeated acquisitions must never receive copied masks without checked registration. Preserve original files, source hashes and review history.

Construct future targets conservatively:

| Review evidence | Proposed use |
|---|---|
| Explicitly kept CNV footprint | Positive region; retain manual versus suggestion-assisted origin |
| Whole field explicitly finished | Background outside confirmed CNVs and unsure/ignore areas |
| Entire scan explicitly reviewed with no CNV or uncertainty | Negative scan |
| Saved partial work | Positive reviewed regions only; unmarked field stays unknown |
| Unsure region | Ignore in loss and primary accuracy scoring; report separately |
| Rejected automatic candidate | Useful reviewed false-positive example; reconcile overlaps with positive/uncertain regions before using as negative pixels |
| Untouched automatic suggestion | Never human ground truth |

Finished-scan status cannot substitute for careful review. Audit time, visual coverage and consistency on a subset. Do not interpret a hidden-suggestions launch as proof the annotator has never seen predictions. The v5 exposure flag is limited evidence. Use blinded fresh annotations and independent adjudication for the final evaluation wherever feasible.

First collect a diverse pilot of approximately 20–30 fully reviewed acquisitions across several animals, both eyes, negative/pre-laser examples, lesion stages, scan qualities, vessel artifacts and edge cases. This is a proposed starting annotation budget, not a sufficient sample-size claim. Start by adjudicating the existing D7/D28 components and D14 failures. Estimate actual lesion prevalence and between-animal variability before choosing a powered final test size. Do not build the entire training set around TS267 or the most obvious lesions.

## 2. Freeze leakage-aware partitions before fitting

Group every visit, eye, repeat, crop and augmented image of an animal into the same split. Use animal-level cross-validation for development; reserve different animals for final testing. Numeric animal identity governs grouping because sex letters can disagree between sessions. No repeated scan or neighboring B-scan from a held-out animal may enter training.

The present upstream layer model was fit on the full labeled cohort. A CNV test animal can therefore be held out from CNV training while still exposed to upstream segmentation training. Report this distinction. For an end-to-end independent claim, compute test thickness channels using an upstream model that excluded that animal, or acquire genuinely new animals not seen by either model. Do not advertise current TS267 comparisons as independent validation.

Freeze a reference manifest and image preprocessing revision. Keep model selection, thresholds, normalizations and postprocessing tuning inside training/validation folds. Never choose the best checkpoint using final test labels.

## 3. Begin with image inputs that can support genuine automation

Proposed first comparison:

1. Structural en-face only.
2. Real OCTA projection only.
3. Structural plus OCTA as two aligned image channels.
4. Only after those baselines, add selected thickness maps and explicit missingness masks.

All inputs must share native [B-scan,A-line] coordinates. Preserve physical scale and source identity. Define the OCTA depth slab in advance; v5 currently uses the saved retinal crop, not a lesion-specific or layer-specific slab. Validate the field/crop and projection artifact sensitivity before freezing it for learning. For thicker pathology, compare alternate depth projections within development folds rather than assuming the current aggregate preserves every lesion.

Thickness channels must never hide unavailable pixels as plausible zero thickness: normalize observed values, use a neutral numerical fill only with an explicit validity channel, and keep the measurement itself missing. Keep raw grayscale/OCTA separate from colorized screenshots. Do not train on overlay lines, CNV annotations, patient/scan text, hand-corrected segmentation or manual vessel masks that would be unavailable at autonomous inference. If automatic vessel context is tested, generate it without target manual input and audit its training exposure.

The current octa-seg U-Net predicts depth-boundary positions from B-scans; CNV footprints are an en-face spatial segmentation target. Reuse the project’s infrastructure and provenance conventions, not its eight-boundary output head. Do not promise direct checkpoint transfer. Test a small initialization/transfer experiment later only with leakage controls and a random-initialization comparison.

## 4. Model experiment, without premature complexity

Proposed baseline: a compact 2D U-Net with one CNV logit per pixel. Train with masked binary cross-entropy plus a foreground-overlap term; compute both only where labels are known. Negative scans still need a meaningful false-positive loss when the foreground term is empty. Sample full fields or overlapping tiles with consistent physical scale; balance positive examples and hard negatives without changing validation prevalence.

Use image-preserving flips, rotations and bounded intensity changes, applied identically to all registered channels and masks. Check whether a transformation changes orientation-dependent artifact behavior before adopting it. Use development early stopping, multiple fixed random seeds and documented normalization.

Keep a sigmoid probability map before thresholding. Separate thresholding from region extraction. Use probability and shape as features, not hard rejection criteria that conceal misses. Compare raw predictions against postprocessed predictions. Report extra foci rather than truncating the evaluation at four. If two true lesions merge, consider a later instance-separation head; do not add it until the error audit shows that is the limiting failure.

If en-face inputs consistently miss lesions only visible in depth, plan a second-stage candidate classifier using a local B-scan stack or a 2.5D model. Do not begin with a large 3D model when the reference set and depth-specific targets are still sparse. An LLM is not required to produce the lesion masks.

## 5. Measure detection, borders and review burden separately

Primary comparisons should include lesion sensitivity at prespecified false positives per scan, precision, positive/negative scan classification and scan-level count error. Define one-to-one lesion matching before evaluation; use a meaningful overlap criterion as primary, with distance tolerance as a separately reported sensitivity analysis. The old 75 µm location hit rate alone is not enough.

Measure Dice/IoU and physical boundary error on appropriately reviewed borders. Report missed small/clipped lesions, vessel-related false positives, merged/split lesions, uncertainty, low-signal scans and performance by animal, eye and time after laser. Use animal-clustered uncertainty estimates rather than treating hundreds of pixels as independent samples. Explicitly handle empty masks and negative scans in every metric.

Also measure active correction time and number of added, erased, removed and accepted regions on a randomized/blinded review subset. Compare the unchanged v3 heuristic suggestions, image-only U-Net, multimodal U-Net and any subsequent model. A new model should improve sensitivity/false-positive tradeoffs and manual effort, not simply produce smoother-looking circles.

## 6. Active review and a controlled route to automation

After the first trained model, select a mixed review queue: uncertain examples, model disagreements, suspected false positives, possible misses, and a fixed random sample. Retain negative scans. Never sample only confident lesions or only problematic scans. Keep the final test set out of this feedback loop.

Freeze each model release and its data manifest. Show candidate probabilities and version provenance in a future reviewer update; never silently replace saved human edits. Require quantitative acceptance targets agreed before test evaluation—for example a specified sensitivity at an acceptable false-positive rate, acceptable count/area bias and bounded correction burden. The numbers must be chosen from project needs and baseline measurements, not invented after seeing results.

Run a prospective silent evaluation on new acquisitions before replacing review with automation. Route scans with out-of-distribution inputs, insufficient acquisition quality, unstable predictions or unsupported measurements back to a human. Version derived areas and thickness measurements independently of the detector. Maintain a rollback path. Full automation is earned on unseen data; it is not achieved by adopting U-Net alone.

## Proposed implementation order for a future authorized task

1. Audit and adjudicate labels; agree coverage/instance semantics and final-test animals.
2. Implement a read-only dataset exporter with masked supervision and leakage checks.
3. Freeze image/OCTA preprocessing and train the image-only baseline.
4. Compare modality ablations and nnU-Net; evaluate grouped development folds.
5. Run a bounded active-review cycle and measure correction burden.
6. Lock the candidate model and thresholds, perform independent/prospective evaluation, then decide whether it is ready for an automation trial.

Current deliverable: this plan and the v5 CNV reviewer only. None of steps 2–6 has been implemented or run here.
