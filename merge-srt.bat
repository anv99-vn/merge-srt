@echo off
:: Add Scoop shims to PATH so ffmpeg/ffprobe are found
set "PATH=%USERPROFILE%\scoop\shims;%PATH%"

if not exist "%~dp0.venv\Scripts\python.exe" (
    echo Virtual environment not found. Running setup...
    call "%~dp0setup.bat"
)
"%~dp0.venv\Scripts\python.exe" "%~dp0merge_srt.py" %*
if errorlevel 1 pause
