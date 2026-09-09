# Stage A first development training run — 2026-09-08

**Experimental. Not validated, not calibrated, not production-ready.** No
final-test animal was evaluated, inspected or unlocked. No threshold in this
report is an acceptance criterion. Every number is development-validation
evidence on **two animals** (TS169, TS325) and **14 eligible B-scans**.

Run directory: `outputs/stage_a/20260908_v2/dev_seed20260908`.

## 1. Pre-flight

| Check | Result |
|---|---|
| `conda activate octa` | python 3.11.15, `D:\Anaconda\envs\octa` |
| `code\check_env.py` | numpy 2.4.6, h5py 3.16.0, scipy 1.17.1, skimage 0.26.0, matplotlib 3.11.1, pandas 3.0.5, PySide6 6.11.1 — all ok |
| `python -m pip check` | No broken requirements |
| Torch / CUDA | 2.8.0+cu126, CUDA 12.6, RTX 3060 Ti (8.00 GiB total, **6.97 GiB free** at launch) |
| `code\stage_a_report.py` | 160 first-round labels, 32 packs, 28 footprints **unchanged**; 160/160 caches present; pack pixels exact; targets contained; QC/source join verified; `scientific_versions_unchanged: true`; `repeatability_data_read: false` |
| Dataset | `dataset_id 1ab0f7b3…`, `partition_id 0ef449a1…`, 89 eligible B-scans / 23 volumes / 9 animals, 172,308 boundary-column targets |
| `python -m stage_a.test_stage_a` | **16/16 OK** (re-run after this session's changes: still 16/16) |

Peak CUDA memory during training was 617,725,440 B (~589 MiB) against 6.97 GiB
free, so memory was never a constraint.

## 2. Training

No `dev_seed20260908` run existed, so this is a fresh run from seed 20260908 —
**not** initialised from any smoke checkpoint (`config.smoke = false`).

```
python -m stage_a.train --data outputs/stage_a/20260908_v2 \
  --out outputs/stage_a/20260908_v2/dev_seed20260908 \
  --epochs 40 --steps-per-epoch 48 --base 8 --lr 0.0003 \
  --region-weight 0.1 --seed 20260908 --device cuda
```

* 1,920 optimizer steps (40 × 48), one full-resolution B-scan per step,
  122,799 parameters, **308.97 s** wall clock on CUDA.
* All 1,920 losses finite; gradient norms finite and non-zero throughout
  (min 3.13, max 392.5, clipped at 5.0). No `FloatingPointError`, no
  `RuntimeError("Zero gradients")`, no OOM.
* Checkpoints written every epoch; `checkpoint_reload_exact: true` (reloaded
  model reproduced the prediction tensor exactly, shape `[1, 8, 512]`).
* Only warning: PyTorch's documented notice that the CUDA region
  cross-entropy has no deterministic kernel. PowerShell 5.1 wraps native
  stderr as a `NativeCommandError` ErrorRecord — that is a shell artifact,
  not a failure.

**Selection.** Best checkpoint by animal-macro development-validation loss:
**epoch 38, step 1824, loss 3.66357** (`best.pt`, sha256 `79586ffb71e3…`).
`last.pt` is epoch 40 (sha256 `34bf06f11b7f…`). Both carry
`experimental: true, validated: false` and a `code_identity` matching the
current package.

**The run is not converged.** Validation loss fell monotonically apart from
small wobbles right through epoch 40 (ep1 18.46 → ep10 8.45 → ep20 5.25 →
ep30 4.07 → ep38 3.66 → ep40 3.75), and train/validation stayed within ~0.5
of each other the whole way. 40 epochs was a budget, not a plateau; there is
no overfitting signature to stop on. Full curve in
`training_history_epochs.csv` / `training_history_steps.csv`.

## 3. Checkpoint reload and resume

`outputs/stage_a/20260908_v2/resume_verification/` holds a controlled A/B:
4 epochs straight vs. 2 epochs + resume-to-4 from `last.pt`.

* Sample sequence **identical** (all 192 steps, same key and animal per step).
* Per-step losses identical to **0.000e+00**; validation losses identical to
  all printed digits; final loss 13.329164 in both.
* Both arms report `checkpoint_reload_exact: true`.
* Their first four validation losses reproduce the full run's epochs 1–4
  exactly, so the delivered run is reproducible from seed on this machine.
* Volume inference resume was also verified: re-running the inference command
  reused all 512 chunks, rewrote none, and byte totals were unchanged.

**Defect found, not fixed — read this before resuming.** Running the
documented resume command against an *already complete* run silently
overwrites `run_step_<N>.json` with an events list of length 0, destroying the
training history. Reproduced in `resume_verification/straight` (192 events →
0). The cause is that `train.run()` writes the run JSON unconditionally after
the `while step < target_steps` loop, which does not execute when the run is
already at its target.

I deliberately did **not** patch `train.py`. `code_identity()` hashes every
`.py` in `code/stage_a/`, and the resume guard rejects any checkpoint whose
`code_identity` differs — so editing `train.py` now would permanently block
resuming *this* checkpoint, which is exactly what the recommended next step
(a longer budget) needs. Apply the fix at the moment a fresh longer run is
started instead. Suggested minimal change: skip the trailing `write_json` (or
write to a `_resume` suffix) when no step was taken this invocation.

Mitigation applied meanwhile: the history is archived as
`training_history_step001920.archived.json` plus the two CSVs, and the
analysis tooling added in this session (`code/stage_a_compare.py`,
`code/stage_a_review.py`) was deliberately placed **outside** the package so
it does not perturb `code_identity`.

## 4. Validation comparison

Same 38 validation decisions, same frozen eligible masks, for all three
predictors. Commands and outputs:

| Predictor | Output |
|---|---|
| `unet_dev` (this checkpoint) | `dev_seed20260908/eval_validation` |
| `stored-auto` | `../baseline_validation` |
| `v2` (stored classical) | `../v2_validation` |
| head-to-head | `../comparison_validation` |

### Baseline coverage — report this before any head-to-head number

| Predictor | Decisions with prediction | Eligible B-scans covered | Eligible animals covered |
|---|---:|---:|---:|
| unet_dev | 38 / 38 | 14 / 14 | 2 / 2 |
| stored_auto | 38 / 38 | 14 / 14 | 2 / 2 |
| **v2** | **34 / 38** | **11 / 14** | **1 / 2** |

The stored v2 segmentation has **no prediction for any B-scan of
`TS169_OS_2025-01-14_D35_s04_121533`** — that is all three eligible TS169
B-scans, i.e. one of only two corrected validation animals. Those columns stay
in v2's eligible denominators as failures; they are not skipped. Consequently:

* **Complete-cohort** numbers (14 B-scans, 2 animals) are directly comparable
  only between `unet_dev` and `stored_auto`. v2's complete-cohort coverage is
  0.731–0.903 by surface and its `failure_fraction_of_eligible` (0.13–0.46)
  is dominated by absence, not by error.
* **Shared-available** numbers (34 decisions, 11 eligible B-scans, TS325 only)
  are the only three-way comparison. They exclude the entire high-QC TS169
  animal, so they are a smaller and different cohort — not a complete-cohort
  result.
* In per-animal tables, v2's TS169 rows show `gross_error_fraction = 0.000`
  **because there are no predictions to be gross**. Read `coverage` /
  `failure_fraction_of_eligible` on those rows, never the gross fraction.

### Boundary error, complete cohort, raw (µm)

`median | p95 | max | gross>25 µm fraction of eligible`

| Surface | unet_dev | stored_auto | v2 (11/14 B-scans) |
|---|---|---|---|
| ILM | 4.3 \| 144.3 \| 349.3 \| 0.163 | **0.0 \| 39.4 \| 107.9 \| 0.071** | 0.0 \| 46.0 \| 107.9 \| 0.071 |
| RNFL_GCL | **4.4 \| 50.4 \| 402.9 \| 0.091** | 22.2 \| 84.1 \| 109.2 \| 0.465 | 15.3 \| 38.3 \| 80.9 \| 0.232 |
| GCL_IPL | **2.9 \| 40.8 \| 466.2 \| 0.060** | 26.8 \| 87.1 \| 123.2 \| 0.528 | 15.0 \| 40.4 \| 83.4 \| 0.235 |
| IPL_INL | 4.7 \| 132.5 \| 446.0 \| 0.154 | 2.6 \| 57.7 \| 149.1 \| 0.171 | **5.8 \| 25.2 \| 70.2 \| 0.041** |
| INL_OPL | 4.1 \| 72.2 \| 452.5 \| 0.079 | **3.7 \| 24.9 \| 176.8 \| 0.050** | 10.1 \| 45.7 \| 50.5 \| 0.162 |
| OPL_ONL | 2.9 \| 42.5 \| 463.2 \| 0.072 | 2.7 \| 30.3 \| 187.4 \| 0.076 | 9.1 \| 29.7 \| 49.9 \| 0.066 |
| PR_RPE | 3.2 \| 133.9 \| 424.9 \| 0.076 | 12.8 \| 20.7 \| 199.1 \| 0.044 | 13.4 \| 18.6 \| 44.6 \| **0.003** |
| RPE | **1.4 \| 5.0 \| 37.6 \| 0.0003** | 0.6 \| 96.6 \| 195.7 \| 0.106 | 1.1 \| 6.8 \| 21.3 \| 0.000 |

Full tables — every surface and band, both cohorts, raw and retained, pooled
plus per-animal, per-QC, per-biology and per-scope — are in
`comparison_validation/comparison.csv` and
`comparison_validation/comparison_animal_macro.csv`.

### Thickness bands, complete cohort, raw (µm)

`median abs | mean abs | mean signed | gross>25 µm fraction of eligible`

| Band | unet_dev | stored_auto | v2 (11/14) |
|---|---|---|---|
| RNFL | **5.2 \| 14.6 \| −2.0 \| 0.141** | 23.5 \| 28.8 \| −23.1 \| 0.477 | 18.8 \| 20.4 \| +14.0 \| 0.350 |
| GCL | 3.2 \| 6.5 \| −0.4 \| 0.046 | 3.8 \| 4.9 \| −2.6 \| **0.004** | 4.1 \| 4.9 \| +2.2 \| 0.002 |
| IPL | **4.0 \| 20.0 \| −6.1 \| 0.160** | 23.5 \| 22.8 \| +18.5 \| 0.466 | 9.7 \| 11.2 \| −4.2 \| 0.047 |
| INL | 5.3 \| 18.0 \| +4.7 \| 0.172 | **5.0 \| 8.6 \| +4.4 \| 0.073** | 5.5 \| 7.7 \| +6.1 \| 0.045 |
| OPL | 3.7 \| 6.2 \| +0.3 \| 0.051 | 4.3 \| 5.0 \| −3.6 \| **0.000** | 5.0 \| 6.5 \| −4.1 \| 0.000 |
| PHOTORECEPTOR | **3.4 \| 9.0 \| −3.2 \| 0.062** | 13.8 \| 15.1 \| +14.3 \| 0.090 | 5.8 \| 6.6 \| +2.1 \| 0.000 |
| RPE | **2.5 \| 4.0 \| +2.8 \| 0.004** | 11.2 \| 10.6 \| −8.5 \| 0.000 | 11.4 \| 10.9 \| −10.8 \| 0.000 |
| TOTAL | 3.0 \| 8.2 \| −3.9 \| 0.070 | 1.0 \| 14.2 \| −8.9 \| 0.107 | **0.9 \| 2.7 \| +1.2 \| 0.007** |

Median and mean absolute error diverge sharply for the U-Net (IPL 4.0 vs
20.0 µm, INL 5.3 vs 18.0) and barely at all for `stored_auto` (IPL 23.5 vs
22.8): the U-Net is usually much more accurate and occasionally much worse,
while the classical cascade is consistently biased. §5 locates that tail.

Signed thickness bias for the U-Net is small on every band (|mean signed|
≤ 6.1 µm, and ≤ 4.7 µm on all but IPL), whereas `stored_auto` carries the
known large opposite-signed RNFL (−23.1) / IPL (+18.5) pair and a +14.3 µm
PHOTORECEPTOR bias. The U-Net's individual boundaries all carry a small
negative mean signed offset (−0.2 to −17.5 µm; animal-macro +0.03 on RPE to −15.5 on IPL_INL),
which largely cancels in the closed bands — that is the same
"common-shift cancels" behaviour the test suite checks for.

### Raw versus retained, and measurement coverage

`retained` = the model's own reason-coded withholding (outside scope, shadow,
crossing; no entropy threshold applied). Complete cohort, pooled:

