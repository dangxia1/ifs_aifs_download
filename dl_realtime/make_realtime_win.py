"""ARFS Windows 独立实时包打包脚本 (本地 Windows 运行, 集成下载+处理+可视化).

原理 (2026-08-07):
  - conda-pack 把本机 ifs_aifs env 整体打包 → runtime/ (Windows 同平台, 解压即用)
  - 组装: runtime(全科学计算库) + 全部代码 + thresholds/(12 月 ERA5 阈值) + viewer.html
  - start.bat 一键: 激活 runtime → dl_realtime.py(下载→IVT→AR→可视化) → http.server → 浏览器
  - 与绿包 (make_green_win.py, 静态最新一期) 互补: 本包在老师电脑上独立跑实时全流程
产物: ARFS_realtime_win.zip (~1GB; 目标机需能访问 ECMWF 数据源, 首次运行下载 ~1.3GB)

用法 (Windows, 需已装好 ifs_aifs 环境且依赖齐全):
    conda activate ifs_aifs
    python make_realtime_win.py
前置: 本地 ivt处理/ 需有 12 个月 ERA5_IVT_threshold_85_19812023_*.pckl
      (从服务器 /shared_data_5/ntfs2/liangju/ARIA_Asia_v15/ERA5 复制)
"""
import os
import shutil
import subprocess
import sys
import tarfile
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(ROOT), "ARFS_realtime_win")  # 父目录输出 (zip 也在这)
ENV_NAME = "ifs_aifs"  # 打包的本地 conda 环境
# conda-pack 是独立 CLI (非 conda 子命令): 优先当前 env 的 Scripts/conda-pack.exe
CONDA_PACK = os.path.join(sys.prefix, "Scripts", "conda-pack.exe")
if not os.path.exists(CONDA_PACK):
    CONDA_PACK = "conda-pack"
THRESH_SRC = os.path.join(os.path.dirname(ROOT), "ivt处理")  # 本地阈值目录 (12 月)
# 复制进包的代码文件 (app/)
APP_FILES = [
    "dl_realtime.py", "visualize_ivt.py", "compute_ivt.py",
    "north_china_timeseries.py", "utils.py", "make_font.py",
    "config_realtime.yaml", "China_provinces.shp", "Continent.shp",
]
# 包根文件: viewer.html (运行时拷进 data/ 与图同级), 背景图
ROOT_FILES = ["viewer.html"]
EXTRA_FILES = [("docs", "背景.jpg")]

START_BAT = """@echo off
title ARFS Atmospheric River Forecast Support (Realtime)
cd /d %~dp0
echo ============================================
echo   ARFS 大气河短期预报支撑平台 (实时完整版)
echo   Download IVT AR Visualize - all in one
echo ============================================
if not exist runtime\\python.exe (
    echo [ERROR] runtime folder missing. Re-extract the zip.
    pause
    exit /b 1
)
set PATH=%~dp0runtime;%~dp0runtime\\Library\\bin;%~dp0runtime\\Scripts;%PATH%
echo [1/3] Download + IVT + AR + Visualize (first run ~1.3GB, 30-60min)
cd app
"%~dp0runtime\\python.exe" dl_realtime.py
if errorlevel 1 (
    echo [ERROR] dl_realtime.py failed. Check app\\log\\.
    pause
    exit /b 1
)
cd ..
echo [2/3] Deploy viewer.html + background
copy /Y viewer.html data\\viewer.html >nul 2>&1
if exist "%~dp0背景.jpg" copy /Y "%~dp0背景.jpg" data\\背景.jpg >nul 2>&1
echo [3/3] Start web server: http://localhost:8501/viewer.html
start "" cmd /c "timeout /t 5 >nul & explorer http://localhost:8501/viewer.html"
"%~dp0runtime\\python.exe" -m http.server 8501 --bind 127.0.0.1 --directory data
pause
"""

USAGE_TXT = """ARFS 大气河短期预报支撑平台 (实时完整版)

与绿色展示版 (静态最新一期) 的区别:
本包集成 数据下载 → IVT 计算 → 大气河识别 → 可视化 → 网页展示 全流程,
在您电脑上独立运行, 每次启动自动拉取 ECMWF 最新一期 IFS/AIFS 预报并出图。

使用方法:
1. 解压 ARFS_realtime_win.zip 到任意目录
2. 双击 start.bat
3. 程序自动: 下载最新数据 (~1.3GB, 首次或隔天运行) → 计算处理 → 出图
   → 浏览器自动打开 http://localhost:8501/viewer.html
4. 关闭黑窗口即停止服务

要求:
- 联网: 需能访问 ECMWF 数据源 (data.ecmwf.int / google 镜像)
- 磁盘: 数据 + 处理产物约 2GB
- 无需安装 Python / 任何依赖 (环境已内置)

注意: 若 8501 端口被占用, 请关闭占用程序后重试。
"""


def sh(cmd, check=True, cwd=None):
    print("$", " ".join(cmd))
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        print(r.stdout[-4000:], r.stderr[-4000:])
        sys.exit(f"[错误] 命令失败: {' '.join(cmd)}")
    return r


def find_thresholds():
    """返回 12 个月阈值文件列表 (缺月报错)."""
    found = []
    for m in range(1, 13):
        p = os.path.join(THRESH_SRC, f"ERA5_IVT_threshold_85_19812023_{m:02d}.pckl")
        if not os.path.exists(p):
            sys.exit(f"[错误] 缺少阈值文件 {m:02d} 月: {p}\n"
                     f"请从服务器 /shared_data_5/ntfs2/liangju/ARIA_Asia_v15/ERA5 复制全部 12 个月")
        found.append(p)
    return found


