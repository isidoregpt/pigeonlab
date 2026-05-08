#!/usr/bin/env pwsh
# Collect a redacted troubleshooting bundle for PigeonLab.

$ErrorActionPreference = "Continue"
$Root = $PSScriptRoot
$LogDir = Join-Path $Root "data\logs"
$DiagRoot = Join-Path $LogDir "diagnostics"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$OutDir = Join-Path $DiagRoot "pigeonlab-diagnostics-$Stamp"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

function Save-CommandOutput([string]$Name, [scriptblock]$Command) {
    $Path = Join-Path $OutDir "$Name.txt"
    try {
        & $Command *> $Path
    } catch {
        "FAILED: $($_.Exception.Message)" | Out-File -FilePath $Path -Encoding UTF8
    }
}

function Redact-Line([string]$Line) {
    if ($Line -match "(?i)(token|secret|password|api[_-]?key|hf_)") {
        $parts = $Line.Split("=", 2)
        if ($parts.Length -eq 2) {
            return "$($parts[0])=<redacted>"
        }
        return "<redacted>"
    }
    return $Line
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

Save-CommandOutput "systeminfo" { systeminfo }
Save-CommandOutput "nvidia-smi" { nvidia-smi }
Save-CommandOutput "ffmpeg-version" { ffmpeg -version }
Save-CommandOutput "ollama-list" { ollama list }
Save-CommandOutput "python-version" { python --version }
Save-CommandOutput "node-version" { node --version }
Save-CommandOutput "npm-version" { npm --version }
Save-CommandOutput "git-status" { git status --short }

$VenvPython = Join-Path $Root "backend\venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    Save-CommandOutput "setup-check" { & $VenvPython (Join-Path $Root "backend\scripts\setup_check.py") }
    Save-CommandOutput "pip-freeze" { & $VenvPython -m pip freeze }
    Save-CommandOutput "pip-check" { & $VenvPython -m pip check }
} else {
    Save-CommandOutput "setup-check" { python (Join-Path $Root "backend\scripts\setup_check.py") }
}

if (Test-Path (Join-Path $Root ".env")) {
    Get-Content -LiteralPath (Join-Path $Root ".env") |
        ForEach-Object { Redact-Line $_ } |
        Out-File -FilePath (Join-Path $OutDir "env-redacted.txt") -Encoding UTF8
}

if (Test-Path $LogDir) {
    Get-ChildItem -LiteralPath $LogDir -File |
        Where-Object { $_.Name -match "pigeonlab|install|backend|frontend|startup" } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 20 |
        Copy-Item -Destination $OutDir -Force
}

$ZipPath = Join-Path $DiagRoot "pigeonlab-diagnostics-$Stamp.zip"
Compress-Archive -Path (Join-Path $OutDir "*") -DestinationPath $ZipPath -Force

Write-Host ""
Write-Host "Diagnostics bundle created:" -ForegroundColor Green
Write-Host $ZipPath -ForegroundColor White
