param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$galleryRoot = $PSScriptRoot
$galleryUrl = 'http://127.0.0.1:8803'
$galleryReady = $false
try {
    $galleryHealth = Invoke-RestMethod "$galleryUrl/health" -TimeoutSec 2
    $galleryReady = $galleryHealth.app -eq 'octa-cnv-v9-model3-gallery' -and $galleryHealth.root -eq $galleryRoot
} catch {}
if (-not $galleryReady) {
    if (-not (Test-Path -LiteralPath (Join-Path $galleryRoot 'FINAL_VERIFIED.json'))) { throw 'Model 3 verification is not complete. See progress.json.' }
    $galleryCommand = 'call "D:\Anaconda\Scripts\activate.bat" octa && python -B "' + (Join-Path $galleryRoot 'server.py') + '"'
    Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', $galleryCommand -WorkingDirectory $galleryRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $galleryRoot 'server.log') -RedirectStandardError (Join-Path $galleryRoot 'server-error.log')
    for ($galleryTry=0; $galleryTry -lt 40; $galleryTry++) {
        Start-Sleep -Milliseconds 500
        try {
            $galleryHealth = Invoke-RestMethod "$galleryUrl/health" -TimeoutSec 1
            if ($galleryHealth.app -eq 'octa-cnv-v9-model3-gallery' -and $galleryHealth.root -eq $galleryRoot) { $galleryReady=$true; break }
        } catch {}
    }
}
if (-not $galleryReady) { throw 'Could not start Model 3 gallery. See server-error.log.' }
if (-not $NoBrowser) { Start-Process $galleryUrl }
