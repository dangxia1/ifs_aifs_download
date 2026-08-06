#!/bin/bash
# ARFS 大气河短期预报支撑平台 — Linux/Mac 启动 (HTML 展示版, 2026-08-06)
cd "$(dirname "$0")"

echo "============================================"
echo "  ARFS 大气河短期预报支撑平台"
echo "============================================"

# 检查 python
if ! command -v python3 >/dev/null 2>&1; then
    echo "[错误] 未找到 python3"
    exit 1
fi

# 展示需要数据目录 (viewer.html + figures/ + run_time.json)
if [ ! -f data/viewer.html ]; then
    echo "[错误] data/viewer.html 不存在"
    echo "  先运行 dl_realtime.py 生成数据, 或复制服务器数据目录"
    echo "  (EC_SAVE_DIR 或 config_realtime.yaml 的 save_dir)"
    exit 1
fi

echo "启动界面中... 浏览器将自动打开 http://localhost:8501/viewer.html"
echo "按 Ctrl+C 关闭"
python3 -m http.server 8501 --bind 127.0.0.1 --directory data
