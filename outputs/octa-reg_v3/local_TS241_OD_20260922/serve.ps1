$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
. D:\Anaconda\shell\condabin\conda-hook.ps1
conda activate octa
$env:PYTHONPATH = "$PWD\code"
python -m octa_reg_v3.review_server --directory $PSScriptRoot --port 8775
