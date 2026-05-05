"""Download historical IFS + AIFS data from Azure (2025-05-01 ~ 2025-08-31).

Usage: python scripts/dl_2025.py
"""
from datetime import datetime, timedelta
from ecmwf.opendata import Client
from dl_utils import TIMES, STEPS, download_with_retry, target_path, log_path

SOURCE = "azure"
MODELS = ["ifs", "aifs-single"]
DATE_START = "2025-05-01"
DATE_END = "2025-08-31"


def main():
    start = datetime.strptime(DATE_START, "%Y-%m-%d")
    end = datetime.strptime(DATE_END, "%Y-%m-%d")
    dates = []
    d = start
    while d <= end:
        dates.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)

    print(f"Source: {SOURCE} | Models: {MODELS}")
    print(f"Dates: {dates[0]} ~ {dates[-1]}  ({len(dates)} days)")
    print()

    for model in MODELS:
        print(f"=== {model} ===")
        client = Client(source=SOURCE, model=model)
        for date_str in dates:
            log_p = log_path(date_str)
            for t in TIMES:
                for s in STEPS:
                    ok, msg = download_with_retry(client, date_str, t, s,
                                                   target_path(date_str, model, t, s), log_p)
                    print(f"  {msg}")

    print("\nDone.")


if __name__ == "__main__":
    main()