def build_packaged_config():
    """生成包内专用 config_realtime.yaml (相对路径, 与包目录绑定)."""
    import yaml
    with open(os.path.join(ROOT, "config_realtime.yaml"), encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    # save_dir/threshold_dir 相对 app/ (dl_realtime.py 所在目录)
    cfg["save_dir"] = "../data"
    cfg["threshold_dir"] = "../thresholds"
    with open(os.path.join(OUT, "app", "config_realtime.yaml"), "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
    print("      包内 config: save_dir=../data threshold_dir=../thresholds")


def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, "app"))
    os.makedirs(os.path.join(OUT, "thresholds"))

    # 1/5 conda-pack 打包 ifs_aifs 环境 → runtime.tar.gz → 解压为 runtime/
    print("[1/5] conda-pack 打包环境 (ifs_aifs)")
    sh([CONDA_PACK, "-n", ENV_NAME, "-o", os.path.join(OUT, "runtime.tar.gz"),
        "--force"])
    print("      解压 runtime/")
    with tarfile.open(os.path.join(OUT, "runtime.tar.gz")) as t:
        t.extractall(os.path.join(OUT, "runtime"))
    os.remove(os.path.join(OUT, "runtime.tar.gz"))
    if not os.path.exists(os.path.join(OUT, "runtime", "python.exe")):
        sys.exit("[错误] runtime/python.exe 不存在, conda-pack 失败")

    # 2/5 复制代码 (app/), 生成包内 config
    print("[2/5] 复制代码 → app/")
    for f in APP_FILES:
        src = os.path.join(ROOT, f)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(OUT, "app", f))
        else:
            print(f"      [警告] 缺文件: {f}")
    for f in ROOT_FILES:
        shutil.copy(os.path.join(ROOT, f), os.path.join(OUT, f))
    for sub, f in EXTRA_FILES:
        src = os.path.join(ROOT, sub, f)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(OUT, f))
    # dl_lastmonth_cal_ivt/ 必须在 app/ 上一级 (dl_realtime.py sys.path 相对路径)
    src_dl = os.path.join(os.path.dirname(ROOT), "dl_lastmonth_cal_ivt")
    if os.path.exists(src_dl):
        shutil.copytree(src_dl, os.path.join(OUT, "dl_lastmonth_cal_ivt"),
                        ignore=shutil.ignore_patterns("__pycache__", "*.log"))
    else:
        print("[警告] 未找到 dl_lastmonth_cal_ivt/, AR 检测将不可用")
    build_packaged_config()

    # 3/5 阈值 12 月
    print("[3/5] 复制阈值 → thresholds/")
    for p in find_thresholds():
        shutil.copy(p, os.path.join(OUT, "thresholds"))
    print(f"      12 个月阈值已复制")

    # 4/5 启动脚本 + 使用说明 (CRLF, 中文 UTF-8)
    print("[4/5] start.bat + 使用说明")
    with open(os.path.join(OUT, "app", "start.bat"), "w", newline="\r\n") as f:
        f.write(START_BAT)
    with open(os.path.join(OUT, "使用说明.txt"), "w", encoding="utf-8") as f:
        f.write(USAGE_TXT)

    # 5/5 zip 打包
    print("[5/5] zip 打包")
    zpath = os.path.join(os.path.dirname(OUT), "ARFS_realtime_win.zip")
    if os.path.exists(zpath):
        os.remove(zpath)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for root, _, files in os.walk(OUT):
            for f in files:
                full = os.path.join(root, f)
                arc = os.path.relpath(full, os.path.dirname(OUT))
                z.write(full, arc)

    # 检查清单
    print("\n===== 检查清单 =====")
    checks = [
        (os.path.join(OUT, "runtime", "python.exe"), "runtime/python.exe"),
        (os.path.join(OUT, "app", "dl_realtime.py"), "app/dl_realtime.py"),
        (os.path.join(OUT, "app", "config_realtime.yaml"), "app/config_realtime.yaml"),
        (os.path.join(OUT, "dl_lastmonth_cal_ivt", "detect_ar.py"), "dl_lastmonth_cal_ivt/detect_ar.py"),
        (os.path.join(OUT, "thresholds"), "thresholds/ (12 月)"),
        (os.path.join(OUT, "viewer.html"), "viewer.html"),
    ]
    for path, label in checks:
        ok = os.path.isdir(path) or os.path.exists(path)
        print(f"  [{'OK' if ok else '!!'}] {label}")
    n_thresh = len(os.listdir(os.path.join(OUT, "thresholds")))
    print(f"  [{'OK' if n_thresh == 12 else '!!'}] 阈值文件 {n_thresh}/12")
    with open(os.path.join(OUT, "viewer.html"), encoding="utf-8") as f:
        vh = f.read(512)
    print("  [{}] viewer 版本标记 v2.9".format("OK" if "v2.9" in vh else "!!"))
    size_mb = os.path.getsize(zpath) / 1048576
    print(f"\n完成: {zpath} ({size_mb:.0f} MB)")
    print("下一步: 解压到老师 Windows 电脑 → 双击 start.bat → 自动下载/处理/展示")
    print("提示: 正式交付前先在目标机跑一次全流程 (首次下载 ~1.3GB, 30-60min)")


if __name__ == "__main__":
    main()
