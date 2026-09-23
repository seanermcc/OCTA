param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$galleryRoot = $PSScriptRoot
$galleryUrl = 'http://127.0.0.1:8799'
$galleryReady = $false
try {
  $galleryHealth = Invoke-RestMethod "$galleryUrl/health" -TimeoutSec 2
  $galleryReady = $galleryHealth.app -eq 'octa-cnv-v9-gallery' -and $galleryHealth.root -eq $galleryRoot
} catch {}
if (-not $galleryReady) {
  if (-not (Test-Path -LiteralPath (Join-Path $galleryRoot 'gallery/data.json'))) { throw 'The gallery is not complete. Check progress.json and compute_batch4.log.' }
  $galleryCommand = 'call "D:\Anaconda\Scripts\activate.bat" octa && python -B "' + (Join-Path $galleryRoot 'server.py') + '"'
  Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', $galleryCommand -WorkingDirectory $galleryRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $galleryRoot 'server.log') -RedirectStandardError (Join-Path $galleryRoot 'server-error.log')
  for ($galleryTry=0; $galleryTry -lt 40; $galleryTry++) {
    Start-Sleep -Milliseconds 500
    try {
      $galleryHealth = Invoke-RestMethod "$galleryUrl/health" -TimeoutSec 1
      if ($galleryHealth.app -eq 'octa-cnv-v9-gallery' -and $galleryHealth.root -eq $galleryRoot) { $galleryReady=$true; break }
    } catch {}
  }
}
if (-not $galleryReady) { throw 'Could not start the gallery. See server-error.log.' }
if (-not $NoBrowser) { Start-Process $galleryUrl }
