# Separate withholding investigation — 2026-09-08

**Completed. No inference change adopted.** The revised investigation and
candidate rules were implemented and run against frozen predictions. Whole-column
crossing rejection is too costly relative to the available uncertainty score.
The narrower four-flag rule has a small exploratory advantage worth retesting
after longer training. None of the five simple signal extensions justifies a
shadow-detector change. This result does not block the separate longer-training
experiment.

## 1. The crossing decision number

On the saved **TS165 training WT volume**, 130,257 of 262,144 A-lines have at
least one crossing: **49.69%**. Of those, 33,475 already have every surface
withheld. Whole-column rejection would newly remove the remaining measurements
from **96,782 A-lines (36.92% of the volume)**, costing 462,321 currently retained
surface-columns. These are availability counts; the full volume has no exhaustive
human readability labels. This is one WT volume, not a rate for every volume.

| Surfaces carrying crossing flags in an A-line | WT A-lines |
|---|---:|
| 1 | 0 |
| 2 | 63,534 |
| 3 | 7,315 |
| 4 | 27,293 |
| 5 | 12,730 |
| 6 | 14,068 |
| 7 | 4,974 |
| 8 | 343 |

The original 443,805 crossing surface-columns reproduce exactly. Distinct
crossing A-lines are 45.24% on the saved training review set and 63.57% on
development-validation. Those sets include rejected scans; they are not random
samples of acquisition quality. By animal, review-set crossing rates range from
27.10% (TS305) to 85.19% (rejected-only TS336). Full splits, QC groups, animals,
and individual B-scans are in `crossing_summary.csv` and `crossing_by_bscan.csv`.

The old **7,447** figure is the overlap of manual unreadability and crossing,
not the count only partially protected. **5,104 were already fully withheld;
2,343 were partially withheld.** No crossing column is currently fully retained:
the existing rule always withholds at least the crossing pair.

## 2. Same predictions, explicit coverage cost

All results below use the same frozen 40-epoch checkpoint predictions. No network
evaluation is required to simulate a mask change: saved rows, entropy, reason
bits and targets suffice. Raw predicted locations and errors never change.

**Coverage denominator:** human-positive surface-columns, including boundaries
that a human supported despite the classical shadow flag. Unknown boundaries
are excluded from this denominator. This is broader than the old comparison's
`valid` denominator, which excludes classical-shadow columns. Both are saved
separately in the CSV. Manual-unreadable leakage is retained surface-columns
divided by all eight surfaces in manually excluded A-lines.

Development-validation, 37,704 human-positive and 17,096 manual-unreadable
surface-columns:

| Experimental policy | Supported retained | Extra supported lost | Unreadable leakage | Retained p95, µm | Worst >25 µm run, A-lines |
|---|---:|---:|---:|---:|---:|
| Existing mask | 86.59% | 0 | 17.87% | 20.99 | 91 |
| Whole column on any crossing | 78.72% | 2,968 | 7.44% | 11.91 | 35 |
| All-pair inversion span | 84.94% | 623 | 13.38% | 16.83 | 91 |
| Whole column at ≥4 flagged surfaces | 84.92% | 630 | 12.88% | 15.53 | 53 |
| Whole column at ≥6 flagged surfaces | 86.35% | 88 | 16.96% | 19.99 | 91 |
| Entropy+signal, train q0.96 | 81.00% | 2,107 | 5.83% | 11.70 | 45 |
| Entropy+signal, train q0.94 | 77.93% | 3,265 | 4.19% | 10.91 | 41 |

The ≥8 variant is a no-op: every surface is already withheld when all eight
carry crossing flags. “≥4” counts distinct flagged surfaces, not four pairwise
crossings. The inversion-span rule checks all ordered surface pairs and withholds
their intervening surfaces where inverted. Existing crossing detection only
checks adjacent pairs, which have no intervening surface.

The original 22.6% leakage headline pools training and validation; it must not
be paired with a validation-only p95 without saying so. The pooled baseline
reproduces **17,590/77,784 = 22.61% leakage** and **18,870/141,015 = 13.38%
supported withholding**. Whole-column rejection pools to 11.35% leakage while
losing another 6,941 supported measurements. Pooled p95 is 14.96 → 11.91 µm;
the worst run is 91 → 44. Full before/after tables use consistent denominators.

