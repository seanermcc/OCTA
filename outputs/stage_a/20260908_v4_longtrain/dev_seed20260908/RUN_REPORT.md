# Stage A fixed-configuration longer training — 2026-09-08

**Experimental development result. Not validated, calibrated, or production-ready.**
Only two animals (TS169, TS325) provide corrected validation evidence, across
14 eligible B-scans. No final-test animal data or repeatability data were opened.

**Result:** longer training improves every boundary's pooled median error and
gross-error fraction versus the original 40-epoch experiment. The ILM gross-error
regression against stored auto closes, and the weak RNFL/GCL and GCL/IPL boundaries
improve further. However, the same catastrophic B-scan remains, crossings remain
in every B-scan of the WT volume, and leakage into manually unreadable tissue
does not improve. Thickness results are mixed. This is evidence for using the
new checkpoint in further development, not for accepting its measurements.

The fresh run completed **200 epochs / 9,600 optimizer steps** in **1,523.23 s
(25.4 minutes)**. Selected checkpoint: **epoch 124, step 5,952**, animal-macro
validation loss **3.394391** versus **3.663572** at epoch 38 in the original run
(7.35% lower). The prespecified extension rule was not met; **no 400-epoch run**.

## 1. Pre-flight and corrections to the execution prompt

The user authorized execution and correction of the prompt. Changes clarified:
new checkpoints are allowed while existing checkpoints are preserved; the
original curve showed an overall downward trend rather than a monotonic decrease;
insufficient duration is a hypothesis rather than an established explanation;
crossing rates must be measured without assuming they stay unchanged; and the
200-to-400 decision must follow an explicit rule fixed before training.

The earlier wait-for-reset note was superseded by the user's instruction to
execute now. At pre-flight, 77% of the five-hour usage window remained. No usage
reset credit was redeemed. Training ran to completion; evaluation/reporting
continued after the user's subsequent instruction to continue the run.

| Check | Result |
| --- | --- |
| Environment | Activated `octa`; scientific imports passed; no package installation or upgrade |
| Package consistency | `pip check`: no broken requirements |
| Tests | 16/16 before the fix, after the fix, and at completion |
| Frozen census | 160 labels / 32 packs / 28 footprints; before/after summaries identical |
| Dataset | `1ab0f7b348d06b5d7448a62f70b77bf84d653113577e02b68c1c16f04ef11786` |
| Partition | `0ef449a19f3941aea617128ad38a624cb3da479a6e2bd193772ab6a60c3de8d1` |
| Supervision/preprocessing | Same frozen eight-boundary `5-8surf-pr` contract; N=1 `native-single-db-p1-p99.5-v1` |
| Scientific versions | `scientific_versions_unchanged: true` before and after |

**Integrity-check adaptation:** the existing report script fingerprints all
splits and writes into frozen v2; the tests also write there. The recorded
`../run_task.py` adapter redirects check reports and temporary files into this
new run root. For the report, it performs **435 allowed-file fingerprint checks**
and skips **204 locked-file verification operations**. Full-cohort counts come
from the frozen manifest metadata; this is explicitly **not** a claim that locked
animal file contents were verified. A file-access guard blocks locked animal
and repeatability paths and blocks writes into the old v2/v3 roots. Neither
the report nor the test source was changed.

## 2. Training, convergence, and budget decision

Fresh initialization, seed 20260908. Architecture, base width 8, learning rate
0.0003, region weight 0.1, 48 steps/epoch, animal-balanced sampling, horizontal
flips, optimizer settings, masks, and data identities match the baseline.
Only the epoch budget changes the learning experiment. The history-write fix
described below has no effect on optimizer updates.

All 9,600 losses were finite and all gradient norms finite and non-zero
(range 0.8189–392.5057, clipped at 5). Peak allocated CUDA memory was
617,725,440 bytes (589 MiB). No OOM, zero-gradient, or non-finite failure occurred.
The expected PyTorch warning about non-deterministic CUDA region cross-entropy
was logged. Checkpoint prediction round-trip was exact.

The first 40 epochs use the identical sample sequence as the original run.
Maximum per-step loss difference was **4.77e-7**, and maximum epoch-validation
loss difference **4.33e-8**. This closely reproduces the baseline before the
additional training, while disclosing the small floating-point difference.

