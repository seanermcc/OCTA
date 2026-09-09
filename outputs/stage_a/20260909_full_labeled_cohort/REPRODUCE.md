# Reproduce the full-cohort continuation

The user explicitly authorized the complete labeled cohort. The former test
animals are available in this new development dataset; no untouched final-test
estimate is claimed. Only manual boundary positions supply targets. Human label
files are never written by these scripts.

Activate the environment first:

```powershell
. 'D:/Anaconda/shell/condabin/conda-hook.ps1'
conda activate octa
$env:PYTHONPATH = 'G:/OCT_TreeShrew/octa/code;G:/OCT_TreeShrew/octa/outputs/stage_a/20260909_inner_retina_tier1/dependencies'
```

Use a new output directory for a new dataset or experiment. The following is the
delivered run's command record; existing completed evaluations should not be
overwritten. Each Python command is its own process because torch and the
GUI/matplotlib OpenMP runtimes can conflict when loaded together on this machine.

## Freeze the manual evidence

```powershell
python code/stage_a_full_cohort.py --out outputs/stage_a/20260909_full_labeled_cohort/data
python code/stage_a_inner_retina_audit.py --data outputs/stage_a/20260909_full_labeled_cohort/data --out outputs/stage_a/20260909_full_labeled_cohort/prerequisites
```

The snapshot reuses verified source image geometry and writes new derived targets
and caches. It preserves the original remote/control scope as a sensitivity mask
while including every visible, supported manual annotation. It contains 102
corrected B-scans and 59 rejected decisions. The historical 101-label subset is
reported separately from the newer annotation with recorded local strokes.

## Train and checkpoint all required models

```powershell
python code/stage_a_inner_cv.py --data outputs/stage_a/20260909_full_labeled_cohort/data --out outputs/stage_a/20260909_full_labeled_cohort/cv_full_cohort --heads 8 --epochs 124 --steps-per-epoch 48 --batch-folds 9 --precision bfloat16 --include-all-labels-model --preload-samples --fast-kernels --device cuda
```

The same command resumes the exact recorded protocol. A completed run is verified
without rewriting exports. Partial resumes reject changed data, source, batching,
or tensor shapes. Nine networks train independently on seven animals each, with
one distinct calibrator and one evaluated animal excluded. The all-label model
then trains separately on all nine animals. It never supplies an out-of-sample
accuracy prediction. The exact training source is in `source_used/`.

BF16 convolution with an FP32 objective/optimizer reduces memory use. Faster CUDA
kernels are permitted: checkpoint reproduction is controlled, but bitwise equality
across fresh runs is not promised. Brief ten-model and deterministic nine-model
performance probes were discarded and are not the delivered weights.

## Compare decoders and calibrate uncertainty

```powershell
python code/stage_a_inner_calibrate.py --data outputs/stage_a/20260909_full_labeled_cohort/data --models outputs/stage_a/20260909_full_labeled_cohort/cv_full_cohort --decoder dp_project --out outputs/stage_a/20260909_full_labeled_cohort/calibration_dp --device cuda
python code/stage_a_inner_calibrate.py --data outputs/stage_a/20260909_full_labeled_cohort/data --models outputs/stage_a/20260909_full_labeled_cohort/cv_full_cohort --decoder soft --out outputs/stage_a/20260909_full_labeled_cohort/calibration_soft --device cuda
python code/stage_a_full_cohort_evaluate.py --data outputs/stage_a/20260909_full_labeled_cohort/data --calibrations soft=outputs/stage_a/20260909_full_labeled_cohort/calibration_soft dp_project=outputs/stage_a/20260909_full_labeled_cohort/calibration_dp --out outputs/stage_a/20260909_full_labeled_cohort/held_animal_comparison
python code/stage_a_inner_calibration_plot.py --calibration outputs/stage_a/20260909_full_labeled_cohort/calibration_dp
python code/stage_a_inner_calibration_plot.py --calibration outputs/stage_a/20260909_full_labeled_cohort/calibration_soft
```

Every threshold comes from a different animal than the one being evaluated.
The raw comparison includes full-manual and original-scope sensitivities,
per-animal rows, and with/without-b0510 tables. It does not use the all-label model.
The previous four-head and joint graph-cut comparisons remain historical
experiments; this continuation uses their selected eight-head architecture and
cheap ordered-DP control.

## Classical controls and descriptive model checks

