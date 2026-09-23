. D:\Anaconda\shell\condabin\conda-hook.ps1
conda activate octa
Set-Location ($PSScriptRoot + '\..\..\..')
$env:PYTHONPATH = "$PWD\code"
python -m octa_reg_v2.review_server
