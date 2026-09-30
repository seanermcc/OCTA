$ErrorActionPreference='Stop'
$compareRoot=[IO.Path]::GetFullPath($env:OCTA_COMPARE_ROOT)
$compareScript=Join-Path $compareRoot 'code\reviewer_compare\serve.py'
$compareArgs='/d /c "call "'+$env:OCTA_COMPARE_ACTIVATE+'" octa && set PYTHONDONTWRITEBYTECODE=1&& python "'+$compareScript+'" --port 8818 --open"'
Start-Process -FilePath cmd.exe -ArgumentList $compareArgs -WorkingDirectory $compareRoot -WindowStyle Hidden
