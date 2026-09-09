# Readability-aware withholding for the Stage A U-Net — 2026-09-08

**Experimental. Not validated, not calibrated, not production-ready.** Evidence
is two development-validation animals with corrected labels (TS169, TS325) plus
five training animals. No final-test animal or repeatability data was touched.
No threshold here is an acceptance criterion. Remaining boundary error inside
readable tissue is a separate segmentation problem and is not addressed.

Contract: eight boundaries (`5-8surf-pr`), N=1 preprocessing
(`native-single-db-p1-p99.5-v1`), as frozen in `20260908_v2`.

---

## 1. Corrected review display

`code/stage_a_review.py` draws every predicted column as a solid line regardless
of the saved `retained` mask, so a reviewer sees a continuous surface through a
vessel shadow the pipeline already refuses to measure. `stage_a_readability.py
display` replaces the default with a **measurement view** and keeps the old
behaviour as a labelled diagnostic.

* **`*__measurement.png` (default).** Each surface line is broken (NaN, never
  zero, never interpolated) wherever `retained[surface, column]` is false. A
  middle panel shows per-A-line exclusion **reasons** as separate tracks —
  classical shadow, boundary crossing, outside-CNV-scope, non-finite,
  entropy/uncertainty (inactive) — from the model's own `reason_bits`, plus two
  hatched *reference* tracks from the frozen targets: human-marked unreadable
  (`region_excluded`) and the CNV footprint+buffer. A bottom panel plots the
  seven retained-thickness bands, which are NaN across every gap.
* **`*__raw_diagnostic.png` (`--raw`).** The old unbroken lines, titled "RAW
  DIAGNOSTIC — NOT the measurement view". Thickness stays the retained (gapped)
  version in both.
* No threshold was added and no measurement changed: `rows`, `retained` and
  `reason_bits` are the arrays `stage_a.evaluate` already wrote.

### Verification — `TS325_OD_2026-01-05_D42_s05_131602_b0128`

| Quantity | Expected (from task) | Found in the frozen arrays |
|---|---|---|
| manual `region_excluded` columns | 83–108, 238–263, 481–511 | 83–108, 238–263, 481–511 |
| saved shadow-exclusion columns | 0–5, 82–109, 209–274, 477–511 | 0–5, 82–109, 209–274, 477–511 |
| model `retained==False` (union over surfaces) | — | 0–5, 82–109, 209–274, 477–511 |

The measurement overlay breaks all eight surfaces across exactly those four
shadow spans; the raw diagnostic shows the predictions diving to the shadow
floor there and collapsing at the right edge. On this B-scan the classical
shadow mask happens to cover every manually-excluded range (the audit shows this
is **not** generally true). Overlays for all 14 validation and 48 training
eligible B-scans are in `review/`.

---

## 2. Audit of the existing mask against human evidence

Train + dev-validation only. Per `(B-scan, surface)` and pooled in
`audit/by_*.csv`; column-level reason overlap in
`audit/reason_overlap_per_bscan.csv`; headline in `audit/audit_summary.json`.

Evidence is used at its granularity: **negative** = manual `region_excluded`
columns; **positive** = a boundary a human drew, saw and did not flag unreliable
or displaced (the classical-shadow bit is tolerated so "withheld despite
support" is measurable); everything else (unreviewed, unedited, not-visible,
displaced, unreliable, out-of-scope, rejected-verdict) is **unknown** and counts
as neither. Classical shadow / `stored_auto` scope masks are comparators, not
truth.

### Headline (pooled, train + dev-validation, per surface-column)

| Question | Result |
|---|---|
| Explicitly-unreadable tissue still measured | **17,590 / 77,784 surface-columns = 22.6 %** (train 24.0 %, val 17.9 %) |
| Supported readable tissue withheld | 18,870 / 141,015 = 13.4 %; **79 % of it (14,986 cols) is withheld by the classical shadow mask alone** |
| Retained-tissue boundary error (human-supported ∩ retained) | median 2.8 µm; mean signed −3.3 µm; **worst-B-scan p95 428 µm**; longest contiguous >25 µm run 91 columns |
| Rejected B-scans (human threw the whole image out) | existing mask still emits a mean of **198 / 512 columns per surface** |

### Where the leakage is

* **By surface:** ILM 31.7 %, RPE 30.9 %, PR_RPE 23.2 %, RNFL_GCL 23.5 % — the
  outer anchors and the RPE-adjacent boundaries are the ones that keep getting
  placed (and measured) inside unreadable tissue. Inner boundaries 16–18 %.