| Epoch | Mean sampled training loss | Animal-macro validation loss | Validation minus training |
| --- | --- | --- | --- |
| 20 | 5.1321 | 5.2549 | 0.1229 |
| 40 | 3.1832 | 3.7516 | 0.5685 |
| 56 | 2.7989 | 3.4351 | 0.6362 |
| 80 | 2.5197 | 3.5962 | 1.0764 |
| 100 | 2.4698 | 3.5853 | 1.1155 |
| **124** | **2.3641** | **3.3944** | **1.0303** |
| 160 | 2.3336 | 3.4899 | 1.1563 |
| 180 | 2.2430 | 3.5840 | 1.3410 |
| 200 | 2.2517 | 3.5581 | 1.3064 |

The curve enters a broad plateau around epochs 50–60, at roughly 3.4–3.6
validation loss, with a later isolated minimum at epoch 124. Training loss
continues falling while the train/validation gap widens. That pattern is
consistent with increasing overfitting and diminishing validation benefit;
there is no statistical claim of an exact convergence epoch.

**Prespecified rule:** extend to 400 only if mean validation loss at epochs
181–200 is at least 1% below epochs 161–180, the best epoch is later than 180,
and the mean validation-minus-training gap increases by no more than 0.5.

Observed: validation window mean **3.53216 → 3.58676** (1.55% worse), best epoch
**124**, gap **1.24605 → 1.33424** (+0.08819). Two conditions fail. Training
therefore stops at 200. All evaluation uses `best.pt`, not epoch-200 `last.pt`.

Full curve and histories: `training_curve.png`, `training_history_epochs.csv`,
`training_history_steps.csv`, and `run_step_009600.json`. The machine-readable
decision is `extension_decision.json`.

## 3. Resume fix and checkpoint provenance

Commit **`5d7ab2c`**, branch **`stage-a-train-longer`**, unmerged. The only change
under `code/stage_a/` is guarding the trailing history write with `if events:`.
Resuming an already-complete run therefore cannot replace its history with an
empty list. The strict data/config/code identity guard remains intact.

Code identity changed deliberately:

- Before: `04752099e5547fdba6691dad00c6ea53be610b3a38a824a3049feffda9e166a3`.
- After: `9f8ad778b778d5ebe04dc5841168b4c4afcf9ac8f1b97f6a92c3a6cd9ee0b78b`.

Existing v2 checkpoints remain loadable for inference, but cannot resume under
the changed code identity. That is compatible with this authorized fresh run.
The original best checkpoint's fingerprint is unchanged.

Two meaningful regression checks passed: a synthetic train → no-op resume →
positive-step extension preserved prior history and wrote the new history; and
a real no-op resume of the delivered 200-epoch run preserved the hashes and
modification times of its checkpoints and training-history JSON. New checkpoint
and history fingerprints are in `completion_verification.json`.

Selected `best.pt` SHA-256:
`855397f3d77fbce2246e619ba9b06efb6339ef56ca0127dce4b14f6a9a3c9cbd`.

## 4. Validation comparison

All 38 validation decisions were evaluated, including ineligible/rejected
decisions for coverage accounting. Both learned checkpoints and stored auto
cover all 14 eligible B-scans and both corrected animals. The regenerated
classical baselines reproduce their original metric summaries and failures
exactly.

**Coverage caveat:** stored classical v2 lacks all predictions for
`TS169_OS_2025-01-14_D35_s04_121533`: four decisions, including all three eligible
TS169 B-scans. Its shared-available comparison covers only TS325, 11 eligible
B-scans. Missing predictions remain failures in complete-cohort denominators.
Do not interpret its zero gross-error entries for absent predictions as success.

Complete-cohort pooled raw boundary results below use **median absolute error
(µm) / gross >25 µm fraction of eligible columns**. The 25 µm cutoff is the
existing provisional reporting cutoff, not an acceptance threshold.

