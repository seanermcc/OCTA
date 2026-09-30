$ErrorActionPreference = 'Stop'
$releaseRoot = 'F:\OCT_TreeShrew\octa\outputs\octo-vessel_onh_v2'
$stagingRoot = 'D:\Projects\octa\outputs\vessel_manual_gallery_preview'
$sourceRoot = 'D:\Projects\octa\outputs\octo-vessel_onh_v2'
$manifest = Get-Content -LiteralPath (Join-Path $stagingRoot 'manual_gallery_manifest.json') -Raw | ConvertFrom-Json
foreach ($annotation in $manifest.annotations) {
    if ((Get-FileHash -LiteralPath $annotation.path -Algorithm SHA256).Hash.ToLower() -ne $annotation.sha256) {
        throw "Annotation changed since build: $($annotation.path)"
    }
}
$backup = Join-Path $releaseRoot 'index_original_20260915.html.bak'
if (Test-Path -LiteralPath $backup) {
    if ((Get-FileHash -LiteralPath $backup).Hash.ToLower() -ne $manifest.original_index_sha256) {
        throw 'Existing archive has a different source hash.'
    }
} else {
    if ((Get-FileHash -LiteralPath (Join-Path $releaseRoot 'index.html')).Hash.ToLower() -ne $manifest.original_index_sha256) {
        throw 'Original HTML changed since build.'
    }
    Copy-Item -LiteralPath (Join-Path $releaseRoot 'index.html') -Destination $backup
}
$assetDestination = Join-Path $releaseRoot 'manual_gallery_assets'
New-Item -ItemType Directory -Path $assetDestination -Force | Out-Null
Get-ChildItem -LiteralPath (Join-Path $stagingRoot 'manual_gallery_assets') -File | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $assetDestination $_.Name)
}
$stagedFiles = @('manual-gallery-data.js', 'manual_gallery_manifest.json', 'index_archived_20260915.html', 'v1_manual_v2.html')
$sourceFiles = @('gallery_template.html', 'manual_gallery_template.html', 'build_manual_gallery.py', 'check_manual_gallery.cjs', 'MANUAL_GALLERY.md', 'OPEN_GALLERY.cmd')
foreach ($name in $stagedFiles) { Copy-Item -LiteralPath (Join-Path $stagingRoot $name) -Destination (Join-Path $releaseRoot $name) }
foreach ($name in $sourceFiles) { Copy-Item -LiteralPath (Join-Path $sourceRoot $name) -Destination (Join-Path $releaseRoot $name) }
# Redirect the original entry point only after all required new assets are present.
Copy-Item -LiteralPath (Join-Path $stagingRoot 'index.html') -Destination (Join-Path $releaseRoot 'index.html')
foreach ($name in ($stagedFiles + @('index.html'))) {
    if ((Get-FileHash -LiteralPath (Join-Path $stagingRoot $name)).Hash -ne (Get-FileHash -LiteralPath (Join-Path $releaseRoot $name)).Hash) { throw "Copy mismatch: $name" }
}
foreach ($annotation in $manifest.annotations) {
    if ((Get-FileHash -LiteralPath $annotation.path).Hash.ToLower() -ne $annotation.sha256) { throw 'Annotation changed during publication.' }
}
Write-Output "Published $releaseRoot\v1_manual_v2.html; original archived; 58 annotation hashes unchanged."
