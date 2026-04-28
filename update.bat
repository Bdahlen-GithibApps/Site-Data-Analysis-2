@echo off
echo Upgrading to the latest NiceGUI portal and all dependencies...
pip install --upgrade -r requirements.txt
if errorlevel 1 (
    echo Upgrade failed. Make sure Python and pip are installed.
    pause
    exit /b 1
)
echo.
echo All packages are now up to date.
echo Run run.bat to start the app.
pause
