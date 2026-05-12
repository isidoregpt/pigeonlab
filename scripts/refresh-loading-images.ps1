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
        $encodedName = [System.Uri]::EscapeDataString($_.Name)
        [pscustomobject]@{
            src = "/loading/$encodedName"
        }
    }

$manifest = [pscustomobject]@{
    startupId = Get-Date -Format "yyyyMMdd-HHmmssffff"
    generatedAt = (Get-Date).ToString("o")
    durationSecondsPerImage = 5.2
    maxDurationSeconds = 8
    images = @($images)
}

$manifestPath = Join-Path $LoadingDir "manifest.json"
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

Write-Host "Loading manifest refreshed: $($images.Count) image(s)"
