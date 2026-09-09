# Next step #1 — train the frozen Stage A `20260908_v2` config longer

> **Timing note — updated after execution approval.** The user explicitly
> authorized execution now on 2026-09-08. Check the current usage allowance;
> no reset credit is redeemed by this instruction. A full pass is one
> training run (~15–50 min wall clock depending on the budget) plus evaluation,
> the head-to-head comparison, overlays, and a written report — budget for the
> whole thing before starting, and if the reset window will not cover it, wait
> for the next one rather than stopping a run part-way. Keep all logs on disk and
> inspect compact summaries; do not stream long console output.

---

## Why this step

`outputs/stage_a/20260908_v2/dev_seed20260908/RUN_REPORT.md` §8 concludes with
exactly one recommended next development step: **train longer on this exact
configuration.** Validation loss had an overall downward trend through epoch 40
(ep30 4.07 → ep38 3.66 → ep40 3.75), train and validation tracked within ~0.5
of each other the whole way, and there was no overfitting signature to stop on.
Insufficient training duration is a hypothesis to test, not an established
explanation that rules out architecture or optimization limitations. The whole run costs
~309 s, so this is cheap and isolates one variable.

It must precede any conclusion about:

- **ILM**, which regressed against the classical cascade (gross 0.163 vs 0.071,
  median 4.3 vs 0.0 µm) and is now the limiting surface;
- the **catastrophic-B-scan rate** — one of 14 validation B-scans
  (`TS325_OD_2026-05-26_6mo_s01_112940_b0510`) fails over 148 contiguous columns
  and drives most of the reported tails;
- whether an **ordering constraint** is needed;
- and — from `outputs/stage_a/20260908_v3_readability/RUN_REPORT.md` §6 — whether
  **decoder entropy still carries the readability signal** once the model is
  better fit, and whether the leakage / worst-run magnitudes a readability gate
  would have to fix are still the same size.

This is a training-length change only. **No architecture sweep, no width / LR /
loss-weight change, no CNV specialist, no new model head, no acceptance
threshold, no calibrated abstention, no approach to the locked test animals.**

## Read first

- `AGENTS.md`, `CLAUDE.md`, the `octa-layer-segmentation` skill.
- `outputs/stage_a/20260908_v2/dev_seed20260908/RUN_REPORT.md` (all of it —
  especially §3 the resume bug, §5 where it fails, §8 assessment, §9 commands).
- `outputs/stage_a/20260908_v3_readability/RUN_REPORT.md` §3 and §6 (the gate and
  the entropy evidence this run will re-test).

## Do this, in order

### 1. Pre-flight — capture the baseline

```powershell
Set-Location 'G:\OCT_TreeShrew\octa'
. 'D:\Anaconda\shell\condabin\conda-hook.ps1'; conda activate octa
$env:PYTHONPATH = 'G:\OCT_TreeShrew\octa\code'

python code\check_env.py
python code\stage_a_report.py          # record: scientific_versions_unchanged, 160/32/28, code_identity
python -m stage_a.test_stage_a          # must be 16/16
python -m pip check
git status --porcelain                  # must be clean (or only expected untracked)
```

Record `code_identity`, the `dataset_id` / `partition_id`, and the label / pack /
footprint counts. These are the before-numbers for the provenance section.

### 2. Fix the resume-clobbers-history bug (deliberate, committed)

`stage_a/train.run()` writes `run_step_<N>.json` unconditionally after the
`while step < target_steps` loop. When the loop body never executes (run already
at target), it overwrites the events list with length 0 and destroys the
history — reproduced in `20260908_v2/resume_verification/straight` (192 → 0).

Minimal fix: **skip that trailing `write_json` (or write it to a `.resume`
suffix) when zero optimizer steps were taken this invocation.** Do not touch or
weaken the `code_identity` guard itself.

This change will alter `code_identity` and therefore make
`20260908_v2/dev_seed20260908/best.pt` non-resumable. That is acceptable **only
because this step starts a fresh run from seed** and nothing needs to resume
that checkpoint (the v3 readability work uses it for inference/eval, never
resume). Confirm that assumption still holds before committing.

```powershell
git checkout -b stage-a-train-longer
# edit code\stage_a\train.py  (the one guard, nothing else)
python -m stage_a.test_stage_a          # must still be 16/16
git add code\stage_a\train.py
git commit    # message: what the guard was, why, and that it invalidates 20260908_v2 resume
```