* **By QC group:** medium 30.1 %, low 19.9 %, high 20.0 %.
* **By animal:** TS250 42.8 % (medium QC, 4 B-scans, mostly manual exclusion),
  TS241 36.2 %, TS325 18.8 %, TS267 18.0 %, TS305 4.6 %.
* **By biology:** post-laser-nominal 23.2 %, WT 15.2 %.

### Reason overlap (column-level, the five reasons kept separate)

| | manual unreadable | classical shadow | CNV scope-out | boundary crossing | uncertainty |
|---|---:|---:|---:|---:|---:|
| count (col-instances) | 9,723 | 13,090 | 10,086 | 29,044 | 0 |
| ∩ manual unreadable | — | 5,383 | 1,372 | 7,447 | 0 |

* Only **55 %** of manually-unreadable columns are covered by the classical
  shadow mask. **1,104 (11 %)** are covered by *none* of shadow, scope or
  crossing — the model measures straight through them.
* 7,447 manually-unreadable columns carry a crossing flag, but crossing only
  withholds the two crossing surfaces, so the other six are still measured —
  this is most of the 22.6 % leakage.
* The entropy/uncertainty reason contributes nothing because no threshold is
  applied at inference.

**Caveat that bounds all of the above:** absence of a manual exclusion is not
proof of readability. The existing entropy/error study (`RUN_REPORT.md` §6) was
run on *eligible* boundary targets and says nothing about detection performance
*inside* manually-excluded regions; §3 below measures that directly.

---

## 3. A focused readability component

`features/columns.npz` holds, for every A-line of the 110 train + dev-validation
B-scans that have a prediction (56,320 columns): 12 local
signal/contrast/continuity features (band CNR, low-signal fraction, gradient
p90, robust column-energy z, adjacent-A-line correlation, vitreous noise, …),
4 entropy summaries across the 8 surfaces, the existing retained mask, the
per-surface abs error, and the readability labels. Supervision available:
**7,586 manually-unreadable columns** (negative) and ~19 k fully-supported
columns (positive) in train; the rest unknown. This is a small, two-validation-
animal problem and the comparison is exploratory.

Three per-A-line rejection methods, each layered **on top of** the existing
per-boundary mask (crossing/missing/scope kept):

| | Method |
|---|---|
| **A · existing** | reason-coded `retained` mask only, no readability layer |
| **B · simple** | standardised `entropy_mean + entropy_max − cnr + band_lowsig_frac`, one threshold |
| **C · learned** | L2 logistic regression on all 16 features, class-balanced, trained on 7,586+ labelled **train** columns |

Thresholds for B and C are chosen on **train** readable-column coverage and
applied unchanged to validation (`compare/coverage_error_curves.csv`,
`matched_coverage.json`, `coverage_error.png`).

### Matched supported-tissue coverage (validation, TS169 + TS325)

| readable-col coverage | method | leakage into manual-unreadable | retained p95 (µm) | retained gross frac | worst contiguous gross run |
|---:|---|---:|---:|---:|---:|
| 1.00 | existing | 0.179 | 21.0 | 0.043 | 91 |
| ~0.985 | **simple** | **0.058** | **11.7** | **0.017** | **45** |
| ~0.985 | learned | 0.110 | 20.3 | 0.041 | 91 |
| ~0.95 | **simple** | **0.042** | **10.9** | **0.014** | **41** |
| ~0.95 | learned | 0.065 | 18.9 | 0.039 | 91 |
| ~0.90 | simple | 0.025 | 9.7 | 0.010 | 30 |
| ~0.90 | learned | 0.039 | 18.6 | 0.038 | 91 |

**The simple entropy+signal rule dominates the learned model at every matched
coverage.** The learned logistic regression is, in effect, a noisier entropy
detector (its largest weight by far is `entropy_mean`, +1.9) diluted across 15
other features fitted to ~7.6 k labels from mostly one animal; it never breaks
the 91-column catastrophic run above 0.80 coverage, whereas the entropy score
breaks it by 0.95 coverage because that B-scan's entropy is pinned near 1.0.

### It withholds where quality is poor and preserves good tissue

At the `simple` q0.96 train threshold, on validation:

