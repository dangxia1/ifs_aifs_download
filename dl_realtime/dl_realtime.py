"""3161 实时预报下载 — 每小时运行，覆盖最新 10 个文件.

Usage: python dl_realtime.py
调度: schtasks /create /tn "3161_download"
      /tr "python D:\Projects\CV\ifs-aifs-ai\dl_3163\dl_realtime.py" /sc HOURLY
"""
import logging
import os
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
    """AR 检测单文件 worker（顶层函数，供 multiprocessing pickle）."""
    nc_path, ar_path = args
    try:
        detect_ar_from_nc(nc_path, ar_path, thresh)
        return f"  AR {os.path.basename(ar_path)}"
    except Exception as e:
        return f"  AR FAIL {os.path.basename(ar_path)}: {e}"


def main():
    setup_logging()
    logging.info("=== 3161 realtime download ===")

    # 读取缓存（每行: model YYYY-MM-DD THHz）
    CACHE = {}
    cf = os.path.join(str(SAVE_DIR), ".last_run")
    if os.path.exists(cf):
        for line in open(cf):
            if line.strip():
                k, d, tt = line.strip().split(); CACHE[k] = f"{d} {tt}"

    total = 0
    any_updated = False
    for model in MODELS:
        steps = MODEL_STEPS[model]
        date_str, time_val = find_latest_run(model)
        run_key = f"{date_str} {time_val:02d}z"
        if CACHE.get(model) == run_key:
            logging.info("--- %s: %s [unchanged, skip] ---", model, run_key)
            continue
        any_updated = True
        CACHE[model] = run_key
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
            total += 1

    logging.info("=== Download done: %d files ===", total)

    # 下载完成后立即写入缓存（即使后续 IVT/AR/可视化失败也不重复下载）
    if any_updated:
        with open(cf, "w") as f:
            for m in MODELS:
                f.write(f"{m} {CACHE[m]}\n")

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
    from functools import partial

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

    if tasks:
        worker = partial(_ar_worker, thresh=thresh_2d)
        with mp.Pool(processes=min(4, len(tasks))) as pool:
            for msg in pool.imap_unordered(worker, tasks):
                logging.info(msg)
    else:
        logging.info("  All AR files exist, skip")

    # 可视化
    logging.info("=== Visualizing ===")
    visualize_all(str(SAVE_DIR), MODEL_DIRS)


if __name__ == "__main__":
    main()