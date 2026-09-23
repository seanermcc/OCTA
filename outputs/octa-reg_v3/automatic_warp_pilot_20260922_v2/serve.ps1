. D:/Anaconda/shell/condabin/conda-hook.ps1
conda activate octa
Set-Location $PSScriptRoot
python -m http.server 8794 --bind 127.0.0.1