| animal | QC | coverage existing → simple | leakage existing → simple | p95 µm existing → simple |
|---|---|---|---|---|
| TS169 | high | 0.976 → 0.973 | 0.150 → 0.074 | 11.8 → 11.4 |
| TS325 | low/med | 0.927 → 0.851 | 0.188 → 0.053 | 23.8 → 11.8 |

High-QC tissue is essentially untouched; the rejection concentrates on the
low/medium-QC animal, which is the intended behaviour.

### Whole-B-scan rejection (separate question)

Per-B-scan mean score vs. the human `rejected` verdict, AUROC
(`compare/whole_bscan_rejection.csv`):

| score | train (18 rej / 72) | validation (24 rej / 38) |
|---|---:|---:|
| `entropy_max` mean | **0.93** | **0.93** |
| simple entropy+signal | 0.87 | 0.88 |
| learned logreg | 0.72 | 0.86 |
| CNR deficit only | 0.64 | 0.59 |

Mean entropy alone separates human-rejected B-scans well; local contrast alone
does not. A whole-B-scan gate is a plausible cheap addition but needs more than
two validation animals to set a point.

### How a gate would be chosen

A gate has two independent parts — the score and the threshold — and neither is
fitted to the validation animals.

**Score.** Fixed from the data, not tuned: `Z[entropy_mean] + Z[entropy_max] −
Z[cnr] + Z[band_lowsig_frac]`, where `Z` is standardisation (subtract mean,
divide by SD) using statistics from the **training** animals only. It fires
where the decoder has no confident boundary depth *and* the column is
low-contrast / low-signal. The comparison above is the evidence for this
particular combination: adding the 12 remaining features via logistic
regression (method C) does not improve on it, and `entropy_mean` alone carries
most of the weight the learned model assigns.

**Threshold — chosen as a coverage-loss budget on training readable columns,
then transferred unchanged.**

1. Take every column a human confirmed readable on all eight surfaces, in the
   five training animals.
2. Decide how much of that readable tissue is acceptable to lose — a budget,
   e.g. 4 %.
3. Set the threshold to the corresponding quantile of the score over those
   training readable columns (4 % → `train q0.96`).
4. Apply that threshold number verbatim to TS169 / TS325 and confirm that
   leakage and retained error fall while readable coverage holds
   (`compare/coverage_error_curves.csv`).

The budget is the only knob, and it is set on training data. Picking the
operating point to minimise error on TS169 / TS325 is rejected: with two
corrected animals the same data cannot both expose the failure and calibrate
the fix, and the negative evidence (`region_excluded` columns) is too sparse to
locate an ROC operating point at per-column granularity.

**Where the budget lands.** From `matched_coverage.json`, tightening the gate
keeps cutting leakage monotonically, but below about `train q0.94` it starts
removing genuinely readable tissue on the low-QC animal (TS325 readable
coverage falls toward 0.85 while high-QC TS169 stays above 0.97). The knee is
`q0.94`–`q0.96`: leakage 4× lower, retained p95 halved, worst gross run
91 → ~41 columns, < 0.3 % of TS169 readable columns touched. That is the
operating point the recommendation refers to — as an experiment, not a fixed
criterion.

**Whole-B-scan gate.** Same procedure one level up: per-B-scan mean of
`entropy_max`, thresholded to reproduce the human `rejected` verdicts on the
training B-scans (AUROC 0.93), applied to validation. It is a second,
independent knob and would be set after the per-A-line gate.

---

## 4. Representative cases (`review/`)

* **Success — `TS325…b0128` (low QC).** Two vessel shadows and a dark right
  edge; the measurement view cleanly breaks all surfaces there, the retained
  RNFL/GCL/IPL bands are within a few µm of the human dotted targets across the
  readable centre.
* **Partial — `TS325…D98…b0061` (medium QC).** ILM sits ~70 px too deep across a
  stripe-shadowed band the classical mask only partly covers; entropy is
  elevated there, so the simple rule removes most of it, but a ~40-column run
  survives — residual segmentation error, not a withholding failure.
* **Failure the mask does not fix — `TS325…6mo…b0510` (low QC).** The retina is
  barely above noise. Crossing detection withholds the scrambled right two
  thirds, but a ~90-column stretch near cols 120–210 is measured with surfaces
  100–300 px from the human targets. This single B-scan drives the validation
  tails. The entropy score rejects it (entropy pinned at 1.0); the learned model
  does not.
* **Over-rejection check.** On high-QC TS169 the simple rule drops <0.3 % of
  readable columns, so "hide more columns" is not how it gets its numbers.

