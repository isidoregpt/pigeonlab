#!/usr/bin/env pwsh
# PigeonLab workstation installer for Windows.

$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot
$LogDir = Join-Path $Root "data\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$TranscriptPath = Join-Path $LogDir "install-$Stamp.log"
Start-Transcript -Path $TranscriptPath -Force | Out-Null

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "== $Message ==" -ForegroundColor Cyan
}

function Write-Ok([string]$Message) {
    Write-Host "  [OK] $Message" -ForegroundColor Green
}

function Write-Warn([string]$Message) {
    Write-Host "  [WARN] $Message" -ForegroundColor Yellow
}

function Write-Fail([string]$Message) {
    Write-Host "  [ERROR] $Message" -ForegroundColor Red
}

function Test-CommandExists([string]$Name) {
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Refresh-Path {
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machinePath;$userPath"
}

function Install-WinGetPackage([string]$Id, [string]$DisplayName) {
    if (-not (Test-CommandExists "winget")) {
        Write-Warn "WinGet is not available. Please install $DisplayName manually."
        return $false
    }
    Write-Host "  Installing $DisplayName with WinGet..."
    & winget install --id $Id --exact --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "WinGet could not install $DisplayName. It may already be installed or may require manual installation."
        return $false
    }
    Refresh-Path
    return $true
}

function Ensure-Command([string]$Command, [string]$PackageId, [string]$DisplayName) {
    if (Test-CommandExists $Command) {
        Write-Ok "$DisplayName found"
        return $true
    }
    Install-WinGetPackage -Id $PackageId -DisplayName $DisplayName | Out-Null
    Refresh-Path
    if (Test-CommandExists $Command) {
        Write-Ok "$DisplayName installed"
        return $true
    }
    Write-Fail "$DisplayName is still missing."
    return $false
}

function Test-Python312([string]$Exe, [string[]]$Args = @()) {
    & $Exe @Args -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)" *> $null
    return $LASTEXITCODE -eq 0
}

function Get-PythonCommand {
    if (Test-CommandExists "py") {
        & py -3.12 --version *> $null
        if ($LASTEXITCODE -eq 0) {
            return [pscustomobject]@{ Exe = "py"; Args = @("-3.12"); Display = "py -3.12" }
        }
    }
    if (Test-CommandExists "python") {
        if (Test-Python312 -Exe "python") {
            return [pscustomobject]@{ Exe = "python"; Args = @(); Display = "python" }
        }
    }
    return $null
}

function Test-IsWindows {
    return [System.Environment]::OSVersion.Platform -eq [System.PlatformID]::Win32NT
}

function Invoke-Python($PythonCmd, [string[]]$AdditionalArgs) {
    & $PythonCmd.Exe @($PythonCmd.Args) @AdditionalArgs
}

