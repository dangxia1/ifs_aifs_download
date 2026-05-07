"""Shared utilities for ECMWF data download scripts."""
import logging
import os
import time
import tempfile
from ecmwf.opendata import Client
import eccodes

# ---------- config ----------
import yaml

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")

_DEFAULTS = {
    "times": [0, 6, 12, 18],
    "steps": [6, 12, 24, 48, 72],
    "single_params": ["2t", "msl", "tp", "ssrd"],
    "level_params": ["q", "u", "v", "t"],
    "levels": [1000, 925, 850, 700, 500, 300, 250, 200, 50],
    "retry_max": 3,
    "retry_interval": 10,
    "save_dir": "data/raw",
    "log_dir": "log",
}


def _load_config():
    if os.path.exists(_CONFIG_PATH):
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    else:
        cfg = {}
    return _DEFAULTS | cfg


_cfg = _load_config()

TIMES = _cfg["times"]
STEPS = _cfg["steps"]
SINGLE_PARAMS = _cfg["single_params"]
LEVEL_PARAMS = _cfg["level_params"]
LEVELS = _cfg["levels"]
RETRY_MAX = _cfg["retry_max"]
RETRY_INTERVAL = _cfg["retry_interval"]
SAVE_DIR = os.path.join(_PROJECT_ROOT, _cfg["save_dir"])
LOG_DIR = os.path.join(_PROJECT_ROOT, _cfg["log_dir"])
EXPECTED = len(SINGLE_PARAMS) + len(LEVEL_PARAMS) * len(LEVELS)  # 40


def configure_logging(level=logging.INFO):
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )


def verify_grib(path):
    with open(path, "rb") as f:
        actual = []
        while True:
            msg_id = eccodes.codes_grib_new_from_file(f)
            if msg_id is None:
                break
            actual.append(eccodes.codes_get(msg_id, "shortName"))
            eccodes.codes_release(msg_id)
    missing = set(SINGLE_PARAMS) - set(actual)
    return len(actual), missing


def download_one(client, date_str, time_val, step, target):
    tmp1 = os.path.join(tempfile.gettempdir(), f"tmp_s_{date_str}_{time_val}_{step}.grib2")
    tmp2 = os.path.join(tempfile.gettempdir(), f"tmp_l_{date_str}_{time_val}_{step}.grib2")
    try:
        client.retrieve(date=date_str, time=time_val, type="fc", step=step,
                        param=SINGLE_PARAMS, target=tmp1)
        client.retrieve(date=date_str, time=time_val, type="fc", step=step,
                        param=LEVEL_PARAMS, levelist=LEVELS, target=tmp2)
        with open(target, "wb") as out:
            for t in (tmp1, tmp2):
                with open(t, "rb") as f:
                    out.write(f.read())
    finally:
        for t in (tmp1, tmp2):
            if os.path.exists(t):
                os.remove(t)


def target_path(date_str, model, time_val, step):
    """Build target file path: data/raw/{year}/{model}/{step}/{date}_{model}_t{time}_step{step}.grib2"""
    date_dir = date_str.replace("-", "")
    year = date_dir[:4]
    fname = f"{date_str}_{model}_t{time_val:02d}_step{step}.grib2"
    return os.path.join(SAVE_DIR, year, model, str(step), fname)


def log_path(date_str):
    """Build log file path: log/{YYYYMM}/{date}_download.log"""
    date_dir = date_str.replace("-", "")
    month = date_dir[:6]
    return os.path.join(LOG_DIR, month, f"{date_dir}_download.log")


def write_log(log_path, msg):
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
        f.flush()


def download_with_retry(client, date_str, time_val, step, target, log_p):
    """Download + verify + log, with retry. Returns (ok, status_msg)."""
    fname = os.path.basename(target)

    if os.path.exists(target):
        write_log(log_p, f"[SKIP] {fname}")
        return True, f"SKIP {fname}"

    os.makedirs(os.path.dirname(target), exist_ok=True)
    t0 = time.time()

    for attempt in range(1, RETRY_MAX + 1):
        try:
            download_one(client, date_str, time_val, step, target)
            count, missing = verify_grib(target)
            elapsed = time.time() - t0
            size_mb = os.path.getsize(target) / 1024 / 1024

            if missing:
                msg = f"[FAIL] {fname}: missing {missing}"
            else:
                msg = f"[OK] {fname}: {count} msgs, {size_mb:.1f}MB, {elapsed:.0f}s"
            write_log(log_p, msg)
            return not missing, msg

        except Exception as e:
            # 404 means data expired on server — skip immediately
            if "404" in str(e):
                msg = f"[EXPIRED] {fname}: 404"
                write_log(log_p, msg)
                return False, msg
            if attempt < RETRY_MAX:
                logging.warning("Retry %d/%d %s: %s", attempt, RETRY_MAX, fname, e)
                time.sleep(RETRY_INTERVAL)
            else:
                msg = f"[FAIL] {fname}: {e}"
                write_log(log_p, msg)
                return False, msg