---

## 5. Recommendation

**Readability modelling does not merit further training on this evidence.**

* The signal that matters — decoder **entropy** — is already produced at
  inference for free. A learned readability output (logistic regression on 16
  features) did **not** beat a one-line standardised entropy+contrast rule at
  any matched coverage, and did not touch the catastrophic B-scan. A U-Net
  readability head would be a larger architecture change, would re-open the
  "reject hard supervised examples to lower loss" failure mode, and is not
  justified by a two-validation-animal comparison.
* **What is worth adopting** (as an experiment, not a validated measurement):
  a per-A-line entropy gate layered on the existing reason-coded mask, plus a
  whole-B-scan entropy gate. At ~0.95 supported coverage on the two validation
  animals it cut leakage into manually-unreadable tissue 4×, halved retained
  p95 error, and shortened the worst contiguous gross run from 91 to 41
  columns — concentrated on the low-QC animal.
* **Blocking before any threshold is fixed:** only TS169 and TS325 carry
  corrected validation evidence, so the same animals cannot both expose the
  problem and calibrate the gate. The `RUN_REPORT.md` §8 next step (train the
  same config longer) still comes first — it may move ILM and the catastrophic-
  B-scan rate, which changes what a readability gate has to do. After that, and
  after more corrected animals exist, calibrate the entropy gate on held-out
  animals and re-run `compare`.
* **Cheap fixes independent of all the above:** (a) when a crossing is detected,
  consider withholding the whole A-line rather than only the two crossing
  surfaces — 7,447 manually-unreadable columns are only partially protected
  today; (b) the classical shadow mask misses 45 % of manually-unreadable
  columns, so shadow detection itself has headroom.

## 6. Next step

In order. Each step is gated by the one before it and none of it starts without
sign-off.

1. **Train the frozen `20260908_v2` config longer** (the `20260908_v2`
   `RUN_REPORT.md` §8 step, unchanged by this work). Stage A is undertrained at
   40 epochs; the ILM regression and the single catastrophic B-scan
   (`TS325…6mo…b0510`) that drives the validation tails may both move. Until
   that is known, a readability gate is being tuned against a moving target.
   This is a training-length change only — same architecture, same data, same
   contract — so it does not re-open the code-identity / resume questions the
   way a readability head would.

2. **Re-run this experiment against the longer-trained checkpoint.** Regenerate
   `eval_train` / `eval_validation`, then `features` and `compare`. The
   question is whether decoder entropy still carries the readability signal
   once the model is better fit, and whether the worst-run and leakage numbers
   the gate has to fix are still the same size.

3. **Get corrected labels on more validation animals.** TS336 is rejected-only
   and TS169 / TS325 cannot both diagnose and calibrate. At least one more
   corrected dev-validation animal is needed before any threshold is fixed;
   ideally the calibration animal is disjoint from the animals used to choose
   the score.

4. **Then, and only then, calibrate the gate.** Set the per-A-line coverage
   budget and the whole-B-scan entropy threshold on the training animals,
   lock them, and report leakage / retained error / coverage on the held-out
   corrected animals — once, without adjustment. If entropy still dominates,
   ship it as `stage_a.inference`'s existing `entropy_threshold` hook (already
   present, currently `None`) plus a whole-B-scan check, not as a new model.

5. **In parallel and independent of 1–4:** implement the two cheap fixes above
   (whole-A-line withholding on a crossing; better shadow detection). These do
   not depend on training length or on more labels and address a known 22.6 %
   leakage directly.

A U-Net readability head is explicitly **not** on this path. It would only be
reconsidered if step 2 shows entropy stops predicting readability after longer
training *and* the local features gain real signal — neither of which the
current evidence suggests.

## 7. Scope compliance

* No final-test animal read, evaluated, inspected or unlocked; no
  `--final-test-protocol` created. Repeatability tree not read.
* No human label, manifest, partition, footprint or checkpoint written or
  modified. `stage_a_report.py`: `scientific_versions_unchanged: true`,
  `repeatability_data_read: false`, 160/32/28 unchanged before and after.
* All new code is `code/stage_a_readability.py`, outside `code/stage_a/`, so
  `code_identity` is unchanged and every existing checkpoint stays resumable;
  `python -m stage_a.test_stage_a` → 16/16.
* The resume-overwrite bug was not triggered (no U-Net training/resume).
* No architecture sweep, no long training campaign, no CNV specialist, no
  production-readiness claim.
