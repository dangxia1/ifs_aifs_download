"""ARFS Windows 离线绿包打包脚本 (Linux 服务器交叉打包 → Windows 免安装使用).

原理 (2026-08-06):
  - python.org 官方 Windows embeddable Python (zip, 自包含解释器, 仅 stdlib)
  - 展示用静态 HTML (viewer.html) + 图片, 无需 streamlit/任何第三方包
  - conda-forge vc14_runtime 包提供 VC 运行库 dll (目标机无需装 VC redist)
→ 产物 ARFS_green_win.zip: 对方 Windows 电脑解压 → 双击 start.bat,
  零安装、零联网即可打开 http://localhost:8501/viewer.html.

用法 (服务器, conda activate ifs_aifs 后):
    python make_green_win.py
输出: /shared_data/zongshen/ARFS_green_win/ARFS_green_win.zip
"""
import glob
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
FIGURES = "/shared_data/zongshen/ec_realtime/figures"
OUT = "/shared_data/zongshen/ARFS_green_win"
PY_URL_TMPL = "https://www.python.org/ftp/python/{ver}/python-{ver}-embed-amd64.zip"
PY_VERS = ["3.12.10", "3.12.9", "3.12.8", "3.11.9", "3.11.8"]
VC_CHANNEL = "https://conda.anaconda.org/conda-forge/win-64/"

START_BAT = """@echo off
title ARFS Atmospheric River Forecast Support (Offline)
cd /d %~dp0
echo ============================================
echo   ARFS Atmospheric River Forecast Support
echo   Offline Edition - no Python needed
echo ============================================
if not exist runtime\\python.exe (
    echo [ERROR] runtime folder missing. Re-extract the zip.
    pause
    exit /b 1
)
if not exist data\\viewer.html (
    echo [ERROR] data folder missing. Re-extract the zip.
    pause
    exit /b 1
)
echo Starting... browser opens http://localhost:8501/viewer.html
echo Press Ctrl+C to stop
start "" cmd /c "timeout /t 5 >nul & explorer http://localhost:8501/viewer.html"
runtime\\python.exe -m http.server 8501 --bind 127.0.0.1 --directory data
pause
"""

USAGE_TXT = """ARFS 大气河短期预报支撑平台 (离线绿色版)

使用方法:
1. 解压 ARFS_green_win.zip 到任意目录
2. 双击 start.bat
3. 浏览器自动打开 http://localhost:8501/viewer.html (或手动输入)

特点:
- 无需安装 Python, 无需联网, 解压即用 (纯网页展示, 无第三方依赖)
- 只读展示: 最新一期 IFS/AIFS 双模型对比图 (全球/东亚/华北) + 北京地区时序图
- 数据更新: 由服务器重新打包最新图后替换本包

注意: 若 8501 端口被占用, 请关闭占用程序后重试。
"""


def sh(cmd, check=True):
    print("$", " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if check and r.returncode != 0:
        print(r.stdout, r.stderr)
        sys.exit(f"[错误] 命令失败: {' '.join(cmd)}")
    return r


def download(url, dest):
    print(f"$ curl -sL -o {dest} {url}")
    r = subprocess.run(["curl", "-sL", "-o", dest, url], capture_output=True)
    if r.returncode != 0 or not os.path.exists(dest) or os.path.getsize(dest) == 0:
        sys.exit(f"[错误] 下载失败: {url}")


def find_embeddable():
    for ver in PY_VERS:
        url = PY_URL_TMPL.format(ver=ver)
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, method="HEAD"), timeout=15) as r:
                if r.status == 200:
                    return ver, url
        except Exception:
            continue
    sys.exit("[错误] 找不到可用的 Windows embeddable Python")


