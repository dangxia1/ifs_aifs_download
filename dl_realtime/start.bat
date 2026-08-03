@echo off
chcp 65001 >nul
title ARFS 大气河短期预报支撑平台
cd /d %~dp0

echo ============================================
echo   ARFS 大气河短期预报支撑平台
echo ============================================

REM 检查 Python
where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 未找到 Python, 请先安装 Python 3.10+:
    echo   https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 首次运行: 创建虚拟环境 + 装依赖
if not exist .venv (
    echo [1/3] 创建虚拟环境...
    python -m venv .venv
    echo [2/3] 安装依赖...
    .venv\Scripts\pip install -r requirements.txt -q
    echo [3/3] 依赖安装完成
)

echo 启动界面中... 浏览器将自动打开 http://localhost:8501
echo 按 Ctrl+C 关闭
.venv\Scripts\streamlit run app.py --server.port 8501 --server.headless true
pause
