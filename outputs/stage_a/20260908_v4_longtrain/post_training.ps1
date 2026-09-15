$ErrorActionPreference = 'Stop'
Set-Location 'G:/OCT_TreeShrew/octa'
. 'D:/Anaconda/shell/condabin/conda-hook.ps1'
conda activate octa
$env:PYTHONPATH = 'G:/OCT_TreeShrew/octa/code'
$env:PYTHONDONTWRITEBYTECODE = '1'
$taskRoot = 'outputs/stage_a/20260908_v4_longtrain'
$taskRun = "$taskRoot/dev_seed20260908"
$taskAdapter = "$taskRoot/run_task.py"
function Invoke-Logged {
    param([string]$LogName, [string[]]$TaskArgs)
    $ErrorActionPreference = 'Continue'
    python $taskAdapter @TaskArgs *> "$taskRoot/logs/$LogName.log"
    $taskExit = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    if ($taskExit -ne 0) {
        Get-Content "$taskRoot/logs/$LogName.log" -Tail 20
        throw "$LogName failed with exit code $taskExit"
    }
    Write-Output "$LogName complete"
}
Invoke-Logged 'training_summary_200' @('script', "$taskRoot/summarize_training.py")
$taskDecision = Get-Content "$taskRun/extension_decision.json" -Raw | ConvertFrom-Json
if ($taskDecision.extend_to_400) {
    Invoke-Logged 'train_400' @('module', 'stage_a.train', '--data', 'outputs/stage_a/20260908_v2', '--out', $taskRun, '--epochs', '400', '--steps-per-epoch', '48', '--base', '8', '--lr', '0.0003', '--region-weight', '0.1', '--seed', '20260908', '--device', 'cuda', '--resume', "$taskRun/last.pt")
    Invoke-Logged 'training_summary_400' @('script', "$taskRoot/summarize_training.py")
}
Invoke-Logged 'model_validation' @('module', 'stage_a.evaluate', '--split', 'validation', '--predictor', 'model', '--checkpoint', "$taskRun/best.pt", '--out', "$taskRun/eval_validation", '--device', 'cuda')
Invoke-Logged 'comparison_validation' @('script', 'code/stage_a_compare.py', '--split', 'validation', '--evals', "unet_long=$taskRun/eval_validation", 'unet_40=outputs/stage_a/20260908_v2/dev_seed20260908/eval_validation', "stored_auto=$taskRoot/baseline_validation", "classical_v2=$taskRoot/v2_validation", '--out', "$taskRoot/comparison_validation")
Invoke-Logged 'review_validation' @('script', 'code/stage_a_review.py', '--split', 'validation', '--eval', "$taskRun/eval_validation", '--out', "$taskRun/review_validation", '--worst', '4')
Invoke-Logged 'volume_TS165' @('module', 'stage_a.inference', '--checkpoint', "$taskRun/best.pt", '--scan-id', 'TS165_OS_2025-04-29_WT_s02_121711', '--out', "$taskRun/volume_TS165", '--device', 'cuda')
Invoke-Logged 'model_train_eval' @('module', 'stage_a.evaluate', '--split', 'train', '--predictor', 'model', '--checkpoint', "$taskRun/best.pt", '--out', "$taskRoot/eval_train", '--device', 'cuda')
Invoke-Logged 'readability_features' @('script', 'code/stage_a_readability.py', 'features', '--eval-train', "$taskRoot/eval_train", '--eval-val', "$taskRun/eval_validation", '--out', $taskRoot)
Invoke-Logged 'readability_compare' @('script', 'code/stage_a_readability.py', 'compare', '--out', $taskRoot)
Invoke-Logged 'measurement_overlays' @('script', 'code/stage_a_readability.py', 'display', '--split', 'validation', '--eval', "$taskRun/eval_validation", '--out', $taskRoot)
Invoke-Logged 'analysis_results' @('script', "$taskRoot/analyze_results.py")
Invoke-Logged 'tests_final' @('tests', 'after')
Invoke-Logged 'report_final' @('report', 'after')
Invoke-Logged 'report_tables' @('script', "$taskRoot/make_report_tables.py")
Invoke-Logged 'completion_verification' @('script', "$taskRoot/verify_completion.py")