| Boundary | Original 40-epoch run | Longer run | Stored auto |
| --- | --- | --- | --- |
| ILM | 4.34 / 0.1626 | **1.57 / 0.0572** | 0.00 / 0.0714 |
| RNFL_GCL | 4.42 / 0.0915 | **2.59 / 0.0566** | 22.19 / 0.4653 |
| GCL_IPL | 2.86 / 0.0605 | **2.07 / 0.0437** | 26.77 / 0.5277 |
| IPL_INL | 4.65 / 0.1539 | **2.74 / 0.1020** | 2.58 / 0.1712 |
| INL_OPL | 4.09 / 0.0786 | **3.27 / 0.0541** | 3.72 / 0.0500 |
| OPL_ONL | 2.85 / 0.0723 | **2.33 / 0.0572** | 2.70 / 0.0760 |
| PR_RPE | 3.16 / 0.0758 | **2.39 / 0.0600** | 12.79 / 0.0441 |
| RPE | 1.44 / 0.0003 | **1.22 / 0.0000** | 0.62 / 0.1060 |

**ILM:** the gross-error regression closes: 16.26% → 5.72%, versus stored
auto's 7.14%. Its p95 also improves, 144.26 → 33.88 µm, versus 39.42 for
stored auto. Median error remains higher than stored auto's 0.00 µm against
these legacy targets, so this is not uniform superiority on every statistic.

**RNFL_GCL / GCL_IPL:** their improvements hold and strengthen. Both median
and gross error improve over the original learned model; the large advantage
over stored auto remains.

**Thickness is not uniformly improved.** TOTAL median/p95 improve from
3.04/38.22 to 2.16/6.39 µm and gross fraction from 0.0701 to 0.0097.
RNFL, IPL, and INL gross fractions also improve. But GCL gross fraction rises
0.0459 → 0.0493, and PHOTORECEPTOR p95 rises 34.95 → 52.89 µm (gross
0.0618 → 0.0635). The OPL median is essentially unchanged/slightly worse
(3.66 → 3.68 µm); the RPE band's gross fraction rises 0.0042 → 0.0047.
All eight bands remain reported, including these limitations.

Full boundary/thickness tables, signed bias, per-animal results and readability
comparisons are in `REPORT_TABLES.md`. The complete and shared-available,
raw and retained, pooled and animal-macro comparison tables are in
`../comparison_validation/`. QC, biological group, and scope strata remain
separate in those files.

## 5. Persistent localized failure

`TS325_OD_2026-05-26_6mo_s01_112940_b0510` is still the worst B-scan:

| Quantity | Original model | Longer model |
| --- | --- | --- |
| Median absolute error | 98.10 µm | 51.52 µm |
| Longest contiguous gross-error run | 148 columns | 148 columns |
| Mean entropy on eligible targets | 0.549 | 0.431 |
| p95 absolute error | 389.78 µm | 462.43 µm |

The lower median does **not** resolve this failure; its extreme tail worsens,
and uncertainty is lower. Visual inspection of the raw diagnostic and the
measurement overlay confirms large excursions away from the dotted human
targets. Existing reason masks break some lines but leave severely wrong
retained segments. The measurement overlay is
`../review/validation/TS325_OD_2026-05-26_6mo_s01_112940_b0510__measurement.png`.

Other localized failures shrink substantially. The original second-worst
D98 b0061 run decreases from 69 to 19 columns; TS169 b0365 decreases from
45 to 11. The next-largest new runs are 34 columns (TS325 D42 b0073) and
27 columns (TS325 6mo b0448).

As a sensitivity only, excluding b0510 reduces the longer model's ILM gross
fraction from 0.0572 to 0.0085, and IPL_INL from 0.1020 to 0.0406.
The main results always retain this B-scan. See `sensitivity_without_b0510.csv`.
With only 14 eligible B-scans and two animals, this does not establish a
population catastrophic-B-scan rate.

Eight diagnostic overlays and 14 measurement overlays were generated. The
measurement views preserve NaN gaps wherever measurements are withheld and
show exclusion reasons. Diagnostic titles were wrapped during rendering without
changing package code, predictions, masks, or metric definitions.

## 6. Readability and entropy after longer training

The same readability analysis was regenerated from **72 train + 38 validation
decisions**, giving **56,320 A-lines across 110 B-scans**. The logistic pilot
uses only training labels (12,134 known training columns); score normalization
and threshold quantiles use training data. No inference gate was enabled.

On eligible boundary targets, entropy still distinguishes gross errors:
pooled AUROC **0.940 → 0.935**, but Spearman correlation with error magnitude
falls **0.473 → 0.325**. This is an error study on eligible targets, not itself
a readability test inside manually excluded regions.

