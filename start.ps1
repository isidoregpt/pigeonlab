#!/usr/bin/env pwsh
# PigeonLab startup script.

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$LogDir = Join-Path $Root "data\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$StartupLog = Join-Path $LogDir "startup-$Stamp.log"

function Write-Startup([string]$Message) {
    $line = "$(Get-Date -Format o) $Message"
    $line | Tee-Object -FilePath $StartupLog -Append
}

function Import-DotEnv([string]$Path) {
    if (-not (Test-Path $Path)) {
        return
    }
    Get-Content -LiteralPath $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            return
        }
        $key, $value = $line.Split("=", 2)
        $key = $key.Trim()
        $value = $value.Trim().Trim('"').Trim("'")
        if ($key) {
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
}

Write-Host ""
Write-Host "===========================" -ForegroundColor Cyan
Write-Host " PigeonLab Startup" -ForegroundColor Cyan
Write-Host "===========================" -ForegroundColor Cyan
Write-Host ""

Import-DotEnv (Join-Path $Root ".env")
Write-Startup "Loaded .env and starting PigeonLab"

$LoadingManifestScript = Join-Path $Root "scripts\refresh-loading-images.ps1"
if (Test-Path $LoadingManifestScript) {
    try {
        & $LoadingManifestScript -ProjectRoot $Root *> $null
        Write-Startup "Refreshed loading image manifest"
    } catch {
        Write-Startup "Loading image manifest refresh failed: $($_.Exception.Message)"
    }
}

$VenvPython = Join-Path $Root "backend\venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "[ERROR] PigeonLab is not installed yet." -ForegroundColor Red
    Write-Host "Run install.bat first, then run start.bat again."
    Write-Startup "Missing virtual environment at $VenvPython"
    exit 1
}

if (-not (Test-Path (Join-Path $Root "frontend\node_modules"))) {
    Write-Host "[ERROR] Frontend dependencies are missing." -ForegroundColor Red
    Write-Host "Run install.bat first, then run start.bat again."
    Write-Startup "Missing frontend node_modules"
    exit 1
}

$BackendPort = if ($env:BACKEND_PORT) { $env:BACKEND_PORT } else { "8000" }
$FrontendPort = if ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { "5173" }
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$BackendLog = Join-Path $LogDir "backend-$Stamp.log"
$FrontendLog = Join-Path $LogDir "frontend-$Stamp.log"

$workerCount = if ($env:PIGEONLAB_UVICORN_WORKERS) { [int]$env:PIGEONLAB_UVICORN_WORKERS } else { 1 }
if ($workerCount -ne 1) {
    Write-Startup "For GPU model safety, overriding PIGEONLAB_UVICORN_WORKERS=$workerCount to 1"
    $workerCount = 1
}

Write-Startup "Backend log: $BackendLog"
Write-Startup "Frontend log: $FrontendLog"

$BackendCommand = @"
Set-Location '$BackendDir'
`$env:PYTHONUNBUFFERED='1'
& '$VenvPython' -m uvicorn main:app --host 127.0.0.1 --port $BackendPort --workers $workerCount *> '$BackendLog'
"@

$FrontendCommand = @"
Set-Location '$FrontendDir'
npm run dev -- --host 127.0.0.1 --port $FrontendPort *> '$FrontendLog'
"@

Start-Process powershell.exe -WindowStyle Hidden -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-Command",
    $BackendCommand
) | Out-Null

Start-Process powershell.exe -WindowStyle Hidden -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-Command",
    $FrontendCommand
) | Out-Null

Write-Host "PigeonLab is starting." -ForegroundColor Green
Write-Host "Frontend: http://localhost:$FrontendPort" -ForegroundColor White
Write-Host "Backend:  http://localhost:$BackendPort" -ForegroundColor White
Write-Host "Logs:     $LogDir" -ForegroundColor White
Write-Host ""
Write-Host "If something goes wrong, run diagnostics.bat and share the generated zip." -ForegroundColor DarkGray
Write-Startup "Startup commands launched"
