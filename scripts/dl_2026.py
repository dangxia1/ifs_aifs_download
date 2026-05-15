"""Download recent IFS + AIFS forecast data (last 5 days, ecmwf source).

Usage: python scripts/dl_2026.py
"""
import logging
from datetime import datetime, timedelta, timezone
from ecmwf.opendata import Client
from dl_utils import (TIMES, STEPS, configure_logging, download_with_retry,
                      target_path, log_path)

SOURCE = "ecmwf"
MODELS = ["ifs", "aifs-single"]


def main():
    configure_logging()
    today = datetime.now(timezone.utc).date()
    dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(5, 0, -1)]

    logging.info("Source: %s | Models: %s", SOURCE, MODELS)
    logging.info("Dates: %s ~ %s  (last 5 days)", dates[0], dates[-1])

    for model in MODELS:
        logging.info("=== %s ===", model)
        client = Client(source=SOURCE, model=model)
        skip_count = 0
        for date_str in dates:
            log_p = log_path(date_str)
            for t in TIMES:
                for s in STEPS:
                    ok, msg = download_with_retry(client, date_str, t, s,
                                                   target_path(date_str, model, t, s), log_p)
                    if msg.startswith("SKIP"):
                        skip_count += 1
                    else:
                        logging.info("  %s", msg)
        if skip_count:
            logging.info("  %d 个文件已存在，跳过", skip_count)
    logging.info("Done.")


if __name__ == "__main__":
    main()