function Invoke-Checked([string]$Label, [scriptblock]$Command) {
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

function Write-WorkstationEnv {
    $EnvPath = Join-Path $Root ".env"
    if (Test-Path $EnvPath) {
        $BackupPath = Join-Path $LogDir ".env.backup-$Stamp"
        Copy-Item -LiteralPath $EnvPath -Destination $BackupPath -Force
        Write-Ok "Existing .env backed up to $BackupPath"
    }

    $content = @"
DATABASE_URL=data/pigeonlab.db
BACKEND_PORT=8000
FRONTEND_PORT=5173
CORS_ORIGINS=http://localhost:5173

PIGEONLAB_HARDWARE_PROFILE=threadripper_a6000
PIGEONLAB_LOG_LEVEL=DEBUG
PIGEONLAB_LOG_JSON=1
PIGEONLAB_LOG_MAX_BYTES=52428800
PIGEONLAB_LOG_BACKUPS=10
PIGEONLAB_UVICORN_WORKERS=1
PIGEONLAB_TORCH_DTYPE=auto
PIGEONLAB_OPENCV_THREADS=32
OMP_NUM_THREADS=32
MKL_NUM_THREADS=32

PIGEONLAB_SAM3_VERSION=sam3.1
PIGEONLAB_SAM3_MODEL_DIR=data/models/sam3.1
PIGEONLAB_SAM3_MAX_OBJECTS=32
PIGEONLAB_SAM3_MULTIPLEX_COUNT=32
PIGEONLAB_SAM3_COMPILE=1
PIGEONLAB_SAM3_WARM_UP=1
PIGEONLAB_SAM3_ASYNC_LOADING=1
PIGEONLAB_SAM3_USE_FA3=0
PIGEONLAB_SAM3_ENABLE_WINDOWS_PATCHES=1
PIGEONLAB_ALLOW_HF_DOWNLOAD=0

PIGEONLAB_VIDEO_INPUT_DIR=data/videos/inbox
PIGEONLAB_VIDEO_OUTPUT_DIR=data/videos/output
PIGEONLAB_VIDEO_ARCHIVE_DIR=data/videos/archive
PIGEONLAB_VIDEO_CHUNK_SECONDS=300
PIGEONLAB_FFMPEG_THREADS=32
PIGEONLAB_FFMPEG_USE_NVENC=1

PIGEONLAB_GEMMA_REVIEW_MODE=off
PIGEONLAB_GEMMA_MODEL=gemma4:e4b
PIGEONLAB_GEMMA_BASE_URL=http://localhost:11434
PIGEONLAB_GEMMA_SAMPLE_SECONDS=15
PIGEONLAB_GEMMA_MAX_FRAMES=20
PIGEONLAB_GEMMA_CONFIDENCE_THRESHOLD=0.65
"@
    Set-Content -LiteralPath $EnvPath -Value $content -Encoding UTF8
    Write-Ok "Workstation .env written"
}

try {
    Write-Host ""
    Write-Host "====================================" -ForegroundColor Cyan
    Write-Host " PigeonLab Workstation Installer" -ForegroundColor Cyan
    Write-Host " Threadripper + RTX A6000 profile" -ForegroundColor Cyan
    Write-Host "====================================" -ForegroundColor Cyan

    Write-Step "Creating folders and optimized .env"
    foreach ($path in @(
        "data",
        "data\logs",
        "data\videos\inbox",
        "data\videos\output",
        "data\videos\archive",
        "data\models\sam3.1",
        "data\frames"
    )) {
        New-Item -ItemType Directory -Force -Path (Join-Path $Root $path) | Out-Null
    }
    Write-WorkstationEnv

    Write-Step "Installing workstation prerequisites"
    Ensure-Command -Command "git" -PackageId "Git.Git" -DisplayName "Git" | Out-Null
    Ensure-Command -Command "node" -PackageId "OpenJS.NodeJS.LTS" -DisplayName "Node.js LTS" | Out-Null
    Ensure-Command -Command "ffmpeg" -PackageId "Gyan.FFmpeg" -DisplayName "FFmpeg" | Out-Null
    Ensure-Command -Command "ollama" -PackageId "Ollama.Ollama" -DisplayName "Ollama" | Out-Null

    $pythonCmd = Get-PythonCommand
    if ($null -eq $pythonCmd) {
        Install-WinGetPackage -Id "Python.Python.3.12" -DisplayName "Python 3.12" | Out-Null
        Refresh-Path
        $pythonCmd = Get-PythonCommand
    }
    if ($null -eq $pythonCmd) {
        throw "Python 3.12 was not found. Install Python 3.12 and rerun install.bat."
    }
    Write-Ok "Python command: $($pythonCmd.Display)"

    Write-Step "Creating Python virtual environment"
    $VenvPath = Join-Path $Root "backend\venv"
    $VenvPython = Join-Path $VenvPath "Scripts\python.exe"
    $NeedsVenvCreate = -not (Test-Path $VenvPath)
    if ((Test-Path $VenvPython) -and -not (Test-Python312 -Exe $VenvPython)) {
        $BackupVenvPath = Join-Path (Split-Path -Parent $VenvPath) "venv.backup-$Stamp"
        Move-Item -LiteralPath $VenvPath -Destination $BackupVenvPath -Force
        Write-Warn "Existing venv was not Python 3.12 and was moved to $BackupVenvPath"
        $NeedsVenvCreate = $true
    } elseif ((Test-Path $VenvPath) -and -not (Test-Path $VenvPython)) {
        $BackupVenvPath = Join-Path (Split-Path -Parent $VenvPath) "venv.backup-$Stamp"
        Move-Item -LiteralPath $VenvPath -Destination $BackupVenvPath -Force
        Write-Warn "Existing venv folder was incomplete and was moved to $BackupVenvPath"
        $NeedsVenvCreate = $true
    }
    if ($NeedsVenvCreate) {
        Invoke-Checked "Create Python virtual environment" {
            Invoke-Python -PythonCmd $pythonCmd -Args @("-m", "venv", $VenvPath)
        }
    }
    if (-not (Test-Path $VenvPython)) {
        throw "Virtual environment Python was not created at $VenvPython"
    }
    & $VenvPython -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)"
    if ($LASTEXITCODE -ne 0) {
        throw "Virtual environment must use Python 3.12 for the Windows SAM3.1 stack."
    }
    Write-Ok "Virtual environment ready"

    Write-Step "Installing Python GPU stack"
    Invoke-Checked "Upgrade pip tooling" {
        & $VenvPython -m pip install --upgrade pip "setuptools<81" wheel
    }
    $TorchIndexUrl = if ($env:PIGEONLAB_TORCH_INDEX_URL) { $env:PIGEONLAB_TORCH_INDEX_URL } else { "https://download.pytorch.org/whl/cu126" }
    Invoke-Checked "Install CUDA PyTorch stack" {
        & $VenvPython -m pip install --no-cache-dir --force-reinstall torch torchvision torchaudio --index-url $TorchIndexUrl
    }
    Invoke-Checked "Install backend requirements" {
        & $VenvPython -m pip install -r (Join-Path $Root "backend\requirements.txt")
    }
    Invoke-Checked "Install SAM3 package" {
        & $VenvPython -m pip install --upgrade "git+https://github.com/facebookresearch/sam3.git"
    }
    if (Test-IsWindows) {
        $TritonSpec = if ($env:PIGEONLAB_TRITON_WINDOWS_SPEC) { $env:PIGEONLAB_TRITON_WINDOWS_SPEC } else { "triton-windows" }
        Invoke-Checked "Install Triton for Windows" {
            & $VenvPython -m pip install --upgrade $TritonSpec
        }
    }
    Invoke-Checked "Align SAM3 Windows dependencies" {
        & $VenvPython -m pip install --upgrade "numpy>=1.26,<2" "opencv-python>=4.8.0,<4.11" "einops>=0.7.0" "psutil" "pycocotools>=2.0.11"
    }
    Invoke-Checked "Validate Python dependency graph" {
        & $VenvPython -m pip check
    }

    Write-Step "Installing frontend dependencies"
    Push-Location (Join-Path $Root "frontend")
    Invoke-Checked "Install frontend dependencies" {
        & npm install
    }
    Pop-Location

    Write-Step "Preparing Ollama Gemma model"
    if (Test-CommandExists "ollama") {
        $GemmaModel = if ($env:PIGEONLAB_GEMMA_MODEL) { $env:PIGEONLAB_GEMMA_MODEL } else { "gemma4:e4b" }
        & ollama pull $GemmaModel
        if ($LASTEXITCODE -ne 0) {
            Write-Warn "Ollama could not pull $GemmaModel. You can retry later with: ollama pull $GemmaModel"
        }
    }

    Write-Step "Optional SAM3.1 checkpoint download"
    Write-Host "  SAM3.1 is gated on Hugging Face. If you have a token, paste it now."
    Write-Host "  Press Enter to skip and download later from Settings/setup_check."
    $SecureToken = Read-Host "  Hugging Face token" -AsSecureString
    $TokenBstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureToken)
    $TokenPlain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($TokenBstr)
    if ($TokenPlain -and $TokenPlain.Trim().Length -gt 0) {
        $env:HF_TOKEN = $TokenPlain.Trim()
        Invoke-Checked "Install Hugging Face Hub client" {
            & $VenvPython -m pip install --upgrade huggingface_hub
        }
        Invoke-Checked "Download SAM3.1 checkpoint" {
            & $VenvPython (Join-Path $Root "backend\scripts\download_sam3.py") --version sam3.1
        }
        Remove-Item Env:\HF_TOKEN -ErrorAction SilentlyContinue
    } else {
        Write-Warn "Skipped SAM3.1 checkpoint download."
    }
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($TokenBstr)

    Write-Step "Running final setup check"
    & $VenvPython (Join-Path $Root "backend\scripts\setup_check.py")

    Write-Host ""
    Write-Host "====================================" -ForegroundColor Green
    Write-Host " PigeonLab install finished" -ForegroundColor Green
    Write-Host " Log: $TranscriptPath" -ForegroundColor Green
    Write-Host " Start app with: start.bat" -ForegroundColor Green
    Write-Host "====================================" -ForegroundColor Green
} catch {
    Write-Fail $_.Exception.Message
    Write-Host "Installer log: $TranscriptPath" -ForegroundColor Yellow
    throw
} finally {
    Stop-Transcript | Out-Null
}
