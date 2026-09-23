param([string]$Group = '')
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$repo = (Resolve-Path (Join-Path $root '..\..')).Path
$url = 'http://127.0.0.1:8774'
try { $health = Invoke-RestMethod "$url/health" -TimeoutSec 2 } catch { $health = $null }
if ($health -and $health.root -ne $root) { throw 'Port 8774 belongs to another reviewer. Preserve that server and choose another port.' }
if (-not $health) {
    $serverScript = Join-Path $root 'serve.ps1'
    Start-Process powershell -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"'+$serverScript+'"')) -WorkingDirectory $repo -WindowStyle Hidden -RedirectStandardOutput (Join-Path $root 'server.log') -RedirectStandardError (Join-Path $root 'server-error.log')
    for ($attempt=0; $attempt -lt 40; $attempt++) {
        Start-Sleep -Milliseconds 250
        try { $health = Invoke-RestMethod "$url/health" -TimeoutSec 1; break } catch {}
    }
    if (-not $health) { throw 'Reviewer did not start. Read server-error.log.' }
}
if ($Group -match '^TS[0-9]+_(OD|OS)$') { $url += '/'+$Group+'/index.html' }
Start-Process $url