| Surface | raw gross | retained gross | retained coverage |
|---|---:|---:|---:|
| ILM | 0.163 | 0.135 | 0.972 |
| RNFL_GCL | 0.091 | 0.049 | 0.948 |
| GCL_IPL | 0.060 | 0.016 | 0.903 |
| IPL_INL | 0.154 | 0.065 | 0.890 |
| INL_OPL | 0.079 | 0.030 | 0.930 |
| OPL_ONL | 0.072 | 0.024 | 0.938 |
| PR_RPE | 0.076 | 0.018 | 0.941 |
| RPE | 0.0003 | 0.0003 | 1.000 |

Withholding roughly halves-to-quarters the gross rate at a 0–11% coverage
cost (ILM 2.8%, IPL_INL 11.0%, RPE 0%), but it does **not** remove the extreme tail (retained max still
270–463 µm on the inner surfaces): the worst failures are inside scope, out of
shadow and ordered. Thickness-band retained coverage (needs two eligible,
retained endpoints) is 0.866–0.999. `failure_fraction_of_eligible` in retained
mode counts the withheld columns as failures, which is why it *rises* while
gross falls — both are reported side by side and neither should be quoted alone.

### Per-animal and per-QC

* **TS169 (high QC; 3 eligible B-scans of 4 decisions; 1,024 eligible columns
  per surface, 340 for ILM).** The
  U-Net is better than `stored_auto` on 6 of 8 surfaces and dramatically
  better on RNFL_GCL (2.4 vs 37.2 µm median; gross 0.022 vs 0.639) and
  GCL_IPL (1.9 vs 44.3; 0.025 vs 0.646). It is worse on ILM (5.8 vs 0.0) and on RPE median
  (2.0 vs 0.0), and its PR_RPE tail is far worse (max 424.9 vs 16.1 µm). v2 has no predictions here.
