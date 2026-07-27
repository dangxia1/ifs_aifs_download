"""3161 实时预报下载 — 每小时运行，覆盖最新 10 个文件.

Usage: python dl_realtime.py
调度: schtasks /create /tn "3161_download"
      /tr "python D:\Projects\CV\ifs-aifs-ai\dl_3163\dl_realtime.py" /sc HOURLY
"""
import logging
import os
from ecmwf.opendata import Client
from utils import (MODELS, MODEL_STEPS, MODEL_DIRS, SOURCE, SAVE_DIR,
                   setup_logging, find_latest_run, download_with_retry,
                   clear_model_dir, model_dir, filename)
from compute_ivt import compute_all_ivt
from visualize_ivt import visualize_all


def main():
    setup_logging()
    logging.info("=== 3161 realtime download ===")
    logging.info("Models: %s | Steps: %s", MODELS, MODEL_STEPS)

    total = 0
    for model in MODELS:
        steps = MODEL_STEPS[model]
        date_str, time_val = find_latest_run(model)  # 每个模型独立获取最新时次
        logging.info("--- %s (steps: %s) ---", model, steps)
        clear_model_dir(model)  # 先清空该模型目录
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

    # 计算 IVT
    logging.info("=== Computing IVT ===")
    compute_all_ivt(str(SAVE_DIR), MODEL_DIRS)

    # 可视化
    logging.info("=== Visualizing ===")
    visualize_all(str(SAVE_DIR), MODEL_DIRS)


if __name__ == "__main__":
    main()