Do not merge without review.

### 3. Fresh longer training run

New versioned directory — **do not write inside `20260908_v2/`**. Follow the
date-prefixed convention, e.g. `outputs/stage_a/<YYYYMMDD>_v4_longtrain/`, with
the run under `dev_seed20260908/`.

Every hyperparameter identical to `20260908_v2` **except `--epochs`**:

```
python -m stage_a.train --data outputs/stage_a/20260908_v2 \
  --out outputs/stage_a/<YYYYMMDD>_v4_longtrain/dev_seed20260908 \
  --epochs 200 --steps-per-epoch 48 --base 8 --lr 0.0003 \
  --region-weight 0.1 --seed 20260908 --device cuda
```

- `--data` still points at the frozen `20260908_v2` dataset — same
  `dataset_id` / `partition_id`, same eight-boundary contract (`5-8surf-pr`),
  same N=1 preprocessing (`native-single-db-p1-p99.5-v1`).
- Best checkpoint by animal-macro dev-validation loss, same as before.
- Run 200 epochs. Extend once to 400 only if the mean validation loss over
  epochs 181–200 is at least 1% below epochs 161–180, the best validation
  epoch is after 180, and the validation-minus-training mean-loss gap has
  increased by no more than 0.5 between those windows. This is a prespecified
  development-budget rule, not proof that overfitting is absent. Resume from
  the new run's `last.pt` with every other setting unchanged. Stop at 200
  if the rule is not met; otherwise stop at 400 regardless of the curve.
  Preserve both invocations' histories and document the full curve.
- Watch for: any non-finite loss, zero gradients, OOM. Peak CUDA memory in v2
  was ~589 MiB against ~7 GiB free, so memory should not bind.

### 4. Evaluate and compare — same pipeline as `20260908_v2` §9

```powershell
python -m stage_a.evaluate --split validation --predictor model `
  --checkpoint outputs/stage_a/<YYYYMMDD>_v4_longtrain/dev_seed20260908/best.pt `
  --out outputs/stage_a/<YYYYMMDD>_v4_longtrain/dev_seed20260908/eval_validation
python -m stage_a.evaluate --split validation --predictor stored-auto `
  --out outputs/stage_a/<YYYYMMDD>_v4_longtrain/baseline_validation
python -m stage_a.evaluate --split validation --predictor v2 `
  --out outputs/stage_a/<YYYYMMDD>_v4_longtrain/v2_validation

python code\stage_a_compare.py --split validation --evals `
  unet_long=outputs/stage_a/<YYYYMMDD>_v4_longtrain/dev_seed20260908/eval_validation `
  stored_auto=outputs/stage_a/<YYYYMMDD>_v4_longtrain/baseline_validation `
  v2=outputs/stage_a/<YYYYMMDD>_v4_longtrain/v2_validation `
  --out outputs/stage_a/<YYYYMMDD>_v4_longtrain/comparison_validation

python code\stage_a_review.py --split validation `
  --eval outputs/stage_a/<YYYYMMDD>_v4_longtrain/dev_seed20260908/eval_validation `
  --out outputs/stage_a/<YYYYMMDD>_v4_longtrain/dev_seed20260908/review_validation --worst 4

# original-coordinate inference sanity (same training-split WT volume as v2)
python -m stage_a.inference `
  --checkpoint outputs/stage_a/<YYYYMMDD>_v4_longtrain/dev_seed20260908/best.pt `
  --scan-id TS165_OS_2025-04-29_WT_s02_121711 `
  --out outputs/stage_a/<YYYYMMDD>_v4_longtrain/dev_seed20260908/volume_TS165
```

Carry forward the v2-comparison caveat: **v2 has no stored prediction for any
B-scan of `TS169_OS_2025-01-14_D35_s04_121533`** (all three eligible TS169
B-scans, one of only two corrected validation animals), so the three-way
comparison is TS325-only and the `unet` ↔ `stored_auto` pair is the only
complete-cohort comparison.

### 5. Re-test the readability findings against the new checkpoint

```powershell
python -m stage_a.evaluate --split train --predictor model `
  --checkpoint outputs/stage_a/<YYYYMMDD>_v4_longtrain/dev_seed20260908/best.pt `
  --out outputs/stage_a/<YYYYMMDD>_v4_longtrain/eval_train --device cuda

