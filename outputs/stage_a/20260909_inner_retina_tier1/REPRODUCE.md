# Reproduce or continue the inner-retina experiments

Run from `G:\OCT_TreeShrew\octa`. Activate the environment first. PyMaxflow is
isolated in this run's output directory; no conda packages were replaced.

```powershell
. 'D:/Anaconda/shell/condabin/conda-hook.ps1'
conda activate octa
$env:PYTHONPATH = 'G:/OCT_TreeShrew/octa/code;G:/OCT_TreeShrew/octa/outputs/stage_a/20260909_inner_retina_tier1/dependencies'
```

Use a new output directory for a new experiment. The frozen dataset defaults
to `outputs/stage_a/20260908_v2`; its final-test animals remain locked. Commands
below use `outputs/stage_a/<new-run>` as a placeholder, which must be replaced.

## Frozen evaluation and manual-reference audit

```powershell
python code/stage_a_inner_retina_audit.py --out outputs/stage_a/<new-run>/prerequisites
python code/stage_a_inner_retina.py --eval outputs/stage_a/20260908_v4_longtrain/dev_seed20260908/eval_validation --out outputs/stage_a/<new-run>/baseline
python code/stage_a_compare.py --scope inner-retina --evals unet_v4=outputs/stage_a/20260908_v4_longtrain/dev_seed20260908/eval_validation stored_auto=outputs/stage_a/20260908_v4_longtrain/baseline_validation v2=outputs/stage_a/20260908_v4_longtrain/v2_validation --out outputs/stage_a/<new-run>/comparison
```

The permitted cohort contains 68 corrected B-scans from seven animals. The
original prompt's 101-label cohort is not accessible without violating its
test lock. The user's instruction is to checkpoint and continue on the
permitted cohort, not to await another cohort choice.

## Classical control and four-head training

```powershell
python code/auto_seg_8layer_v2/eval_variants.py --inner-retina --loao --out outputs/stage_a/<new-run>/classical_loao
python code/stage_a_classical_scope.py --experiment outputs/stage_a/<new-run>/classical_loao --out outputs/stage_a/<new-run>/classical_validation
python code/stage_a_inner_train.py --out outputs/stage_a/<new-run>/four_head --heads 4 --epochs 200 --steps-per-epoch 48 --device cuda
python code/stage_a_decoder.py evaluate --checkpoint outputs/stage_a/<new-run>/four_head/best.pt --methods soft --out outputs/stage_a/<new-run>/four_head_eval --device cuda
```

Four-head training can resume with `--resume <run-directory>/last.pt` and the
same run settings. The original eight-head checkpoint is not overwritten.
The matched-endpoint classical control preserves the old endpoint provider and
its fitting history; its newly fitted fractions alone are animal-held-out.

## Measured decoder constraints and comparison

```powershell
python code/stage_a_decoder.py fit --out outputs/stage_a/<new-run>/constraints
python code/stage_a_decoder.py evaluate --checkpoint outputs/stage_a/20260908_v4_longtrain/dev_seed20260908/best.pt --constraints outputs/stage_a/<new-run>/constraints/constraints.json --out outputs/stage_a/<new-run>/decoder_comparison --device cpu
```

The default accuracy cohort includes every manually supported inner-retina
validation B-scan. `--include-unlabelled-decisions` additionally infers decisions
without manual reference, at considerable extra graph-cut cost. Those decisions
cannot establish boundary accuracy. `--methods soft,dp_project` runs the
dependency-free control without graph cut.

The completed comparison in this run was frozen from the original unpruned
graph predictions using `stage_a_decoder_finish.py`; all 14 manually supported
validation B-scans were present. The optional exact-pruning implementation is
a separate computational control and is not the default graph solver.

## Independent models, calibration, and outer-free endpoint control

```powershell
python code/stage_a_inner_cv.py --out outputs/stage_a/<new-run>/cv --heads 8 --epochs 124 --steps-per-epoch 48 --batch-folds 7 --device cuda
python code/stage_a_inner_calibrate.py --models outputs/stage_a/<new-run>/cv --decoder dp_project --out outputs/stage_a/<new-run>/calibration_dp --device cuda
python code/stage_a_inner_calibrate.py --models outputs/stage_a/<new-run>/cv --decoder soft --out outputs/stage_a/<new-run>/calibration_soft --device cuda
python code/stage_a_inner_calibration_plot.py --calibration outputs/stage_a/<new-run>/calibration_dp
python code/auto_seg_8layer_v2/eval_variants.py --inner-retina --loao --inner-anchor-models outputs/stage_a/<new-run>/cv --out outputs/stage_a/<new-run>/outer_free_hybrid
```

Each fold has five training animals, one distinct calibration animal, and one
held-out evaluation animal. The fixed 124-epoch budget comes from development
training; calibration/evaluation animal losses never select model weights.
The model-training protocol and every epoch are checkpointed. Keep the same
batching configuration when resuming a run.

The exact CV source used for this checkpoint is preserved as
`source_used/cv_training_source.py`. It can reproduce the original protocol in
a new directory. The current trainer adds explicit fold-group and tensor-shape
resume checks, preventing accidental broadcasting if batch configuration changes.
It also verifies completed exports without rewriting them. With the activated
environment and the same `PYTHONPATH`, inspect the completed run safely with:

```powershell
python code/stage_a_inner_cv.py --out outputs/stage_a/20260909_inner_retina_tier1/cv_seven_animals --heads 8 --epochs 124 --steps-per-epoch 48 --batch-folds 7 --device cpu
```

The outer-free control consumes only the learned ILM and IPL_INL endpoint
coordinates. Both endpoint models and new inner fractions exclude the animal
being evaluated. It is a disclosed hybrid control, not a claim that the old
classical endpoint finder ceased depending on PR_RPE.

## Create and inspect review packs

```powershell
python code/stage_a_inner_queue.py --checkpoint outputs/stage_a/20260908_v4_longtrain/dev_seed20260908/best.pt --constraints outputs/stage_a/20260909_inner_retina_tier1/constraints_training_only/constraints.json --decoder dp_project --scan-ids TS165_OS_2025-04-29_WT_s02_121711 TS325_OD_2026-05-26_6mo_s01_112940 --out outputs/stage_a/<new-run>/review_queue --device cpu
python code/eight_surface/label_gui.py outputs/stage_a/<new-run>/review_queue/packs
```

The delivered packs are already in `review_queue/packs/`. Opening them in the
GUI is a human-review step, not automatic acceptance. The builder writes no
labels and excludes previously reviewed B-scans. Priority is an experimental
uncertainty/run-length heuristic, kept separate from acquisition QC. A
per-volume entropy quantile does not guarantee accuracy or deployment coverage.

## Verification

Run each test module in a separate Python process. On this Windows environment,
loading torch and GUI/matplotlib OpenMP runtimes in one process can conflict.

```powershell
python code/test_stage_a_inner_retina.py
python code/test_stage_a_decoder.py
python code/test_stage_a_decoder_sparse.py
python code/test_stage_a_inner_training.py
python code/test_stage_a_inner_calibration.py
python code/test_stage_a_inner_queue.py
```

`stage_a_inner_verify.py --mode inputs|models|packs --out <run>` performs the
read-only input, checkpoint, and actual-GUI-reader checks in separate modes.