* **TS325 (low + medium QC, 10 B-scans).** Same pattern, weaker: RNFL_GCL 5.2
  vs 19.2/15.3 and GCL_IPL 3.2 vs 24.6/15.0, but ILM 4.1 vs 0.0/0.0 with
  p95 157.6 vs 46.0, and IPL_INL/INL_OPL tails worse than both baselines.
* **By QC group** the U-Net's median error is stable (high 1.9–5.8, medium
  2.4–6.4, low 1.0–5.1 µm) — but its *tails* are entirely a low/medium-QC
  phenomenon (p95 up to 220 µm at low QC, 157.6 at medium, ≤ 64.5 at high).
  `stored_auto` shows the opposite: its RNFL_GCL/GCL_IPL failure is worst at
  high QC (0.639/0.646).

## 5. Where it still fails

`review_validation/per_bscan_localized_failure.csv` ranks every validation
B-scan by contiguous failure extent.

**The tail is one B-scan.** `TS325_OD_2026-05-26_6mo_s01_112940_b0510`
(low QC, `footprint_negative_timing_unknown`) has median error 98.1 µm, 75.5%
gross columns and a **148-column (422 µm) contiguous failure run**. Removing
that single B-scan from the pooled complete cohort:

| Surface | p95 with | p95 without | gross with | gross without |
|---|---:|---:|---:|---:|
| ILM | 144.3 | 41.9 | 0.163 | 0.087 |
| RNFL_GCL | 50.4 | 17.5 | 0.091 | 0.035 |
| GCL_IPL | 40.8 | 10.4 | 0.060 | 0.018 |
| IPL_INL | 132.5 | 55.8 | 0.154 | 0.104 |
| INL_OPL | 72.2 | 10.7 | 0.079 | 0.007 |
| OPL_ONL | 42.5 | 11.6 | 0.072 | 0.014 |
| PR_RPE | 133.9 | 11.6 | 0.076 | 0.012 |

