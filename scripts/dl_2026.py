"""Download recent IFS + AIFS forecast data (last 5 days, ecmwf source).

Usage: python scripts/dl_2026.py
"""
from datetime import datetime, timedelta, timezone
from ecmwf.opendata import Client
from dl_utils import TIMES, STEPS, download_with_retry, target_path, log_path

SOURCE = "ecmwf"
MODELS = ["ifs", "aifs-single"]


def main():
    today = datetime.now(timezone.utc).date()
    dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(5, 0, -1)]

    print(f"Source: {SOURCE} | Models: {MODELS}")
    print(f"Dates: {dates[0]} ~ {dates[-1]}  (last 5 days)")
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
