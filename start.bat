@echo off
setlocal

echo.
echo  ===========================
echo   PigeonLab Startup Script
echo  ===========================
echo.

:: -----------------------------------------------
:: 1. Check Python
:: -----------------------------------------------
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo         Download from https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo  Found: %%i

:: -----------------------------------------------
:: 2. Check Node
:: -----------------------------------------------
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not installed or not in PATH.
    echo         Download from https://nodejs.org/
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('node --version 2^>^&1') do echo  Found: Node %%i

:: -----------------------------------------------
:: 3. Create Python venv if needed
:: -----------------------------------------------
if not exist "backend\venv" (
    echo.
    echo  Creating Python virtual environment...
    python -m venv backend\venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: -----------------------------------------------
:: 4. Install Python dependencies
:: -----------------------------------------------
echo.
echo  Installing Python dependencies...
call backend\venv\Scripts\activate.bat
pip install -r backend\requirements.txt --quiet
if %errorlevel% neq 0 (
    echo [WARNING] Some Python packages may have failed to install.
    echo           The app may still work if core packages are available.
)

:: -----------------------------------------------
:: 5. Install Node dependencies if needed
:: -----------------------------------------------
if not exist "frontend\node_modules" (
    echo.
    echo  Installing frontend dependencies...
    cd frontend
    call npm install
    cd ..
    if %errorlevel% neq 0 (
        echo [ERROR] npm install failed.
        pause
        exit /b 1
    )
)

:: -----------------------------------------------
:: 6. Start backend in new terminal
:: -----------------------------------------------
echo.
echo  Starting FastAPI backend...
start "PigeonLab Backend" cmd /k "cd /d %~dp0backend && ..\backend\venv\Scripts\activate.bat && python -m uvicorn main:app --reload --port 8000"

:: -----------------------------------------------
:: 7. Start frontend in new terminal
:: -----------------------------------------------
echo  Starting Vite frontend...
start "PigeonLab Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

:: -----------------------------------------------
:: 8. Done
:: -----------------------------------------------
echo.
echo  ============================================
echo   PigeonLab is starting...
echo.
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:5173
echo   API docs: http://localhost:8000/docs
echo  ============================================
echo.
echo  Tip: Run "python backend\seed_data.py" to load sample data.
echo.

endlocal