### Matched supported coverage

The previous comparison selected the nearest *all-eight-readable A-line*
coverage while labelling the result supported coverage. This investigation
instead matches the **number of human-positive surface-columns retained**.
Ties are kept together; the primary comparisons differ by no more than three
supported surface-columns. Matching validation coverage is descriptive, not
threshold calibration. Operational examples q0.94/q0.96 use training thresholds
transferred unchanged. No threshold is selected for deployment.

At the whole-column rule's validation coverage, its **29,679** supported retained
measurements compare with **29,682** for entropy+signal. Leakage is **7.44% vs
4.40%**, p95 **11.91 vs 11.05 µm**, and worst run **35 vs 43**. Thus whole-column
rejection buys a shorter worst run at the expense of the other outcomes.

The ≥4 rule is closer: at about 84.92% coverage, leakage is **12.88% vs 12.82%**
for matched entropy+signal, p95 **15.53 vs 16.12 µm**, and worst run **53 for both**.
Of its 630 newly lost supported measurements, **541 (85.9%) come from the single
catastrophic TS325 B-scan**. The result is strongly concentrated in one image.

Adding ≥4 to q0.96 entropy+signal loses 76 further supported validation
measurements and removes 37 more unreadable surface-columns. Against simply
tightening the score to the same coverage, the advantage shrinks to **nine fewer
unreadable surface-columns**, p95 **11.55 vs 11.62 µm**, and the **same 45-column
worst run**, with a two-supported-column matching discrepancy. This is a small
exploratory lead, not sufficient evidence to adopt a new rule. Training and
validation tradeoffs also differ; inspect both panels of `coverage_tradeoff.png`.

## 3. What the shadow misses are

The classical mask misses **4,340/9,723 = 44.64%** of manual-unreadable A-lines.
Only **427/4,340 = 9.84%** of these misses lie in the first/last 32 columns;
this is mostly an interior problem, not merely dark edges.

| Group | Misses | Caught by score q0.96 | Caught by score q0.94 |
|---|---:|---:|---:|
| Training | 3,731 | 1,616 (43.31%) | 1,964 (52.64%) |
| Validation | 609 | 460 (75.53%) | 508 (83.42%) |
| Pooled | 4,340 | 2,076 (47.83%) | 2,472 (56.96%) |
| Pooled, caught by no existing reason | 1,104 | 113 (10.24%) | 169 (15.31%) |

These are score overlaps before accounting for other existing reasons; some
shadow misses are already withheld by scope/crossing. They show that entropy
does **not** make all residual shadow work redundant. It is particularly weak
on the 1,104 columns caught by no existing reason.

However, the misses are not simply a darker version of readable tissue:

| Feature, pooled median | Shadow misses | Shadow-detected manual exclusions | Human-positive on all eight surfaces |
|---|---:|---:|---:|
| CNR | 3.76 | 1.57 | 3.55 |
| Low-signal fraction | 0.260 | 0.420 | 0.287 |
| Relative column energy | −0.124 | −2.075 | 0.227 |
| Depth-gradient p90 | 0.0866 | 0.0823 | 0.0847 |
| Neighbor correlation | 0.956 | 0.904 | 0.967 |

The 1,104 entirely unprotected columns have median CNR 4.10 and low-signal
fraction 0.158. A broader low-signal cutoff is unlikely to isolate them without
discarding substantial readable tissue. Full quantiles and animal/QC breakdowns
are in `shadow_feature_distributions.csv`; these pooled similarities do not
establish absence of useful spatial information.

Five bounded signal extensions were tested: low CNR, high low-signal fraction,
low relative energy, weak depth gradient and low neighbor correlation. Each
threshold is the adverse-score q0.96 of training columns valid on all eight
surfaces, transferred unchanged. Each was tested alone and added to the q0.96
entropy+signal score. **All ten have higher validation leakage than entropy+signal
at matched supported coverage**; they do not uniformly lose on every error
statistic. None offers enough additional value to justify a detector change.

For example, after the q0.96 score and existing mask, 138 validation shadow
misses still retain some measurements. Low CNR catches 57 more but costs
**5,378 additional supported measurements**; low energy catches 12 for **220**;
neighbor correlation catches 51 for **2,751**. High low-signal fraction and weak
gradient catch **none** of these residual validation misses while still costing
21 and 56 supported measurements. See `signal_complementarity.csv` and
`signal_candidates.csv`.

