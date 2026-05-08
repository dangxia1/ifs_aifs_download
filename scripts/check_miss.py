"""Check for missing data files in a date range.

Usage: python scripts/check_miss.py 2026-05-01 2026-05-07
"""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dl_utils import TIMES, STEPS, target_path  # noqa: E402

MODELS = ["ifs", "aifs-single"]


def main():
    if len(sys.argv) != 3:
        print(f"Usage: python {__file__} <start_date> <end_date>")
        sys.exit(1)

    start = datetime.strptime(sys.argv[1], "%Y-%m-%d")
    end = datetime.strptime(sys.argv[2], "%Y-%m-%d")
    dates = []
    d = start
    while d <= end:
        dates.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)

    total_missing = 0
    per_day = len(TIMES) * len(STEPS)
    total_files = len(dates) * len(MODELS) * per_day

    for model in MODELS:
        print(f"\n=== {model} ===")
        for date_str in dates:
            missing = []
            for t in TIMES:
                for s in STEPS:
                    path = target_path(date_str, model, t, s)
                    if not os.path.exists(path):
                        name = os.path.basename(path)
                        missing.append(name)
            if missing:
                total_missing += len(missing)
                print(f"  {date_str}: missing {len(missing)}/{per_day}")
            else:
                print(f"  {date_str}: all complete ({per_day}/{per_day})")

    print(f"\nMissing {total_missing} out of {total_files} total")


if __name__ == "__main__":
    main()