def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    runtime = os.path.join(OUT, "runtime")
    os.makedirs(runtime)

    # 1/4 下载 Windows embeddable Python (仅 stdlib, http.server 展示用)
    py_ver, py_url = find_embeddable()
    print(f"[1/4] Windows embeddable Python {py_ver}")
    py_zip = os.path.join(OUT, "py.zip")
    download(py_url, py_zip)
    with zipfile.ZipFile(py_zip) as z:
        z.extractall(runtime)
    os.remove(py_zip)
    print(f"      → {runtime}/python.exe")

    # 2/4 启用 site + site-packages (embeddable 默认关闭; 无第三方包,
    #     保留此步仅保证 stdlib 路径正常)
    print("[2/4] 配置 python*._pth")
    pths = glob.glob(os.path.join(runtime, "python3*._pth"))
    if not pths:
        sys.exit("[错误] 未找到 ._pth 文件")
    stdlib_zip = open(pths[0]).readline().strip()
    with open(pths[0], "w") as f:
        f.write(f"{stdlib_zip}\n.\nimport site\n")
    print(f"      {os.path.basename(pths[0])}: {stdlib_zip} + import site")

    # 3/4 VC 运行库 dll (vcruntime140 / msvcp140 等)
    print("[3/4] VC 运行库 dll (vc14_runtime)")
    try:
        import zstandard  # noqa: F401
    except ImportError:
        sh([sys.executable, "-m", "pip", "install", "-q", "zstandard"])
        import zstandard
    out = sh(["conda", "search", "vc14_runtime", "--platform", "win-64",
              "-c", "conda-forge", "--json"], check=False)
    if out.returncode != 0:
        sys.exit("[错误] conda search vc14_runtime 失败")
    data = json.loads(out.stdout)
    builds = data.get("vc14_runtime", [])
    if not builds:
        sys.exit("[错误] conda-forge 无 vc14_runtime")
    # conda search --json 输出: {"vc14_runtime": [每条 build 一个 dict]},
    # 不是 {version: [...]} —— 从 build 列表取版本号最大的一条 (2026-08-06 bug 修复)
    def _ver_num(v):
        return [int(x) for x in v.replace("-", ".").split(".") if x.isdigit()]
    best = max(builds, key=lambda b: _ver_num(b["version"]))
    latest = best["version"]
    fn = best["fn"]
    print(f"      {latest} → {fn}")
    vc_pkg = os.path.join(OUT, "vc.conda")
    download(VC_CHANNEL + fn, vc_pkg)
    vc_tmp = os.path.join(OUT, "vc_tmp")
    with zipfile.ZipFile(vc_pkg) as z:
        inner = [n for n in z.namelist() if n.startswith("pkg-")][0]
        blob = z.read(inner)
    # .conda 内层 pkg-*.tar.zst 是 zstd 流: stream_reader 不可 seek,
    # tarfile 需要 seekable 文件对象 → 先整体解压进内存再读 tar (2026-08-06)
    dctx = zstandard.ZstdDecompressor()
    buf = io.BytesIO()
    with dctx.stream_reader(io.BytesIO(blob)) as rd:
        shutil.copyfileobj(rd, buf)
    buf.seek(0)
    with tarfile.open(fileobj=buf) as t:
        t.extractall(vc_tmp)
    shutil.copytree(os.path.join(vc_tmp, "Library", "bin"), runtime,
                    dirs_exist_ok=True)
    os.remove(vc_pkg)
    shutil.rmtree(vc_tmp, ignore_errors=True)
    missing = [d for d in ("vcruntime140.dll", "vcruntime140_1.dll",
                           "msvcp140.dll") if not os.path.exists(os.path.join(runtime, d))]
    if missing:
        print(f"      [警告] 缺少 dll: {missing}")

    # 4/4 组装绿包: 展示页 + 最新图 + 启动脚本
    print("[4/4] 组装绿包")
    data_dir = os.path.join(OUT, "data")
    fig_dir = os.path.join(data_dir, "figures")
    shutil.copytree(FIGURES, fig_dir, dirs_exist_ok=True)
    n_figs = len(glob.glob(os.path.join(fig_dir, "**", "*.png"), recursive=True))
    # run_time.json 实际在 SAVE_DIR 根 (visualize_all 会 rmtree(figures),
    # 脚本开头写根目录); 兼容旧位置 figures/ (2026-08-07 修复)
    rt_cands = [os.path.join(os.path.dirname(FIGURES), "run_time.json"),
                os.path.join(FIGURES, "run_time.json")]
    for cand in rt_cands:
        if os.path.exists(cand):
            shutil.copy(cand, os.path.join(data_dir, "run_time.json"))
            break
    # 展示页 viewer.html 放数据目录根 (与 figures/ run_time.json 同级,
    # 页内全部用相对路径; 2026-08-06 HTML 版取代 streamlit)
    shutil.copy(os.path.join(ROOT, "viewer.html"), os.path.join(data_dir, "viewer.html"))
    # 背景图 (页面暗化背景; viewer 按 背景.jpg → data/背景.jpg 顺序探测)
    bg_src = os.path.join(ROOT, "docs", "背景.jpg")
    if os.path.exists(bg_src):
        shutil.copy(bg_src, os.path.join(data_dir, "背景.jpg"))
    shutil.copytree(os.path.join(ROOT, "docs"), os.path.join(OUT, "docs"))
    # 中国立场边界 shapefile (省界/海岸线, 老师提供; 绿包为只读展示,
    # 保留以备将来重画)
    for shp in ("China_provinces.shp", "Continent.shp"):
        src = os.path.join(ROOT, shp)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(OUT, shp))
    with open(os.path.join(OUT, "start.bat"), "w", newline="\r\n") as f:
        f.write(START_BAT)
    with open(os.path.join(OUT, "使用说明.txt"), "w", encoding="utf-8") as f:
        f.write(USAGE_TXT)

    # zip
    print("→ zip 打包")
    os.chdir(os.path.dirname(OUT))
    sh(["zip", "-r", "-q", "ARFS_green_win.zip", "ARFS_green_win"], check=False)
    zpath = os.path.join(os.path.dirname(OUT), "ARFS_green_win.zip")
    if not os.path.exists(zpath):
        sys.exit("[错误] zip 打包失败")

    # 检查清单
    print("\n===== 检查清单 =====")
    for path, label in (
        (os.path.join(runtime, "python.exe"), "python.exe"),
        (os.path.join(data_dir, "viewer.html"), "viewer.html"),
        (os.path.join(data_dir, "背景.jpg"), "背景图"),
        (os.path.join(data_dir, "run_time.json"), "run_time.json"),
        (os.path.join(data_dir, "figures"), "图片目录"),
        (os.path.join(runtime, "vcruntime140.dll"), "vcruntime140.dll"),
        (os.path.join(runtime, "msvcp140.dll"), "msvcp140.dll"),
    ):
        print(f"  [{'OK' if os.path.exists(path) else '!!'}] {label}")
    print(f"  [OK] 图片 {n_figs} 张")
    size_mb = os.path.getsize(zpath) / 1048576
    print(f"\n完成: {zpath} ({size_mb:.0f} MB)")
    print("下一步: 下载到 Windows 解压 → 双击 start.bat → 浏览器验证")


if __name__ == "__main__":
    main()
