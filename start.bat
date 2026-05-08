@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
if %errorlevel% neq 0 (
    echo.
    echo PigeonLab failed to start. Check data\logs\startup-*.log for details.
    pause
    exit /b %errorlevel%
)
endlocal
