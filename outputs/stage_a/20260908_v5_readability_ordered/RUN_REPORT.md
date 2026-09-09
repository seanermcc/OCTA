# Stage A: whole-column readability and ordered decoding — 2026-09-08

**Completed development experiment; not a promotion candidate.** The combined method reduces manual-exclusion leakage and breaks measurements into intervals, but loses useful labelled tissue and retains catastrophic, anatomically ordered mistakes. It does not outperform the existing entropy-plus-signal rule consistently. No production threshold was enabled.

Following the user's clarification, **only frozen manual segmentations are boundary/thickness ground truth**. Published layer thicknesses and classical surfaces are not truth or fitting targets. Existing scope and classical-shadow masks remain withholding protections only.

## Result at the prespecified exploratory operating point

The same 38 validation decisions were evaluated; 14 have eligible manual boundary evidence, from **TS169 and TS325 only**. TS336 is rejected-only and contributes no boundary accuracy evidence. All errors are in micrometres; gross means absolute error >25 um, the existing provisional reporting cutoff. Runs are consecutive A-lines within one B-scan and one boundary.

| Method | Supported measured / 34,809 | Coverage | Leakage / 17,096 | Leakage | Boundary median / p95 (um) | Gross / measured | Worst run |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Epoch 124 existing | 33090 | 95.06% | 3159 | 18.48% | 2.10 / 9.41 | 658 / 33090 | 44 |
| Readability alone | 28655 | 82.32% | 1193 | 6.98% | 2.06 / 9.37 | 594 / 28655 | 44 |
| Ordered alone | 30280 | 86.99% | 1272 | 7.44% | 2.13 / 7.92 | 192 / 30280 | 29 |
| Readability + ordered | 26121 | 75.04% | 616 | 3.60% | 2.08 / 7.84 | 153 / 26121 | 13 |
| Entropy + signal | 26099 | 74.98% | 646 | 3.78% | 1.93 / 7.39 | 79 / 26099 | 19 |
| Entropy + signal + ordered | 25503 | 73.27% | 504 | 2.95% | 2.05 / 7.50 | 42 / 25503 | 27 |


Readability + ordered and entropy + signal have an unusually close **supported-coverage match: 75.04% versus 74.98%**, a 0.063 percentage-point difference (22 surface-columns). The combined method has slightly less leakage and a shorter worst run (13 versus 19), but larger p95 error and **153 versus 79 retained gross errors**. This is a mixed tradeoff, not superiority.

The combined method drops 7,266 previously retained supported positions and adds 297, for a net loss of 6,969. Its error-or-withheld fraction rises from 6.83% to 25.40%. A lower conditional p95 therefore cannot be called a general segmentation improvement.

Thickness results are also mixed: combined TOTAL median/p95 is 2.24/5.61 um versus 2.16/6.39 for existing withholding; GCL median worsens 2.46 → 2.59 um and RPE-band p95 worsens 9.82 → 11.20 um. **TOTAL and the RPE band have no eligible endpoint pair in b0510**, so their zero gross-error counts do not clear that catastrophic case. All eight bands remain in the tables with their own denominators.

## Annotation audit and target limitations

| Split | B-scans | Weak positive | Explicit negative | Unknown | Strong local positive |
| --- | --- | --- | --- | --- | --- |
| train | 72 | 4548 | 7586 | 24730 | 0 |
| validation | 38 | 2782 | 2137 | 14537 | 0 |


Every development label is `2-surface-reliability`, with whole-surface edit/visibility/reliability flags. **None records exact local stroke coverage.** The current GUI code supports newer local provenance, but no frozen file has it; neither the GUI nor labels were changed by this experiment.

- Negative: explicit human `region_excluded`, independent of B-scan verdict. These remain distinct from boundary-position supervision.
- Weak positive: all eight existing boundary masks eligible; corrected verdict; all eight surfaces edited, visible, reliable, and not displaced; at least 8 strokes and 30 seconds active review. The qualifying positive files actually have 47–204 seconds of review. Positive loss weight is **0.25**, explicitly acknowledging the coarse evidence.
- Unknown: everything else. Unedited/missing labels, rejected verdict alone, invisible individual surfaces, classical shadows, and outside-scope regions do not become unreadability negatives. An explicit exclusion overrides any positive proxy.

These are **weak review proxies, not certified per-column readable labels**. They do not recover which columns a stroke traversed. The strict local policy has **zero positive examples** in either split. A fully local, human-readability-supervised experiment cannot be supported by this snapshot; this run tests the strongest documented coarse proxy while preserving the original boundary eligibility contract. The positive-review duration is a filter, not proof of attention at each A-line. Uncertainty about the positive labels remains a central limitation.

## Model and fixed budget

All encoder, bridge, decoder, boundary-head and region-head parameters come from **epoch 124**, unchanged and frozen. Raw rows, entropy and old reason masks reproduce exactly on **110/110** development B-scans. There is no boundary retraining confound.

