Opt-in Stage A conservative decoding experiment. All three completed iterations
live in [the experiment report](G:/OCT_TreeShrew/octa/outputs/stage_a/20260908_v6_conservative_decoder/RUN_REPORT.md).

The original epoch-124 boundary model is frozen. The decoder never restores
original scope/shadow/missing/crossing rejections. It uses bounded posterior
movement, order over all retained surface pairs, separate per-boundary support,
independent disconnected intervals, explicit jump gaps, and minimum retained
interval lengths. Later checkpoints inherit every earlier rejection. There are
no normal thickness priors and no classical boundary ground-truth targets.

C1, C2 and C3 are saved decoder configurations and measurement checkpoints;
they reference the same unchanged neural checkpoint. No experiment version is
enabled in production. C2 is the recommended review compromise; C3 loses useful
coverage without removing the remaining localized ILM error.

The source modules serve these roles:

- `decoder.py`: conservative decoding and reason bits.
- `experiment.py`: freeze training-derived settings, run each version, preserve
  source snapshots, score manual targets, and verify old artifact integrity.
- `test_decoder.py`: fourteen synthetic geometry and withholding contracts.
- `verify.py`: forty-one combined tests, checks all 114 measurement files, and
  exactly reruns both prespecified failure images for all three versions.
- `review.py`, `figures.py`: actual OCT scientific overlays and annotation cards.
- `analyze.py`, `report.py`: comparisons, paired location effects, residual errors,
  proposal-only annotation queue and reports.

Activate the environment in PowerShell before running Python:

```powershell
. 'D:/Anaconda/shell/condabin/conda-hook.ps1'
conda activate octa
$env:PYTHONPATH='G:/OCT_TreeShrew/octa/code'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:MPLCONFIGDIR='G:/OCT_TreeShrew/octa/outputs/stage_a/20260908_v6_conservative_decoder/mpl'
python G:/OCT_TreeShrew/octa/outputs/stage_a/20260908_v6_conservative_decoder/run_task.py tests stage_a_conservative_decoder.verify
```

The wrapper restricts writes to the new experiment directory and blocks final
test and repeatability contents. Completed version runs refuse to overwrite
their checkpoint. A future experiment needs a new output directory and frozen
plan. Plotting runs in a separate process from torch to avoid the local OpenMP
runtime conflict.

Measurements are native canonical coordinates (vitreous at depth zero), with
surface order ILM, RNFL_GCL, GCL_IPL, IPL_INL, INL_OPL, OPL_ONL, PR_RPE, RPE.
Rejected values are NaN, thickness requires both supported endpoints, and
`validated_thickness_um` is entirely NaN. Data remain experimental.

Human labels are read-only. The annotation CSV and cards are suggestions for
human review, never labels or a new source of ground truth. The existing GUI
and label format are unchanged by this experiment.
