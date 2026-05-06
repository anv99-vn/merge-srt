@echo off
echo Creating virtual environment...
python -m venv .venv
if errorlevel 1 (
    echo ERROR: Python not found or venv failed.
    pause
    exit /b 1
)
echo Done! Run merge-srt.bat to use the app.
pause
