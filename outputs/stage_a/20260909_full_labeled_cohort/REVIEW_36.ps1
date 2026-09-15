$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath 'G:/OCT_TreeShrew/octa'
. 'D:/Anaconda/shell/condabin/conda-hook.ps1'
conda activate octa
if ($LASTEXITCODE -ne 0) { throw 'Could not activate octa environment' }
python code/eight_surface/label_gui.py outputs/stage_a/20260909_full_labeled_cohort/review_queue/packs --labels outputs/stage_a/20260909_full_labeled_cohort/manual_review_36/labels --window-title 'OCT - 36 candidate review - all eight boundaries' *> outputs/stage_a/20260909_full_labeled_cohort/review_36_gui.log
