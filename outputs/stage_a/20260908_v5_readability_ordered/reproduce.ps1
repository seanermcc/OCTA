# Command record. Do not run prepare/train/evaluate over completed artifacts.
# For a new experiment, change the package RUN root and guard output root,
# then save a new prespecified plan. Do not modify the frozen DATA root.
$ErrorActionPreference = 'Stop'
Set-Location 'G:/OCT_TreeShrew/octa'
. 'D:/Anaconda/shell/condabin/conda-hook.ps1'
conda activate octa
$env:PYTHONPATH = 'G:/OCT_TreeShrew/octa/code'
$env:PYTHONDONTWRITEBYTECODE = '1'
$taskRoot = 'outputs/stage_a/20260908_v5_readability_ordered'
$env:MPLCONFIGDIR = "G:/OCT_TreeShrew/octa/$taskRoot/mpl"
$taskAdapter = "$taskRoot/run_task.py"
function Invoke-Recorded {
    param([string]$Name,[string[]]$TaskArgs)
    python $taskAdapter @TaskArgs *> "$taskRoot/logs/$Name.log"
    if ($LASTEXITCODE -ne 0) { throw "$Name failed: inspect its log" }
}
Invoke-Recorded prepare @('module','stage_a_readability_ordered.experiment','prepare')
Invoke-Recorded test_new @('tests','stage_a_readability_ordered.test_readability_ordered')
Invoke-Recorded test_existing @('tests','stage_a.test_stage_a')
Invoke-Recorded train @('module','stage_a_readability_ordered.experiment','train')
Invoke-Recorded evaluate @('module','stage_a_readability_ordered.experiment','evaluate')
Invoke-Recorded paired @('module','stage_a_readability_ordered.paired')
Invoke-Recorded review @('module','stage_a_readability_ordered.review')
Invoke-Recorded software_verify @('module','stage_a_readability_ordered.verify')
Invoke-Recorded report @('module','stage_a_readability_ordered.report')
Invoke-Recorded verify @('module','stage_a_readability_ordered.experiment','verify')
