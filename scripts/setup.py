"""Create data/ and log/ directory structure for a date range.

Usage: python scripts/setup.py <start_date> <end_date> [--models ifs aifs-single]

Example: python scripts/setup.py 2025-05-01 2025-08-31
         python scripts/setup.py 2026-05-01 2026-08-31
"""
import logging
import os
import sys
import argparse
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dl_utils import SAVE_DIR, LOG_DIR, STEPS, configure_logging  # noqa: E402

DEFAULT_MODELS = ["ifs", "aifs-single"]


def main():
    configure_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("start", help="YYYY-MM-DD")
    parser.add_argument("end", help="YYYY-MM-DD")
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    args = parser.parse_args()

    start = datetime.strptime(args.start, "%Y-%m-%d")
    end = datetime.strptime(args.end, "%Y-%m-%d")

    dirs = set()
    d = start
    while d <= end:
        year = d.strftime("%Y")
        month = d.strftime("%Y%m")
        for model in args.models:
            for s in STEPS:
                dirs.add(os.path.join(SAVE_DIR, year, model, str(s)))
        dirs.add(os.path.join(LOG_DIR, month))
        d += timedelta(days=1)

    for path in sorted(dirs):
        os.makedirs(path, exist_ok=True)
        logging.info("  %s/", path)

    logging.info("Created %d directories.", len(dirs))


if __name__ == "__main__":
    main()