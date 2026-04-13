@echo off
echo Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install dependencies. Make sure Python and pip are installed.
    pause
    exit /b 1
)
echo.
echo Starting Dev Code Lookup app at http://localhost:8080
echo Press Ctrl+C to stop.
echo.
python app.py
pause