```powershell
python code/auto_seg_8layer_v2/eval_variants.py --data outputs/stage_a/20260909_full_labeled_cohort/data --inner-retina --loao --out outputs/stage_a/20260909_full_labeled_cohort/classical_loao
python code/auto_seg_8layer_v2/eval_variants.py --data outputs/stage_a/20260909_full_labeled_cohort/data --inner-retina --loao --inner-anchor-models outputs/stage_a/20260909_full_labeled_cohort/cv_full_cohort --out outputs/stage_a/20260909_full_labeled_cohort/outer_free_hybrid_loao
python code/stage_a_full_cohort_evaluate.py --data outputs/stage_a/20260909_full_labeled_cohort/data --checkpoint outputs/stage_a/20260908_v4_longtrain/dev_seed20260908/best.pt --out outputs/stage_a/20260909_full_labeled_cohort/original_v4_full_cohort --device cpu
python code/stage_a_full_cohort_evaluate.py --data outputs/stage_a/20260909_full_labeled_cohort/data --fit-checkpoint outputs/stage_a/20260909_full_labeled_cohort/cv_full_cohort/ALL_LABELLED/last.pt --out outputs/stage_a/20260909_full_labeled_cohort/all_label_fit_diagnostic --device cpu
```

The old-v4 comparator has mixed historical train/validation membership and is
stratified accordingly. The ALL_LABELLED check is strictly an in-sample fit
diagnostic. The hybrid consumes only learned ILM/IPL_INL coordinates; it does not
refit the classical IPL_INL prior. N=3 and attraction 0.05 remain unchanged.

## Full-volume experimental outputs and GUI packs

```powershell
python code/stage_a_decoder.py fit --data outputs/stage_a/20260909_full_labeled_cohort/data --animals TS165 TS169 TS241 TS247 TS250 TS267 TS283 TS305 TS325 --out outputs/stage_a/20260909_full_labeled_cohort/all_label_constraints
python code/stage_a_inner_queue.py --data outputs/stage_a/20260909_full_labeled_cohort/data --checkpoint outputs/stage_a/20260909_full_labeled_cohort/cv_full_cohort/ALL_LABELLED/last.pt --constraints outputs/stage_a/20260909_full_labeled_cohort/all_label_constraints/constraints.json --decoder dp_project --scan-ids TS165_OS_2025-04-29_WT_s02_121711 TS247_OD_2024-11-06_D21_s03_104157 TS283_OD_2025-01-29_D7_s02_123712 TS325_OD_2026-05-26_6mo_s01_112940 --out outputs/stage_a/20260909_full_labeled_cohort/review_queue --device cuda
python code/stage_a_inner_queue_preview.py --queue outputs/stage_a/20260909_full_labeled_cohort/review_queue
python code/eight_surface/label_gui.py outputs/stage_a/20260909_full_labeled_cohort/review_queue/packs
```

The queue covers four complete volumes and uses the original remote/control
volume masks, per-volume entropy quantiles for review triage, and separate
acquisition-QC fields. Shadowed thickness is NaN; unsupported layers are explicitly
unreliable. The final GUI command is for human review, not automatic acceptance.

## Verify and report

```powershell
python code/test_stage_a_full_cohort.py
python code/test_stage_a_inner_training.py
python code/stage_a_full_cohort_verify.py --out outputs/stage_a/20260909_full_labeled_cohort --mode inputs
python code/stage_a_full_cohort_verify.py --out outputs/stage_a/20260909_full_labeled_cohort --mode models
python code/stage_a_full_cohort_verify.py --out outputs/stage_a/20260909_full_labeled_cohort --mode packs
python code/stage_a_full_cohort_verify.py --out outputs/stage_a/20260909_full_labeled_cohort --mode complete
python code/stage_a_full_cohort_report.py --out outputs/stage_a/20260909_full_labeled_cohort
python code/stage_a_full_cohort_checkpoint.py --out outputs/stage_a/20260909_full_labeled_cohort
```

The final packaging command requires seven passing test-module logs (33 checks)
under `test_logs/`, the completed reports, and verification results. It freezes
source and artifact hashes, writes the three phase reports and `START_HERE.md`,
and refuses to replace a differing source snapshot. The test modules are
`test_stage_a_inner_retina`, `test_stage_a_decoder`, `test_stage_a_decoder_sparse`,
`test_stage_a_inner_training`, `test_stage_a_inner_calibration`,
`test_stage_a_inner_queue`, and `test_stage_a_full_cohort`. Run each in a separate
activated Python process and save its output, as in the delivered `test_logs/`.
