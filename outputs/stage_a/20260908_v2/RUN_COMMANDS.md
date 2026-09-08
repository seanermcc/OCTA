# First full development run — prepared, not launched

Run in PowerShell. Activate `octa` before Python:

```powershell
Set-Location 'G:\OCT_TreeShrew\octa'
. 'D:\Anaconda\shell\condabin\conda-hook.ps1'
conda activate octa
$env:PYTHONPATH = 'G:\OCT_TreeShrew\octa\code'
```

Verify the prepared snapshot and software:

```powershell
python code/stage_a_report.py
python -m stage_a.test_stage_a
python -m pip check
```

The first full development candidate starts fresh from seed 20260908. It uses 40 epochs of 48 animal-balanced samples, one full-resolution B-scan per optimizer step, base width 8, boundary distribution plus masked regression loss, and 0.1 closed-band region-loss weight. These are initial development settings, not optimized settings or acceptance criteria. Do not initialize from the smoke checkpoint.

```powershell
python -m stage_a.train --data outputs/stage_a/20260908_v2 --out outputs/stage_a/20260908_v2/dev_seed20260908 --epochs 40 --steps-per-epoch 48 --base 8 --lr 0.0003 --region-weight 0.1 --seed 20260908 --device cuda
```

Checkpointing occurs at epoch boundaries; a stopped run resumes from its latest saved epoch (an unfinished epoch may be repeated). Best checkpoint selection uses animal-macro development-validation loss. No early-stop tolerance or calibrated uncertainty threshold is silently assumed.

```powershell
python -m stage_a.train --data outputs/stage_a/20260908_v2 --out outputs/stage_a/20260908_v2/dev_seed20260908 --epochs 40 --steps-per-epoch 48 --base 8 --lr 0.0003 --region-weight 0.1 --seed 20260908 --device cuda --resume outputs/stage_a/20260908_v2/dev_seed20260908/last.pt
```

Compare the candidate and fixed available baselines on exactly the same validation decisions and eligible masks:

```powershell
python -m stage_a.evaluate --split validation --predictor model --checkpoint outputs/stage_a/20260908_v2/dev_seed20260908/best.pt --out outputs/stage_a/20260908_v2/dev_seed20260908/eval_validation
python -m stage_a.evaluate --split validation --predictor stored-auto --out outputs/stage_a/20260908_v2/baseline_validation
python -m stage_a.evaluate --split validation --predictor v2 --out outputs/stage_a/20260908_v2/v2_validation
```

The stored-v2 command reports absent volume predictions explicitly; it does not rerun or retune the classical cascade. Historical v2 development overlapped some human examples. Use the coverage report before making a head-to-head comparison. Error/coverage curves include provisional entropy thresholds; calibrate and select a threshold only using development animals. Conditional error can improve merely because coverage falls, so examine raw risk and all-eligible failure rates together.

Resumable original-coordinate inference on a training volume:

```powershell
python -m stage_a.inference --checkpoint outputs/stage_a/20260908_v2/dev_seed20260908/best.pt --scan-id TS165_OS_2025-04-29_WT_s02_121711 --out outputs/stage_a/20260908_v2/dev_seed20260908/volume_TS165
```

Repeat that command to verify/reuse completed B-scan chunks. The current entry point requires a source registered in the frozen manifest; register new acquisitions in a new audited dataset version. Unknown scope remains unavailable. `--entropy-threshold` is optional and must come from development calibration. Outputs include canonical and disk rows, retained rows, entropy, reason bits, scope/shadow masks, and experimental thicknesses. Validated thicknesses remain NaN until a separate scientifically justified promotion workflow is implemented.

Final-test evaluation/inference is locked by default. After repeatability and scientific measurement requirements are settled, freeze a protocol JSON with `criteria_finalized: true`, this dataset's `dataset_id`, the chosen `checkpoint_sha256`, and `surface_thresholds` for all eight surfaces. Supply it with `--final-test-protocol` to an explicit test run. Do not use that switch for preparation, debugging or model selection. No such final-test protocol was created in this task.

To create a future data version, use a **new** directory for `stage_a.audit --out`, then `stage_a.cache --data` and `stage_a.partitions --data`. Review the coverage and animal design before freezing another version. Existing manifests and partitions refuse silent overwrite. Repeatability data is not ingested by these commands.
