@echo off
REM run.bat — Windows quick-start script for Site Data Analysis app
REM
REM WHERE TO RUN THIS:
REM   On your Windows computer.
REM   Double-click this file in File Explorer, OR open Command Prompt /
REM   PowerShell, cd into this project folder, and run:  run.bat
REM   Then open  http://localhost:8081  in your browser.
REM
REM REQUIREMENTS:
REM   Python 3.10 or newer must be installed from https://www.python.org/downloads/
REM   Make sure "Add Python to PATH" was checked during installation.

echo.
echo Checking Python version...
python --version
IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Python was not found. Please install Python 3.10 or newer from:
    echo        https://www.python.org/downloads/
    echo        Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo.
echo Installing dependencies (this may take a moment)...
python -m pip --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo pip module not found; bootstrapping with ensurepip...
    python -m ensurepip --upgrade
)
python -m pip install -r requirements.txt -q
IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: pip install failed. See output above for details.
    pause
    exit /b 1
)

echo.
echo =============================================
echo   App starting at  http://localhost:8081
echo   For other workstations, use http://YOUR-IP:8081
echo   Opening your browser automatically...
echo   Press Ctrl+C (or close this window) to stop.
echo =============================================
echo.

REM Open the browser after a short delay (start is non-blocking)
start "" /b cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:8081"

python app.py

pause
