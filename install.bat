@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
if %errorlevel% neq 0 (
    echo.
    echo PigeonLab install failed. Check data\logs\install-*.log for details.
    pause
    exit /b %errorlevel%
)
echo.
echo PigeonLab install finished. You can now run start.bat.
pause
endlocal
