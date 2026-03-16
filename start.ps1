#!/usr/bin/env pwsh
# PigeonLab Startup Script (PowerShell)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "  ===========================" -ForegroundColor Cyan
Write-Host "   PigeonLab Startup Script"   -ForegroundColor Cyan
Write-Host "  ===========================" -ForegroundColor Cyan
Write-Host ""

$Root = $PSScriptRoot

# -----------------------------------------------
# 1. Check Python
# -----------------------------------------------
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "[ERROR] Python is not installed or not in PATH." -ForegroundColor Red
    Write-Host "        Download from https://www.python.org/downloads/"
    exit 1
}
$pyVersion = & python --version 2>&1
Write-Host "  Found: $pyVersion"

# -----------------------------------------------
# 2. Check Node
# -----------------------------------------------
$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) {
    Write-Host "[ERROR] Node.js is not installed or not in PATH." -ForegroundColor Red
    Write-Host "        Download from https://nodejs.org/"
    exit 1
}
$nodeVersion = & node --version 2>&1
Write-Host "  Found: Node $nodeVersion"

# -----------------------------------------------
# 3. Create Python venv if needed
# -----------------------------------------------
$venvPath = Join-Path $Root "backend\venv"
if (-not (Test-Path $venvPath)) {
    Write-Host ""
    Write-Host "  Creating Python virtual environment..." -ForegroundColor Yellow
    & python -m venv $venvPath
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to create virtual environment." -ForegroundColor Red
        exit 1
    }
}

# -----------------------------------------------
# 4. Install Python dependencies
# -----------------------------------------------
Write-Host ""
Write-Host "  Installing Python dependencies..." -ForegroundColor Yellow

$activateScript = Join-Path $venvPath "Scripts\Activate.ps1"
if (-not (Test-Path $activateScript)) {
    # Linux/macOS fallback
    $activateScript = Join-Path $venvPath "bin/Activate.ps1"
}

& $activateScript
& pip install -r (Join-Path $Root "backend\requirements.txt") --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARNING] Some Python packages may have failed to install." -ForegroundColor Yellow
}

# -----------------------------------------------
# 5. Install Node dependencies if needed
# -----------------------------------------------
$nodeModules = Join-Path $Root "frontend\node_modules"
if (-not (Test-Path $nodeModules)) {
    Write-Host ""
    Write-Host "  Installing frontend dependencies..." -ForegroundColor Yellow
    Push-Location (Join-Path $Root "frontend")
    & npm install
    Pop-Location
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] npm install failed." -ForegroundColor Red
        exit 1
    }
}

# -----------------------------------------------
# 6. Start backend in new terminal
# -----------------------------------------------
Write-Host ""
Write-Host "  Starting FastAPI backend..." -ForegroundColor Green

$backendDir = Join-Path $Root "backend"
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$backendDir'; & '$activateScript'; python -m uvicorn main:app --reload --port 8000"
)

# -----------------------------------------------
# 7. Start frontend in new terminal
# -----------------------------------------------
Write-Host "  Starting Vite frontend..." -ForegroundColor Green

$frontendDir = Join-Path $Root "frontend"
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$frontendDir'; npm run dev"
)

# -----------------------------------------------
# 8. Done
# -----------------------------------------------
Write-Host ""
Write-Host "  ============================================" -ForegroundColor Cyan
Write-Host "   PigeonLab is starting..."                    -ForegroundColor Cyan
Write-Host ""                                               -ForegroundColor Cyan
Write-Host "   Backend:  http://localhost:8000"              -ForegroundColor White
Write-Host "   Frontend: http://localhost:5173"              -ForegroundColor White
Write-Host "   API docs: http://localhost:8000/docs"         -ForegroundColor White
Write-Host "  ============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Tip: Run 'python backend\seed_data.py' to load sample data." -ForegroundColor DarkGray
Write-Host ""
