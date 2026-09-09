# Stage A readability-aware withholding — experiment v3

**Experimental. Not validated, not calibrated, not production-ready.** No
final-test animal (TS247, TS283, TS328) was read, evaluated, inspected or
unlocked. No repeatability data was read. No human label, manifest, partition or
checkpoint was written or modified. All work is derived from the frozen
`20260908_v2` dataset and the `dev_seed20260908` checkpoint.

## What is here

| Path | Contents |
|---|---|
| `RUN_REPORT.md` | the deliverable: corrected display, mask audit, method comparison, recommendation |
| `eval_train/` | `stage_a.evaluate --split train --predictor model` (needed for the audit; train split only) |
| `review/{train,validation}/` | corrected review overlays — `*__measurement.png` (default, gaps at withheld columns) and `*__raw_diagnostic.png` (`--raw`) |
| `audit/` | existing-mask vs. human-evidence tables (`by_*.csv`, `reason_overlap_per_bscan.csv`, `audit_summary.json`) |
| `features/columns.npz` | per-A-line signal/contrast/continuity features + per-surface entropy + readability labels, train + dev-validation |
| `compare/` | existing mask vs. simple entropy+signal candidate vs. learned logistic-regression pilot; `coverage_error_curves.csv`, `matched_coverage.json`, `whole_bscan_rejection.csv`, `coverage_error.png` |
| `inspection_readability/` | pre-existing single-B-scan diagnostic (TS325 b0128), unchanged |

## Provenance handling

* All code added this session is in **`code/stage_a_readability.py`, outside the
  `stage_a` package**, so `stage_a.train.code_identity()` is unchanged and every
  existing checkpoint stays resumable. `python -m stage_a.test_stage_a` → 16/16;
  `python code/stage_a_report.py` → `scientific_versions_unchanged: true`,
  `repeatability_data_read: false`, 160 labels / 32 packs / 28 footprints
  unchanged, before and after.
* The documented resume bug (`run_step_*.json` overwritten with zero events when
  a completed budget is resumed) is **not triggered**: no U-Net training or
  resume was run. The learned pilot is a separate ~30-line logistic regression
  with no checkpoint.
* The learned pilot deliberately does **not** add a rejection head to the
  boundary loss, so it cannot lower training loss by abstaining on hard
  supervised examples.

## Reproduce

```powershell
Set-Location 'G:\OCT_TreeShrew\octa'
. 'D:\Anaconda\shell\condabin\conda-hook.ps1'; conda activate octa
$env:PYTHONPATH = 'G:\OCT_TreeShrew\octa\code'

python -m stage_a.evaluate --split train --predictor model `
  --checkpoint outputs/stage_a/20260908_v2/dev_seed20260908/best.pt `
  --out outputs/stage_a/20260908_v3_readability/eval_train --device cuda

python code/stage_a_readability.py display --split validation `
  --eval outputs/stage_a/20260908_v2/dev_seed20260908/eval_validation --raw
python code/stage_a_readability.py display --split train `
  --eval outputs/stage_a/20260908_v3_readability/eval_train

python code/stage_a_readability.py audit `
  --eval-train outputs/stage_a/20260908_v3_readability/eval_train `
  --eval-val   outputs/stage_a/20260908_v2/dev_seed20260908/eval_validation

python code/stage_a_readability.py features `
  --eval-train outputs/stage_a/20260908_v3_readability/eval_train `
  --eval-val   outputs/stage_a/20260908_v2/dev_seed20260908/eval_validation
python code/stage_a_readability.py compare
```
