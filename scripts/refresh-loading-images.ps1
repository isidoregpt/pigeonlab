#!/usr/bin/env pwsh
# Build the frontend loading-image manifest from files in frontend/public/loading.

[CmdletBinding()]
param(
    [string]$ProjectRoot = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = Split-Path -Parent $PSScriptRoot
}

$LoadingDir = Join-Path $ProjectRoot "frontend\public\loading"
New-Item -ItemType Directory -Force -Path $LoadingDir | Out-Null

$extensions = @("*.png", "*.jpg", "*.jpeg", "*.webp", "*.gif")
$files = foreach ($extension in $extensions) {
    Get-ChildItem -LiteralPath $LoadingDir -Filter $extension -File -ErrorAction SilentlyContinue
}

$images = $files |
    Sort-Object Name |
    ForEach-Object {
        $name = [System.IO.Path]::GetFileNameWithoutExtension($_.Name)
        $caption = ($name -replace "[-_]+", " ").Trim()
        $encodedName = [System.Uri]::EscapeDataString($_.Name)
        [pscustomobject]@{
            src = "/loading/$encodedName"
            caption = $caption
        }
    }

$manifest = [pscustomobject]@{
    durationSecondsPerImage = 4.5
    maxDurationSeconds = 24
    images = @($images)
}

$manifestPath = Join-Path $LoadingDir "manifest.json"
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

Write-Host "Loading manifest refreshed: $($images.Count) image(s)"
