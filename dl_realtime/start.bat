@echo off
title ARFS Atmospheric River Forecast Support
cd /d %~dp0

echo ============================================
echo   ARFS Atmospheric River Forecast Support
echo ============================================

REM Check Python
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found.
    echo   Install Python 3.10+ from: https://www.python.org/downloads/
    echo   IMPORTANT: check "Add python.exe to PATH" during install.
    pause
    exit /b 1
)

REM 展示需要数据目录 (viewer.html + figures/ + run_time.json)
if not exist data\viewer.html (
    echo [ERROR] data\viewer.html not found.
    echo   Run dl_realtime.py to generate data, or copy the data dir
    echo   from the server (EC_SAVE_DIR / config_realtime.yaml save_dir).
    pause
    exit /b 1
)

echo Starting... browser will open http://localhost:8501/viewer.html automatically
echo Press Ctrl+C to stop

REM Open browser after 5s using explorer (most reliable on Windows)
start "" cmd /c "timeout /t 5 >nul & explorer http://localhost:8501/viewer.html"

python -m http.server 8501 --bind 127.0.0.1 --directory data
pause
