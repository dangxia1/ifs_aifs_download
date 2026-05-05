"""Fill missing data files from Azure source.

Scans data/raw/ for gaps and downloads them. Use when ecmwf source
data has expired (~4 day window) and Azure still has it.

Usage: python scripts/dl_miss.py 2026-05-01 2026-05-04
"""
import os
import sys
from datetime import datetime, timedelta
from ecmwf.opendata import Client
from dl_utils import TIMES, STEPS, download_with_retry, target_path, log_path

SOURCE = "azure"
MODELS = ["ifs", "aifs-single"]


def main():
    if len(sys.argv) != 3:
        print("Usage: python scripts/dl_miss.py <start_date> <end_date>")
        sys.exit(1)

    start = datetime.strptime(sys.argv[1], "%Y-%m-%d")
    end = datetime.strptime(sys.argv[2], "%Y-%m-%d")
    dates = []
    d = start
    while d <= end:
        dates.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)

    for model in MODELS:
        client = Client(source=SOURCE, model=model)
        print(f"\n=== {model} (azure) ===")

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
                    print(f"  {msg}")

            if missing == 0:
                print(f"  {date_str}: all complete ({len(TIMES) * len(STEPS)} files)")
            else:
                print(f"  {date_str}: {missing} files attempted")


if __name__ == "__main__":
    main()