The direct manual-unreadability comparison shows a separate limitation:

| Validation, existing reason mask only | Original model | Longer model |
| --- | --- | --- |
| Unreadable surface-column leakage | 17.87% | 18.48% |
| Supported-surface coverage | 93.79% | 95.06% |
| Retained median error | 3.09 µm | 2.10 µm |
| Retained p95 error | 20.99 µm | 9.41 µm |
| Worst retained contiguous gross run | 91 columns | 44 columns |

Longer training reduces the retained-error burden, but **does not reduce
leakage into manually unreadable tissue**. The raw 148-column run and retained
44-column run answer different questions and must not be interchanged.

At approximately 95% readable-column coverage for the new checkpoint:

| Method | Actual readable-column coverage | Supported-surface coverage | Unreadable leakage | Retained p95 | Worst retained run |
| --- | --- | --- | --- | --- | --- |
| Simple entropy + signal rule | 94.61% | 83.35% | 5.65% | 7.51 µm | 19 columns |
| Learned logistic pilot | 95.58% | 89.34% | 7.96% | 8.75 µm | 44 columns |

The simple rule retains the better leakage/error/run tradeoff on the supplied
grid, but it also retains fewer supported surface-columns. These are **approximate
readable-column coverage matches**, not exact equal-coverage comparisons across
all supervised surface-columns. At the nominal 98% point, achieved coverage is
96.62% versus 99.75%, so that pair especially cannot establish strict dominance.
The entire fixed grid and actual achieved coverages are reported in
`../compare/matched_coverage.json` and `REPORT_TABLES.md`; no operating point is
selected for use.

At the approximate 95% point, the old simple rule had leakage 4.19%, p95
10.91 µm, and a 41-column retained run. The new rule has better residual
errors/runs but **higher leakage** (5.65%). Old thresholds and the old claim of
a fourfold leakage reduction should not simply be carried forward. For the
new checkpoint this displayed point reduces leakage from 18.48% to 5.65%
(about 3.27-fold).

Entropy remains a major feature family, but **mean entropy alone no longer
has the largest fitted coefficient**. The new standardized regression has
entropy standard deviation 1.9000, maximum 1.8040, mean 1.0331; the original
mean coefficient was 1.9194. Coefficients on correlated features are descriptive,
not proof of causal importance. For whole-B-scan rejected-verdict ranking,
validation AUROC is 0.976 for the learned pilot versus 0.967 for maximum entropy
alone and 0.890 for the simple combined score. Thus no blanket claim that the
simple method dominates the learned method on every task is supported.

The evidence continues to support investigating an entropy-based gate, but
does not justify a new readability head or a calibrated threshold here. More
corrected dev-validation animals are still required, including at least one
additional animal and ideally calibration evidence disjoint from score selection.

## 7. Original-coordinate WT volume verification

Training-split WT scan `TS165_OS_2025-04-29_WT_s02_121711`: **512/512 B-scans**
completed. Original-volume orientation was redetected, vitreous-high on disk.
The maximum disk/canonical round-trip difference is 0.00003052 px.

| Quantity | Original checkpoint | Longer checkpoint |
| --- | --- | --- |
| Boundary-columns flagged for crossing | 443,805 / 2,097,152 (21.16%) | 392,486 / 2,097,152 (18.72%) |
| Median B-scan crossing fraction | 14.94% | 13.51% |
| p90 B-scan crossing fraction | 42.89% | 36.97% |
| Maximum B-scan crossing fraction | 57.64% | 52.05% |
| B-scans with any crossing | 512/512 | 512/512 |
| Retained boundary-columns | 1,411,745 | 1,452,668 |

Crossings decrease but remain widespread; the absence of an ordering constraint
still matters. These fractions count flagged **boundary-columns**, not unique
A-lines or crossing pairs. The classical shadow count remains 372,736, and
outside-scope count remains zero for this WT control.

Checks passed on all chunks: retained exactly equals zero reason bits; withheld
rows are NaN; experimental thickness is finite only with two valid retained,
ordered endpoints; validated thickness is entirely NaN; `validated` remains
false. No entropy threshold was supplied. `volume_verification.json` contains
the counts and geometry checks for both checkpoints.

## 8. Decision informed by this experiment

