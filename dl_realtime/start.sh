#!/bin/bash
# ARFS 大气河短期预报支撑平台 — Linux/Mac 启动
cd "$(dirname "$0")"

echo "============================================"
echo "  ARFS 大气河短期预报支撑平台"
echo "============================================"

# 检查 python
if ! command -v python3 >/dev/null 2>&1; then
    echo "[错误] 未找到 python3"
    exit 1
fi

# 首次运行: 创建虚拟环境 + 装依赖
if [ ! -d .venv ]; then
    echo "[1/3] 创建虚拟环境..."
    python3 -m venv .venv
    echo "[2/3] 安装依赖..."
    .venv/bin/pip install -r requirements.txt -q
    echo "[3/3] 依赖安装完成"
fi

echo "启动界面中... 浏览器将自动打开 http://localhost:8501"
echo "按 Ctrl+C 关闭"
.venv/bin/streamlit run app.py --server.port 8501 --server.headless true
