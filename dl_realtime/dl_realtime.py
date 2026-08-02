"""3161 实时预报下载 — 每小时运行，覆盖最新 10 个文件.

Usage: python dl_realtime.py
调度: schtasks /create /tn "3161_download"
      /tr "python D:\Projects\CV\ifs-aifs-ai\dl_3163\dl_realtime.py" /sc HOURLY
"""
import logging
import os
import warnings
warnings.filterwarnings("ignore")  # 屏蔽 FilFinder 等无关警告 (子进程继承)
from pathlib import Path
from ecmwf.opendata import Client
from utils import (MODELS, MODEL_STEPS, MODEL_DIRS, SOURCE, SAVE_DIR,
                   setup_logging, find_latest_run, download_with_retry,
                   clear_model_dir, model_dir, filename, THRESHOLD_DIR)
# 先导入本目录模块（compute_ivt / visualize_ivt 都在本目录）
from compute_ivt import compute_all_ivt
from visualize_ivt import visualize_all
# 再插入外部路径，仅用于 import detect_ar
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dl_lastmonth_cal_ivt"))
from detect_ar import _load_monthly_thresholds, _seasonal_threshold, detect_ar_from_nc


def _ar_worker(args, thresh):
    """AR 检测单文件 worker（mp.Process 目标，子进程内直接 print）."""
    nc_path, ar_path = args
    try:
        detect_ar_from_nc(nc_path, ar_path, thresh)
        print(f"  AR {os.path.basename(ar_path)}", flush=True)
    except Exception as e:
        print(f"  AR FAIL {os.path.basename(ar_path)}: {e}", flush=True)


def main():
    setup_logging()
    logging.info("=== 3161 realtime download ===")

    # 读取缓存（单行: 对齐时次 "YYYY-MM-DD THHz"）
    cf = os.path.join(str(SAVE_DIR), ".last_run")
    cached = ""
    if os.path.exists(cf):
        cached = open(cf).read().strip()

    # 获取两个模型的最新时次，取较旧者对齐（对比图必须同一时次）
    latest_runs = {}
    for model in MODELS:
        date_str, time_val = find_latest_run(model)
        latest_runs[model] = f"{date_str} {time_val:02d}z"
        logging.info("--- %s: latest=%s ---", model, latest_runs[model])

    aligned = min(latest_runs.values())  # 字符串比较: 日期+时次, min 取较旧
    logging.info("Aligned run: %s (cached: %s)", aligned, cached or "none")

    if aligned == cached:
        logging.info("=== No new aligned run, exit ===")
        return

    # 新时次: 清空旧数据 + 重新下载两个模型 (同一对齐时次)
    for model in MODELS:
        date_str, time_val = latest_runs[model].split()
        time_val = int(time_val[:-1])
        # 只下载对齐时次的数据；若某模型还没出对齐时次则用其最新 (较旧)
        if latest_runs[model] != aligned:
            date_str, time_val = aligned.split()
            time_val = int(time_val[:-1])
        steps = MODEL_STEPS[model]
        logging.info("--- %s (steps: %s) ---", model, steps)
        clear_model_dir(model)
        client = Client(source=SOURCE, model=model)

        d = model_dir(model)
        for step in steps:
            target = os.path.join(d, filename(date_str, model, time_val, step))

            ok, msg = download_with_retry(client, date_str, time_val, step, target)
            logging.info("  %s", msg)
            if not ok:
                logging.error("Aborting: %s step=%d failed", model, step)
                return 1

    logging.info("=== Download done: 50 files ===")

    # 下载完成后立即写入缓存（即使后续 IVT/AR/可视化失败也不重复下载）
    with open(cf, "w") as f:
        f.write(aligned + "\n")

    # 清空旧 IVT/AR，只保留最新一次
    for subdir in MODEL_DIRS.values():
        for root in ("ivt", "ar"):
            d = os.path.join(str(SAVE_DIR), root, subdir)
            if os.path.exists(d):
                import shutil
                shutil.rmtree(d)

    # 计算 IVT
    logging.info("=== Computing IVT ===")
    compute_all_ivt(str(SAVE_DIR), MODEL_DIRS)

    # AR 检测（跳过已存在 + 多进程并行）
    logging.info("=== AR Detection ===")
    thresholds = _load_monthly_thresholds(THRESHOLD_DIR)
    from datetime import datetime as dt
    month_idx = dt.utcnow().month - 1
    thresh_2d = _seasonal_threshold(thresholds, month_idx)
    ivt_root = os.path.join(str(SAVE_DIR), "ivt")
    ar_root = os.path.join(str(SAVE_DIR), "ar")

    import multiprocessing as mp

    # 收集待处理文件（跳过已存在）
    tasks = []
    for subdir in MODEL_DIRS.values():
        out_dir = os.path.join(ar_root, subdir)
        os.makedirs(out_dir, exist_ok=True)
        for nc_f in sorted(Path(ivt_root, subdir).glob("*_ivt.nc")):
            ar_f = os.path.join(out_dir, nc_f.name.replace("_ivt.nc", "_ar.nc"))
            if os.path.exists(ar_f):
                logging.info("  AR skip %s", os.path.basename(ar_f))
                continue
            tasks.append((str(nc_f), ar_f))

    # 分批并行 (非 daemon 进程，FilFinder2D 内部可再开子进程)
    if tasks:
        NPROC = 4
        for i in range(0, len(tasks), NPROC):
            batch = tasks[i:i + NPROC]
            procs = [mp.Process(target=_ar_worker, args=(t, thresh_2d))
                     for t in batch]
            for p in procs:
                p.start()
            for p in procs:
                p.join()
    else:
        logging.info("  All AR files exist, skip")

    # 可视化
    logging.info("=== Visualizing ===")
    visualize_all(str(SAVE_DIR), MODEL_DIRS)


if __name__ == "__main__":
    main()