python code\stage_a_readability.py features `
  --eval-train outputs/stage_a/<YYYYMMDD>_v4_longtrain/eval_train `
  --eval-val   outputs/stage_a/<YYYYMMDD>_v4_longtrain/dev_seed20260908/eval_validation
python code\stage_a_readability.py compare
```

Write the regenerated `features/` and `compare/` under the **new** run
directory, not over `20260908_v3_readability/`. Pass explicit `--out`-style
paths if `stage_a_readability.py` hardcodes `V3`; if it does, add an argument
rather than overwriting the frozen v3 artifacts.

## Report — `outputs/stage_a/<YYYYMMDD>_v4_longtrain/dev_seed20260908/RUN_REPORT.md`

Parallel the `20260908_v2` structure. Answer, with numbers against the v2
baseline in each case:

1. **Convergence.** Did validation loss plateau? At what epoch and loss? Full
   curve (`training_history_epochs.csv`). Train/val gap through the run.
2. **ILM.** Gross fraction and median vs v2's 0.163 / 4.3 µm. Did the regression
   against the classical cascade (0.071 / 0.0) close, narrow, or persist?
3. **The catastrophic B-scan** `TS325_OD_2026-05-26_6mo_s01_112940_b0510`:
   longest contiguous failure run, median error, mean entropy — vs the
   148-col / 98.1 µm / 0.549 baseline. Still catastrophic?
4. **RNFL_GCL / GCL_IPL** — the two boundaries the classical cascade never
   placed from the image. Held (v2: 4.4 / 2.9 µm median, gross 0.091 / 0.060)
   or drifted?
5. **Crossing rate** on the TS165 WT volume — measure the change against the
   original checkpoint. Longer training can change crossings even without
   adding an ordering constraint; do not assume the rate is unchanged.
6. **Readability signal.** From the regenerated `compare/`: does decoder
   entropy still dominate the learned logistic regression at matched coverage?
   Are the leakage and worst-contiguous-gross-run magnitudes a gate would have
   to fix still the same size, or did longer training shrink them?
7. **Decision this informs.** Whether ILM, the catastrophic-B-scan rate, and an
   ordering constraint still need dedicated attention; and whether
   readability-gate calibration can proceed — noting it *still* also needs
   step 3 (≥1 more corrected dev-validation animal) regardless of this result.

Keep the standing disclosures: two corrected validation animals only, one
B-scan dominates the tails, no WT animal outside training, legacy surface-wide
supervision, nothing here is a generalization or acceptance claim.

## Provenance rules (hard)

- **No final-test animal** (TS247, TS283, TS328) read, evaluated, inspected or
  unlocked. No `--final-test-protocol` created. **Repeatability tree not read.**
- **No human label, manifest, partition, footprint or existing checkpoint**
  written or modified. New training and verification checkpoints are allowed
  only under the new run directory. `label_gui.py` never launched. Human
  labels are never edited by a script.
- `20260908_v2/` and `20260908_v3_readability/` are **preserved**, except for
  this user-authorized prompt correction. All new experiment artifacts go
  under the new `<YYYYMMDD>_v4_longtrain/` directory.
- Animal-level isolation maintained: both eyes, all dates and repeats stay with
  their animal; training animals for fitting, dev-validation for exploratory
  comparison only.
- `python code\stage_a_report.py` before **and** after:
  `scientific_versions_unchanged: true`, `repeatability_data_read: false`,
  160 labels / 32 packs / 28 footprints unchanged.
- Run the report and test suite through a recorded wrapper that redirects
  their hardcoded v2 outputs and temporary files into the new run directory.
  The report normally fingerprints all splits: skip locked-animal file-content
  verification, disclose that limit, and derive full-cohort counts only from
  frozen manifest metadata. Never open locked animal images, labels, targets,
  caches, or repeatability data merely to satisfy an integrity check.
- `python -m stage_a.test_stage_a` → 16/16 after the `train.py` fix and again at
  the end.
- The `train.py` fix is the **only** permitted change under `code/stage_a/`,
  it is committed on a branch with a message explaining the `code_identity`
  invalidation, and it is not merged without review. `code/stage_a_readability.py`
  changes (if step 5 needs an `--out` argument) stay outside the package.
- End the run report with a scope-compliance section like `20260908_v2` §10.