This is reported as a **sensitivity, not as the headline**: 1 of 14 validation
B-scans failing catastrophically is a 7% whole-B-scan failure rate, and with
two validation animals that estimate is extremely coarse. The overlay
(`overlays/worst_localized_148col__…b0510.png`) shows why — the retina is
barely above noise, the human targets sit in a band the model never locks
onto, and the model instead tracks deeper choroidal structure across half the
image. Its entropy is correspondingly the highest in the split (mean 0.549,
pinned at 1.0 across the dark left third).

Second and third worst: `TS325_…D98_s01_131308_b0061` (69 columns, ILM sits
~70 px too deep across a heavily stripe-shadowed region) and
`TS169_…D35_s04_121533_b0365` (45 columns, IPL_INL excursions into two vessel
shadows on an otherwise excellent high-QC B-scan).

**ILM is the model's weakest surface and the one clear regression** against
the classical cascade (gross 0.163 vs 0.071; median 4.3 vs 0.0). This inverts
the classical picture, where ILM is the strongest anchor and RNFL_GCL/GCL_IPL
are the weak ones. ILM also has the fewest eligible validation columns (3,517
vs 4,580), so it is the least-supervised surface as well.

**No ordering constraint.** The model emits eight independent expectations;
nothing enforces ILM ≤ RNFL_GCL ≤ … ≤ RPE. On the WT volume in §7, **every one
of 512 B-scans** contains crossing columns (median 14.9% of boundary-columns,
p90 42.9%, max 57.6%). Crossing is the single largest withholding reason
(443,805 columns vs 372,736 for shadow).

