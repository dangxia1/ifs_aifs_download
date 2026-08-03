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

REM First run: create venv + install deps
if not exist .venv (
    echo [1/3] Creating virtual environment...
    python -m venv .venv
    echo [2/3] Installing dependencies...
    .venv\Scripts\pip install -r requirements.txt -q -i https://pypi.tuna.tsinghua.edu.cn/simple
    echo [3/3] Setup complete
)

echo Starting... browser will open http://localhost:8501 automatically
echo Press Ctrl+C to stop

REM Open browser after 5s (let streamlit boot first)
start "ARFS-browser" cmd /c "timeout /t 5 >nul & start http://localhost:8501"

.venv\Scripts\streamlit run app.py --server.port 8501
pause
