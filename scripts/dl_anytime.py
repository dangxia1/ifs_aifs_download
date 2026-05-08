"""Download data from Azure source for any date range.

Skips existing files. Use for filling historical data or patching gaps.

Usage: python scripts/dl_anytime.py 2025-05-01 2025-08-31   # 历史全量
       python scripts/dl_anytime.py 2026-05-01 2026-05-04   # 补缺口
"""
import logging
import os
import argparse
from datetime import datetime, timedelta
from ecmwf.opendata import Client
from dl_utils import (TIMES, STEPS, configure_logging, download_with_retry,
                      target_path, log_path)

SOURCE = "azure"
MODELS = ["ifs", "aifs-single"]


def main():
    configure_logging()
    parser = argparse.ArgumentParser(description="Download data from Azure for any date range")
    parser.add_argument("start", help="Start date (YYYY-MM-DD)")
    parser.add_argument("end", help="End date (YYYY-MM-DD)")
    args = parser.parse_args()

    start = datetime.strptime(args.start, "%Y-%m-%d")
    end = datetime.strptime(args.end, "%Y-%m-%d")
    dates = []
    d = start
    while d <= end:
        dates.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)

    for model in MODELS:
        client = Client(source=SOURCE, model=model)
        logging.info("=== %s (azure) ===", model)

        for date_str in dates:
            log_p = log_path(date_str)
            missing = 0
            for t in TIMES:
                for s in STEPS:
                    target = target_path(date_str, model, t, s)
                    if os.path.exists(target):
                        continue
                    missing += 1
                    ok, msg = download_with_retry(client, date_str, t, s, target, log_p)
                    logging.info("  %s", msg)

            if missing == 0:
                logging.info("  %s: all complete (%d files)", date_str, len(TIMES) * len(STEPS))
            else:
                logging.info("  %s: %d files attempted", date_str, missing)


if __name__ == "__main__":
    main()