Overlays generated (`review_validation/overlays/`, original disk coordinates,
prediction solid / human target dotted, entropy strip below): 4 worst
localized failures + 5 representative median/best examples per animal × QC
group; index in `overlay_index.csv`.

## 6. Entropy as a candidate error signal (development validation only)

Computed only on validation columns, from `best.pt`. Nothing was tuned on it.

| Group | n columns | Spearman(entropy, abs err) | AUROC entropy → gross | median entropy ok / gross |
|---|---:|---:|---:|---|
| pooled | 34,809 | 0.473 | **0.940** | 0.396 / 0.571 |
| ILM | 3,517 | 0.605 | 0.945 | 0.409 / 0.664 |
| RNFL_GCL | 4,580 | 0.491 | 0.923 | 0.440 / 0.635 |
| GCL_IPL | 4,580 | 0.393 | 0.964 | 0.416 / 0.560 |
| IPL_INL | 4,580 | 0.577 | 0.966 | 0.373 / 0.649 |
| INL_OPL | 4,580 | 0.338 | 0.972 | 0.463 / 0.577 |
| OPL_ONL | 4,580 | 0.395 | 0.984 | 0.384 / 0.506 |
| PR_RPE | 4,580 | 0.391 | 0.992 | 0.363 / 0.470 |
| RPE | 3,812 | 0.232 | 1.000 | 0.337 / 0.502 |
| TS169 | 7,508 | 0.233 | 0.984 | 0.384 / 0.722 |
| TS325 | 27,301 | 0.526 | 0.931 | 0.399 / 0.564 |

Entropy does predict error: AUROC 0.92–1.00 per surface for the >25 µm
event. The rank correlation with the *magnitude* of error is much weaker
(0.23–0.61), so entropy separates "wrong" from "right" far better than it
orders "how wrong".

Candidate operating points (`entropy_risk_coverage.csv`) — **provisional, not
calibrated, not acceptance thresholds, and read off the same two animals used
for model selection**:

| Coverage | Threshold | Retained median | Retained p95 | Retained gross | Gross columns left per 1,000 eligible |
|---:|---:|---:|---:|---:|---:|
| 1.00 | — | 3.31 | 70.1 | 0.087 | 86.5 |
| 0.95 | 0.618 | 3.14 | 29.6 | 0.057 | 54.0 |
| 0.90 | 0.531 | 2.99 | 15.7 | 0.034 | 30.3 |
| 0.80 | 0.471 | 2.79 | 10.0 | 0.013 | 10.4 |
| 0.70 | 0.445 | 2.64 | 8.6 | 0.006 | 4.5 |

Conditional error falls partly *because* coverage falls, so the last column —
absolute gross columns remaining per 1,000 eligible — is the honest one. No
threshold should be fixed until the scientific error/coverage requirement
exists; the same two animals cannot both select the model and calibrate its
abstention.

## 7. Original-coordinate inference verification

```
python -m stage_a.inference --checkpoint outputs/stage_a/20260908_v2/dev_seed20260908/best.pt \
  --scan-id TS165_OS_2025-04-29_WT_s02_121711 \
  --out outputs/stage_a/20260908_v2/dev_seed20260908/volume_TS165
```

Development (training-split) WT volume, **512/512 B-scans complete**,
`full_volume_complete: true`.