1. Use epoch 124 as the improved **development checkpoint**. Additional training
   past the observed plateau is not supported by this run; the 400-epoch
   extension was correctly declined by the rule.
2. The ILM gross-error regression is no longer the same broad limitation, but
   residual ILM failures and the catastrophic low-signal B-scan still need
   dedicated attention. The new minimum loss does not establish safe measurements.
3. Investigating ordering/withholding remains justified: crossings persist
   throughout the WT volume and severe retained errors survive the present mask.
   This run did not add either an ordering constraint or whole-A-line rejection.
4. Readability remains a separate development problem. Entropy is still useful,
   but changed uncertainty and leakage behavior require new-checkpoint analysis.
   Calibration is **not ready**: at least one more corrected dev-validation animal
   is still needed. No labels were created or requested as part of this run.

Standing limitations: only two corrected validation animals; the same animals
select the checkpoint and support these exploratory comparisons; one B-scan
dominates important tails; no WT animal outside training; legacy surface-wide
supervision does not certify that every eligible column was individually drawn;
stored classical v2 has incomplete validation coverage and historical overlap.
No result here is a generalization, acceptance, or production-readiness claim.

## 9. Reproducible execution and artifacts

The corrected authorized prompt is preserved at `../EXECUTION_PROMPT.md`.
`../post_training.ps1` records the exact extension decision, evaluations,
four-predictor comparison, diagnostic review, full-volume inference, training
evaluation, readability features/comparison, measurement overlays, and final
checks. It expects a completed fresh 200-epoch training run and new output paths;
it is not intended to overwrite completed evaluations.

Initial training command, after activating `octa` and setting `PYTHONPATH=code`:

```powershell
python outputs/stage_a/20260908_v4_longtrain/run_task.py module stage_a.train --data outputs/stage_a/20260908_v2 --out outputs/stage_a/20260908_v4_longtrain/dev_seed20260908 --epochs 200 --steps-per-epoch 48 --base 8 --lr 0.0003 --region-weight 0.1 --seed 20260908 --device cuda
```

Logs are kept in `../logs/`, rather than streamed as training output. Analysis
helpers reside under the new run root. `code/stage_a_readability.py`, already
untracked at pre-flight, gained an explicit `--out` root and corresponding
feature-input default; its scientific feature/model/metric calculations did not
change. The only package change is the committed history guard. Full numerical
tables are in `REPORT_TABLES.md` and the CSV/JSON artifacts referenced above.

## 10. Scope compliance

- No final-test animal (TS247, TS283, TS328) image, label, target, cache, or source
  data opened, evaluated, inspected, or unlocked; no final-test protocol created.
  Only aggregate frozen manifest/partition metadata was used for identity,
  counts, and animal isolation. Repeatability data were not read.
- No human label, pack, footprint, manifest, partition, or existing checkpoint
  was written or modified. The labelling GUI was not launched. No raw spectral
  reconstruction was attempted; source data were read-only.
- All new experiment artifacts and verification checkpoints are under
  `20260908_v4_longtrain/`. The only authorized old-root edit was the user's
  requested correction to `20260908_v3_readability/NEXT_STEP_PROMPT_train_longer.md`.
  After that correction, **1,869 existing v2/v3 files** retain their sizes and
  modification times; allowed-file fingerprint checks and the original best
  checkpoint's full fingerprint also pass. Locked file contents were not hashed.
- Before/after integrity summaries are identical: census 160/32/28,
  `scientific_versions_unchanged: true`, `repeatability_data_read: false`.
  The scoped verification limitation is recorded in section 1 and in both
  `../checks/*/verification_scope.json` files.
- Animal-level partition isolation and frozen data/preprocessing identities are
  unchanged. No architecture, width, learning-rate, loss-weight, or optimizer
  change; no CNV specialist, new model head, acceptance threshold, or calibrated
  abstention. No further training extension was run.
- All 16 tests pass before, after the fix, and at the end. Synthetic and real
  no-op resume checks pass. Checkpoint reload, original-coordinate geometry,
  withholding masks, and thickness NaN checks pass.
- `code/stage_a/train.py` is the only changed file inside the package. Commit
  `5d7ab2c` explains deliberate old-checkpoint resume invalidation; it remains
  on `stage-a-train-longer`, **not merged**. Unrelated untracked work was left alone.
