param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$assessmentUrl = 'http://127.0.0.1:8805'
$assessmentReady = $false
try {
    $assessmentHealth = Invoke-RestMethod "$assessmentUrl/health" -TimeoutSec 2
    if ($assessmentHealth.app -ne 'cnv-final-assessment' -or $assessmentHealth.root -ne $PSScriptRoot) { throw 'Port 8805 belongs to another application.' }
    $assessmentReady = $true
} catch {}
if (-not $assessmentReady) {
    if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'gallery/data.json'))) { throw 'Build the assessment snapshot first.' }
    $assessmentCommand = 'call "D:\Anaconda\Scripts\activate.bat" octa && python -B "' + (Join-Path $PSScriptRoot 'server.py') + '"'
    Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', $assessmentCommand -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot 'server.log') -RedirectStandardError (Join-Path $PSScriptRoot 'server-error.log')
    for ($assessmentTry=0; $assessmentTry -lt 40; $assessmentTry++) {
        Start-Sleep -Milliseconds 500
        try {
            $assessmentHealth = Invoke-RestMethod "$assessmentUrl/health" -TimeoutSec 1
            if ($assessmentHealth.app -eq 'cnv-final-assessment' -and $assessmentHealth.root -eq $PSScriptRoot) { $assessmentReady=$true; break }
        } catch {}
    }
}
if (-not $assessmentReady) { throw 'Could not start assessment. See server-error.log.' }
if (-not $NoBrowser) { Start-Process $assessmentUrl }