The new 64,641-parameter head uses the frozen decoder's 8 feature channels pooled into 16 depth bins, plus the normalized image in 32 depth bins (160 channels total). Three lateral convolutions span 57 A-lines. This retains depth-specific contrast/attenuation patterns and neighboring image structure; there is no darkness-only rejection rule or vessel/ONH classifier. The simple comparator retains the prior standardized entropy-mean + entropy-max − CNR + low-signal-fraction rule; its normalization uses training data only. Additional classical continuity metrics are not readability labels and were not used as truth.

`PRESPECIFIED_PLAN.json` was saved and fingerprinted before training: seed 20260909; **40 epochs × 48 steps = 1,920 updates**, AdamW lr 0.0003, decay 0.0001, gradient clip 5, animal-balanced sampling, horizontal flips of cached features/targets. Loss is class-macro BCE on known columns, explicit negatives weight 1, weak positives 0.25; unknown loss is zero. Readability loss weight 1; boundary and region update weights zero.

Selection: minimum animal-macro validation readability loss, earliest exact tie; no extension or parameter search. **Epoch 10** was selected, loss 0.204520. Training the cached-feature head took **35.19 seconds**; all 1,920 losses/gradients were finite and nonzero, and checkpoint round-trip was exact. Later validation losses worsen. Proxy AUROC is 0.902 training / 0.709 validation; neither score nor loss establishes calibrated readability.

The displayed gate is the **training 95% positive-proxy coverage quantile**, not a validation-chosen operating point. Its usable-score cutoff is about 0.007386, illustrating that these weighted-loss sigmoid scores are **not calibrated probabilities**. Actual validation gate coverage is 85.91% for the head and 87.46% for the simple rule; final all-eight measurement coverage is lower (81.24% for combined). The fixed grid is 50, 70, 80, 85, 90, 95, 98, 99 and 100% training proxy coverage. It is not an optimization search.

## Ordered decoding and its limitations

Canonical order is ILM → RNFL_GCL → GCL_IPL → IPL_INL → INL_OPL → OPL_ONL → PR_RPE → RPE. Exact column-wise dynamic programming requires a one-native-pixel geometric gap. It never fits normal layer thicknesses.

Posterior candidates must lie within log(20) of their own peak. A column is withheld if any boundary exceeds its **training eligible-target p99.5 entropy** or lacks finite support, or if eight supported ordered rows are infeasible. Entropy caps range 0.419–0.840; full values and counts are in `continuity_measurements_train.csv`.

One forward and one backward coordinate-descent sweep add a continuity penalty of `0.15 × min(|depth difference| / scale, 4)` per neighbor. Scales are the training manual adjacent-column slope p99, floored at 2 px: 2.386 px for ILM, 2 px for the others. These are conservative soft penalties, **not hard slope limits**, and the legacy manual curves themselves contain software-smoothed/untouched sections. Scope, shadow, readability, unsupported and infeasible gaps split the problem; no neighbor crosses a rejected gap and no gap is interpolated. This is not a global two-dimensional optimum.

Ordering is demonstrable, image support is not guaranteed: model posterior concentration can still be confidently wrong. The bounded penalty permits extremely large jumps, as b0510 demonstrates. It was not tightened after seeing validation failures.

Raw predictions contain 48,230 crossing-flagged boundary-columns / 155,648 (30.99%). Existing withholding already yields zero measured adjacent crossings; ordered measurements also have zero. On the 46,648 boundary-columns retained by ordered-only, 1,239 raw positions were crossing-flagged before decoding and zero afterward. **341 manually supported positions are recovered from old crossing withholding, but 100/341 are grossly wrong.** Zero crossing is not a quality certificate.

## Separating relocation from rejection

`decoder_support_raw` applies ordered-only support to the old raw rows while retaining the old crossing protection. Its p95 is 7.80 um and worst run 19; ordered-only gives 7.92 um and 29. Exact shared-column comparisons remove the remaining selection difference:

| Exact common columns | n | Median A / B (um) | p95 A / B (um) | MAE A / B (um) | Gross A / B |
| --- | --- | --- | --- | --- | --- |
| Epoch 124 existing → Ordered alone | 29939 | 1.99 / 2.11 | 7.80 / 7.84 | 3.26 / 3.47 | 136 / 92 |
| Epoch 124 existing → Readability + ordered | 25824 | 1.95 / 2.06 | 7.70 / 7.79 | 3.26 / 3.51 | 96 / 53 |
| Entropy + signal → Readability + ordered | 21577 | 1.85 / 1.96 | 7.08 / 7.44 | 2.49 / 2.57 | 7 / 8 |
| Readability alone → Readability + ordered | 25824 | 1.95 / 2.06 | 7.70 / 7.79 | 3.26 / 3.51 | 96 / 53 |


Outside the learned rejection mask, combined decoding changes **3,520** common supported positions by more than 1 px. Of 25,824 common positions, 1,619 improve and 2,228 worsen by >1 um. These are decoder changes, not head retraining; mean absolute error increases despite fewer gross errors. The full paired thickness results are also reported. No boundary-location error is scored inside explicit human exclusions because no eligible manual truth exists there.

At approximately 95% **readable-gate** coverage, the fixed-grid comparison is:

