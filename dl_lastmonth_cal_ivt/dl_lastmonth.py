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
                   SAVE_DIR, setup_logging, last_month_ym, month_dates,
                   grib_path, nc_path, download_with_retry)
from compute_ivt import compute_ivt


def main():
    setup_logging()

    # 确定目标月份
    ym = sys.argv[1] if len(sys.argv) > 1 else last_month_ym()
    dates = month_dates(ym)

    logging.info("=== dl_lastmonth IVT ===")
    logging.info("Month: %s | Dates: %d | Source: %s", ym, len(dates), SOURCE)
    logging.info("Models: %s | Steps: %s", MODELS, MODEL_STEPS)

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

                    # 跳过已完成的
                    if os.path.exists(np_):
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
                        total_ok += 1
                    except Exception as e:
                        logging.error("  IVT FAIL %s: %s", fname, e)

    logging.info("=== Done: %d new, %d skipped ===", total_ok, total_skip)


if __name__ == "__main__":
    main()