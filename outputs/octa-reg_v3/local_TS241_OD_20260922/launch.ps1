$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$url = 'http://127.0.0.1:8775'
try { $health = Invoke-RestMethod "$url/health" -TimeoutSec 2 } catch { $health = $null }
if ($health -and $health.root -ne $root) { throw 'Port 8775 belongs to another reviewer.' }
if (-not $health) {
    Start-Process powershell -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"'+(Join-Path $root 'serve.ps1')+'"')) -WindowStyle Hidden -RedirectStandardOutput (Join-Path $root 'server.log') -RedirectStandardError (Join-Path $root 'server-error.log')
    for ($attempt=0; $attempt -lt 40; $attempt++) {
        Start-Sleep -Milliseconds 250
        try { $health = Invoke-RestMethod "$url/health" -TimeoutSec 1; break } catch {}
    }
    if (-not $health) { throw 'Reviewer did not start. See server-error.log.' }
}
Start-Process "$url/TS241_OD/index.html"