The original shadow false-exclusion burden remains important. This experiment
never unmasks a shadow: it does not claim to solve over-withholding by the
classical detector, nor to rule out a future spatial detector.

## 4. Representative images inspected

Eight baseline/candidate images were generated using the measurement display
and inspected, with missing measurements shown as gaps. Candidate plots are
explicitly labelled simulations. `review/cases.json` links each paired image.

- **Partial success — TS325 D98 b0061:** the score removes much of the broad
  dim right region and narrow shadow regions marked unreadable. It still leaves
  predictions inside portions of the marked region; 161 supported measurements
  are additionally lost. This is a partial success, not a complete correction.
- **Useful tissue lost — TS169 D35 b0164:** whole-column crossing rejection
  removes additional boundaries near the right-side transition where dotted
  human targets exist, costing 143 supported measurements. An inconsistent
  inner boundary does not establish that every outer boundary is unusable.
- **Remaining failure — TS241 D21 b0159:** broad manual exclusion includes
  visible structure to the left of a central low-signal stripe. The score masks
  parts of the stripe but continues reporting measurements across much of the
  manually excluded range. Local darkness alone does not reproduce the human
  judgment. Manual labels remain untouched and authoritative.
- **Concentrated tail — TS325 6mo b0510:** ≥4 crossing flags removes much of the
  scrambled right region, yet displaced predictions remain through the central
  image and isolated right-side patches. The rule does not fix segmentation.
  This one image supplies 541 of the rule's 630 supported validation losses.

## 5. Decision and relationship to longer training

The decision was saved in `DECISION.md` before any possible inference edit.
**No production candidate passed the adoption decision.** The separate analysis
code, simulated masks, comparisons, and overlays are the implemented deliverable.
There was no reason to rerun the network, change inference semantics, invalidate
checkpoint resume, create a code branch, or merge anything.

Retain ≥4 crossing flags as an experimental candidate to recheck on the
longer-trained checkpoint. Re-examine the remaining unreadable regions there
as well. Training can alter crossings and uncertainty; these mask results are
not independent of model fit. Compare short and long training under the same
mask, then compare masks under the same model. Do not delay longer training to
build a detector unsupported by this investigation.

## 6. Verification, provenance and limits

- **16/16 existing synthetic/invariant tests passed**, plus independent checks
  reproducing the frozen audit counts, ensuring masks only remove measurements,
  verifying the ≥8 no-op, and checking matched-count discrepancies.
- The test suite ran with local metadata fixtures and synthetic temporary
  checkpoints in this folder, avoiding its normal writes into v2. No scientific
  checkpoint was created or altered. The normal status script was not run
  because it writes into v2 and reads across the full cohort; a read-only check
  was used instead.
- All 110 selected training/development-validation target fingerprints were
  verified. Snapshot checks cover file sizes and modification times throughout
  frozen v2/v3, plus content hashes of the Stage A package. Source evaluation
  fingerprints and the scientific checkpoint fingerprint are saved separately.
- The frozen manifest still records **160 labels / 32 packs / 28 footprints**.
  This is not a claim to have re-read every label: final-test animal arrays were
  deliberately not opened. No label, footprint, partition or manifest was edited.
- No raw volume, final-test animal array, or repeatability data was read; no
  training or final-test evaluation occurred. Only the existing training-WT
  prediction chunks were inspected for the whole-volume crossing count.
- The external readability helper acquired an explicit output argument during
  the session. The first display attempt stopped on a missing argument and was
  rerun with this folder explicitly supplied. This investigation did not edit
  that external helper; a local snapshot is retained for reproducibility.
- All new scientific artifacts are in this folder. `integrity_final.json`
  records the end-of-run check and scientific package versions.

Only two development-validation animals have corrected evidence; TS336 is
rejected-only and the WT volume is from training. Human-positive flags inherit
the legacy surface-wide editing granularity. Unknown does not mean readable.
Multiple candidate comparisons are exploratory, not independent validation.
No result is calibrated, an acceptance criterion, a generalization claim, or
a validated retinal measurement.