| Check | Result |
|---|---|
| Checkpoint recorded in job | sha256 `79586ffb71e3…` = `best.pt` |
| Orientation | redetected from the volume profile, `vitreous_high = true` |
| Disk ↔ canonical round-trip | max **0.00003052 px** (float32 storage) |
| `retained == (reason_bits == 0)` | true on all 512 chunks |
| `retained_rows` NaN wherever not retained | true |
| Experimental thickness finite only where retained | true |
| `validated_thickness_um` | **all NaN**, `validated: false`, on all 512 chunks |
| Entropy threshold | `None` — no uncertainty withholding applied |
| Re-run | reused all 512 chunks, rewrote none, byte totals identical |

Withholding over 2,097,152 boundary-columns: retained 1,411,745 (67.3%);
crossing 443,805; shadow 372,736; outside scope 0 (TS165 WT is an independent
control, so the whole en-face grid is in scope — the exclusion machinery is
exercised, it simply excludes nothing here). Per-B-scan retained fraction
ranges 0.359–0.881, median 0.695.

Outputs are explicitly experimental: no validated measurement is produced, and
the shadow mask is the frozen classical artifact, not learned visibility.

## 8. Assessment

**What improved.** The two boundaries the classical cascade has never placed
from the image — RNFL_GCL and GCL_IPL — are transformed. Pooled median error
drops 22.2 → 4.4 µm and 26.8 → 2.9 µm, gross rate 0.465 → 0.091 and
0.528 → 0.060, on a *complete* two-animal cohort with full coverage. The
derived RNFL and IPL bands follow (RNFL 23.5 → 5.2 µm median, gross 0.477 →
0.141; IPL 23.5 → 4.0, 0.466 → 0.160) and the large opposite-signed
RNFL/IPL bias pair of the classical output collapses to ≤ 6.1 µm. RPE is the
best-measured surface (median 1.4 µm, p95 5.0 µm, gross 0.0003) — level
with stored v2 on the shared cohort (1.2 vs 1.1 µm median) and far better
than `stored_auto`'s tail (p95 96.6 µm). Signed
thickness bias is small on every band. This is the first evidence in this
project that a learned per-column cost reaches the weak inner boundaries that
prior refitting could not — consistent with the earlier finding that the
prior-window cascade is architecturally capped.

**What still fails.** ILM regressed (gross 0.163 vs 0.071) and is now the
limiting surface, echoing the pre-existing ILM problem on low-QC volumes. One
of 14 validation B-scans fails catastrophically over 148 contiguous columns
and drives most of the reported tails; excluding it drops pooled p95 by 2–11×
on six of eight surfaces. Ordering is not enforced, so every B-scan of a real
volume contains crossing columns and 33% of columns are withheld before any
uncertainty gate. Reason-coded withholding reduces gross rates but leaves the
extreme tail untouched, so the worst errors are confident, in-scope and
ordered — the plausible-but-unsupported failure mode this project has been
bitten by before, now in learned form.

**What the evidence does not support.** Nothing here is a generalization
claim. Two validation animals, 14 B-scans, one of which dominates the tail;
no WT animal outside training, so there is no independent control estimate at
all; supervision is legacy surface-wide, so an "eligible" column is not
evidence that a human drew that column. v2 is missing an entire validation
animal, so the three-way comparison is TS325-only. Entropy's AUROC was
measured on the same two animals that selected the checkpoint.

**Does it support a focused next development step? Yes — one.** Train longer
on this exact configuration. Validation loss was still falling at epoch 40
with train and validation tracking within ~0.5 and no overfitting signature,
and the whole run costs 309 s, so the 40-epoch budget — not the architecture,
the width, the learning rate or the loss weights — is the binding constraint
on the current result. That single change is cheap, isolates one variable, and
must precede any conclusion about ILM, about the catastrophic-B-scan rate, or
about whether an ordering constraint is needed. Apply the §3 `train.py` fix
when starting it, since that run begins from scratch anyway.

Not recommended now, on this evidence: an architecture sweep, a CNV
specialist, any acceptance threshold, any calibrated abstention, and any
approach to the locked test animals.

## 9. Reproducible commands