| Method | Training quantile | Actual readable gate coverage | Supported coverage | Leakage | p95 (um) | Worst run |
| --- | --- | --- | --- | --- | --- | --- |
| learned | 0.99 | 95.22% | 91.05% | 8.77% | 9.28 | 44 |
| simple | 0.98 | 94.61% | 83.35% | 5.65% | 7.51 | 19 |


These do **not** match supported-surface coverage (91.05% versus 83.35%). `matched_coverage.csv` additionally discloses absolute mismatch for supported coverage and final all-eight coverage; exact shared-column comparisons above are preferable when assessing relocation.

## Reviewed failures and readable controls

- **D98 b0061:** baseline 1,504/1,592 supported positions and 1,467/2,448 unreadable surface-positions measured. Combined retains only **390/1,592 (24.50%)**, with 184/2,448 leakage. Its retained gross count reaches zero by rejecting most useful tissue. Ordered-only actually lengthens the worst gross run from 19 to 29. The far-right unsupported region is greatly reduced, but the left/middle labelled retina is over-withheld.
- **Catastrophic b0510:** readability alone changes none of the baseline retained measurements. Combined retains **568/2,561 (22.18%)** supported positions; 141 remain gross. Its worst retained run shortens from 44 to 13, but p95 rises **421.63 → 525.28 um**. The overlay visibly contains an ordered stack at the wrong depth and large jumps. This case is not solved. The simple rule withholds the entire case, whose missing accuracy remains unavailable rather than zero error.
- **Readable TS169 b0164:** baseline retains 2,718/2,720 supported positions; combined retains 2,288 (84.12%). The simple rule retains 2,718. Much of the lost tissue still follows visible, manually labelled structure.
- **Readable TS325 D42 b0023:** combined retains 2,552/2,894 (88.18%) versus baseline 2,890; p95 improves 9.71 → 8.65 um. The simple rule has p95 7.91 but only 80.44% support coverage. Both useful retention and omissions are visible in the shared-scale comparison.

All **14 eligible measurement overlays** and **five six-panel comparisons** are in `review/`. They show raw predictions, NaN-gapped measurements, eligible manual targets, explicit exclusions, readable scores, reasons and thickness. Plots use canonical native depth (vitreous at 0); old reports used reversed disk depth. Numerical arrays include the verified inverse disk mapping. All panels within a comparison share image scaling and depth range.

## Is finer per-surface visibility justified?

**A targeted collection study is justified; its benefit is not yet proven.** Whole-column rejection loses **5,230** previously retained positions that were within 5 um of the manual target, including **613 ILM positions**. For 278 of those ILM positions, the ILM passes its own entropy cap but another boundary fails, causing whole-column rejection. This is measurable lost useful coverage that per-surface decisions could potentially preserve.

That evidence does not establish that ILM should be retained inside an explicit whole-image exclusion: frozen eligibility deliberately has zero human boundary targets there. Location supervision, local visibility, and whole-image unreadability must remain separate. Earlier step 2—per-surface × per-A-line visibility—is a possible follow-up annotation collection, **not implemented here**. Existing format capability does not fill the legacy annotation gap.

## Validation, integrity and reproducibility

See `REPORT_TABLES.md` for all eight boundary and thickness results, denominators, animal/quality strata, matched coverage and exact paired comparisons. Error statistics are conditional on retained finite ordered measurements; missing/withheld counts and fractions remain explicit. `qc_group` is the frozen review grouping, not a newly calibrated acquisition-quality label; high-quality validation evidence is confounded with TS169.

Only the same two corrected validation animals select the head and support its reported performance. There is no independent calibration set, no held-out WT validation animal, no final-test/repeatability evaluation, no new human labels, and no production promotion. All old checkpoints, frozen definitions and labels are preserved. Access was restricted by the dated guard; content fingerprints cover allowed development files only, not locked animal contents.

The final code lives in the separate `code/stage_a_readability_ordered/` package, preserving the original trainer's code identity and resume behavior. Packaging changed import paths after evaluation, not model/decoder computation; final tests and checkpoint reproduction verify this. Figure rendering was isolated from PyTorch after an OpenMP DLL conflict; no unsafe duplicate-runtime override, installation or library upgrade was used.

Final verification: **11 new tests + 16 original tests pass**. All 110 packaged-model boundary predictions reproduce exactly; full-image versus cached-head scores differ by zero; D98 b0061 and b0510 decoder outputs reproduce exactly. All 266 measurement files preserve experimental status and NaN gaps. **334 allowed development fingerprints** verify; **2,689 old artifacts** retain size and modification time, with no added old-root artifacts. Locked file contents were not hashed. Details: `final_software_verification.json` and `integrity_complete.json`.

The recorded `reproduce.ps1` gives the command sequence. Prepare/train/evaluate refuse completed destinations. Plan, training histories, both head checkpoints, original checkpoint fingerprint, fixed-grid measurements, raw validation logits, reason arrays, paired comparisons and integrity/test results remain under this dated root. Human-label writers were never called. **Decision: retain this as a failed development candidate and collect stronger local evidence before threshold calibration or further claims.**
