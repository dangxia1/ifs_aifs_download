"""上月数据下载 + IVT 计算 — 每月初运行一次.

Usage: python dl_lastmonth.py [YYYYMM]
  不带参数: 自动处理上个月
  带参数: 处理指定月份 (如 202606)
"""
import logging
import os
import sys
from ecmwf.opendata import Client
from utils import (MODELS, MODEL_STEPS, MODEL_DIRS, SOURCE, TIMES,
                   SAVE_DIR, THRESHOLD_DIR, setup_logging, last_month_ym,
                   month_dates, grib_path, nc_path, download_with_retry)
from compute_ivt import compute_ivt
from detect_ar import (detect_ar_from_nc, _load_monthly_thresholds,
                       _seasonal_threshold, consolidate_monthly_ar)


def main():
    setup_logging()

    # 确定目标月份
    ym = sys.argv[1] if len(sys.argv) > 1 else last_month_ym()
    dates = month_dates(ym)

    logging.info("=== dl_lastmonth IVT ===")
    logging.info("Month: %s | Dates: %d | Source: %s", ym, len(dates), SOURCE)
    logging.info("Models: %s | Steps: %s", MODELS, MODEL_STEPS)

    # 加载 AR 阈值
    thresholds_all = _load_monthly_thresholds(THRESHOLD_DIR)
    logging.info("AR thresholds loaded: %d months", len(thresholds_all))

    total_ok = 0
    total_skip = 0

    for model in MODELS:
        client = Client(source=SOURCE, model=model)
        steps = MODEL_STEPS[model]
        logging.info("--- %s (%d steps x %d days x %d times) ---",
                     model, len(steps), len(dates), len(TIMES))

        for date_str in dates:
            for t in TIMES:
                for step in steps:
                    gp = grib_path(ym, model, date_str, t, step)
                    np_ = nc_path(ym, model, date_str, t, step)
                    fname = os.path.basename(np_)

                    # AR NC 存在即跳过 (最后一步，有即完成)
                    ar_np = np_.replace("_ivt.nc", "_ar.nc")
                    if os.path.exists(ar_np):
                        total_skip += 1
                        continue

                    # 1. 下载 grib2
                    os.makedirs(os.path.dirname(gp), exist_ok=True)
                    ok, msg = download_with_retry(client, date_str, t, step, gp)

                    if not ok:
                        logging.info("  %s", msg)
                        continue  # 跳过失败文件，继续下一个

                    # 2. 计算 IVT
                    os.makedirs(os.path.dirname(np_), exist_ok=True)
                    try:
                        nlev, size_mb = compute_ivt(gp, np_)
                        logging.info("  %s  IVT: %d lev, %.1fMB", msg, nlev, size_mb)

                        # 3. AR 检测
                        month_idx = int(date_str[5:7]) - 1  # 1-12 → 0-11
                        thresh_2d = _seasonal_threshold(thresholds_all, month_idx)
                        ar_kb = detect_ar_from_nc(np_, ar_np, thresh_2d)
                        logging.info("         AR: %.0f KB", ar_kb)
                        total_ok += 1
                    except Exception as e:
                        logging.error("  IVT/AR FAIL %s: %s", fname, e)

    logging.info("=== Done: %d new, %d skipped ===", total_ok, total_skip)

    # 拼接月度 AR NetCDF
    logging.info("=== Consolidating monthly AR ===")
    consolidate_monthly_ar(SAVE_DIR, MODEL_DIRS, ym)


if __name__ == "__main__":
    main()