```powershell
Set-Location 'G:\OCT_TreeShrew\octa'
. 'D:\Anaconda\shell\condabin\conda-hook.ps1'
conda activate octa
$env:PYTHONPATH = 'G:\OCT_TreeShrew\octa\code'

# pre-flight
python code\check_env.py
python code\stage_a_report.py
python -m stage_a.test_stage_a
python -m pip check

# training (fresh, seed 20260908)
python -m stage_a.train --data outputs/stage_a/20260908_v2 --out outputs/stage_a/20260908_v2/dev_seed20260908 --epochs 40 --steps-per-epoch 48 --base 8 --lr 0.0003 --region-weight 0.1 --seed 20260908 --device cuda

# evaluation on the same validation decisions
python -m stage_a.evaluate --split validation --predictor model --checkpoint outputs/stage_a/20260908_v2/dev_seed20260908/best.pt --out outputs/stage_a/20260908_v2/dev_seed20260908/eval_validation
python -m stage_a.evaluate --split validation --predictor stored-auto --out outputs/stage_a/20260908_v2/baseline_validation
python -m stage_a.evaluate --split validation --predictor v2 --out outputs/stage_a/20260908_v2/v2_validation

# head-to-head, complete cohort and shared-available cohort
python code\stage_a_compare.py --split validation --evals unet_dev=outputs/stage_a/20260908_v2/dev_seed20260908/eval_validation stored_auto=outputs/stage_a/20260908_v2/baseline_validation v2=outputs/stage_a/20260908_v2/v2_validation --out outputs/stage_a/20260908_v2/comparison_validation

# overlays + entropy study (development validation only)
python code\stage_a_review.py --split validation --eval outputs/stage_a/20260908_v2/dev_seed20260908/eval_validation --out outputs/stage_a/20260908_v2/dev_seed20260908/review_validation --worst 4

# original-coordinate inference (re-run is a no-op that reuses chunks)
python -m stage_a.inference --checkpoint outputs/stage_a/20260908_v2/dev_seed20260908/best.pt --scan-id TS165_OS_2025-04-29_WT_s02_121711 --out outputs/stage_a/20260908_v2/dev_seed20260908/volume_TS165

# resume verification (separate scratch run directories)
python -m stage_a.train --data outputs/stage_a/20260908_v2 --out outputs/stage_a/20260908_v2/resume_verification/split --epochs 2 --steps-per-epoch 48 --base 8 --lr 0.0003 --region-weight 0.1 --seed 20260908 --device cuda
python -m stage_a.train --data outputs/stage_a/20260908_v2 --out outputs/stage_a/20260908_v2/resume_verification/split --epochs 4 --steps-per-epoch 48 --base 8 --lr 0.0003 --region-weight 0.1 --seed 20260908 --device cuda --resume outputs/stage_a/20260908_v2/resume_verification/split/last.pt
```

## 10. Scope compliance

* Labelling GUI never launched, closed or modified. No human annotation,
  repeatability pack, manifest or label file written or read for editing; the
  repeatability directory was not read. `stage_a_report.py` re-verified 160
  labels, 32 packs and 28 footprints unchanged, before and after.
* Frozen dataset and animal partitions untouched; `dataset_id` and
  `partition_id` unchanged; both eyes, all dates and repeats stay with their
  animal.
* Final-test animals (TS247, TS283, TS328) were never evaluated, inspected or
  predicted; no `--final-test-protocol` was created or supplied; the lock is
  still armed.
* Existing outputs preserved; all new artifacts are in new directories under
  `outputs/stage_a/20260908_v2/`.
* Eight-boundary anatomy `5-8surf-pr`, N=1 single-B-scan preprocessing
  (`native-single-db-p1-p99.5-v1`) and the documented supervision masks all
  retained unchanged.
* No architecture sweep, no CNV specialist, no production-readiness claim, and
  no dependence on repeatability results or GUI changes.

### Code changed this session

Two new analysis scripts, both **outside** `code/stage_a/` so that
`train.code_identity()` — and therefore resume compatibility of every existing
checkpoint — is unaffected:

* `code/stage_a_compare.py` — head-to-head predictor comparison on identical
  decisions, reporting complete and shared-available cohorts separately. Reads
  only prediction arrays already written by `stage_a.evaluate` plus the frozen
  targets; refuses the test split.
* `code/stage_a_review.py` — original-coordinate overlays and the
  entropy/error study. Deliberately torch-free: importing torch's `libomp`
  into the same process as matplotlib's MKL `libiomp5md` aborts with
  "OMP: Error #15" in this environment, so it repeats `Dataset`'s identity and
  fingerprint checks without the tensor loader. Refuses the test split.

No file under `code/stage_a/` was modified. `python -m stage_a.test_stage_a`
was re-run afterwards: **16/16 OK**, and `code_identity` still equals
`04752099e554…`, matching both delivered checkpoints.
