"""上月数据下载 + IVT 共享模块."""
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# 非终端环境禁用进度条，避免 nohup/cron 日志刷屏
if not sys.stdout.isatty():
    os.environ.setdefault("TQDM_DISABLE", "1")

import yaml
import eccodes
from ecmwf.opendata import Client

# ── 项目根目录 ──────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.yaml"

_DEFAULTS = {
    "steps": {"ifs": [0, 3, 6, 24, 72], "aifs-single": [0, 6, 24, 72]},
    "models": {"ifs": "ifs", "aifs-single": "aifs"},
    "source": "google",
    "times": [0, 6, 12, 18],
    "single_params": ["tp"],
    "level_params": ["q", "u", "v", "t"],
    "levels": [1000, 925, 850, 700, 500, 300, 250, 200, 50],
    "retry_max": 3,
    "retry_interval": 10,
    "save_dir": "/shared_data/zongshen/ec_monthly_ivt",
    "threshold_dir": "/shared_data_5/ntfs2/liangju/ARIA_Asia_v15/ERA5",
}


def _load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    else:
        cfg = {}
    merged = _DEFAULTS | cfg
    sd = merged["save_dir"]
    if not os.path.isabs(sd):
        sd = str(ROOT / sd)
    merged["save_dir"] = sd
    return merged


_cfg = _load_config()

MODEL_STEPS = _cfg["steps"]
MODEL_DIRS = _cfg["models"]
MODELS = list(MODEL_DIRS.keys())
SOURCE = _cfg["source"]
TIMES = _cfg["times"]
SINGLE_PARAMS = _cfg["single_params"]
LEVEL_PARAMS = _cfg["level_params"]
LEVELS = _cfg["levels"]
RETRY_MAX = _cfg["retry_max"]
RETRY_INTERVAL = _cfg["retry_interval"]
SAVE_DIR = _cfg["save_dir"]
THRESHOLD_DIR = _cfg.get("threshold_dir", "")


# ── 上月计算 ────────────────────────────────────────────
def last_month_ym():
    """返回上月的 YYYYMM 字符串。例如 7月23日运行 → '202606'."""
    today = datetime.utcnow()
    first_of_this_month = today.replace(day=1)
    last_of_prev = first_of_this_month - timedelta(days=1)
    return last_of_prev.strftime("%Y%m")


def month_dates(ym):
    """返回指定月份的所有日期 ['YYYY-MM-DD', ...]."""
    year = int(ym[:4])
    month = int(ym[4:6])
    first = datetime(year, month, 1)
    if month == 12:
        last = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        last = datetime(year, month + 1, 1) - timedelta(days=1)
    dates = []
    d = first
    while d <= last:
        dates.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)
    return dates


# ── 路径 ────────────────────────────────────────────────
def month_save_dir(ym):
    """{save_dir}/{YYYYMM}/"""
    return os.path.join(SAVE_DIR, ym)


def grib_path(ym, model, date_str, time_val, step):
    """{save_dir}/{YYYYMM}/{dir}/step{N}/{date}_{model}_t{time}_step{N}.grib2"""
    subdir = MODEL_DIRS[model]
    fname = f"{date_str}_{model}_t{time_val:02d}_step{step}.grib2"
    return os.path.join(SAVE_DIR, ym, subdir, f"step{step}", fname)


def nc_path(ym, model, date_str, time_val, step):
    """IVT 输出路径，与 grib 同目录，后缀 _ivt.nc."""
    gpath = grib_path(ym, model, date_str, time_val, step)
    return gpath.replace(".grib2", "_ivt.nc")


# ── 日志 ─────────────────────────────────────────────────
def setup_logging():
    log_dir = Path(SAVE_DIR) / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.FileHandler(log_dir / f"{ts}.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


# ── 下载 + 校验 ─────────────────────────────────────────
def download_one(client, date_str, time_val, step, target):
    tmp1 = target + ".s.tmp"
    tmp2 = target + ".l.tmp"
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


def verify_grib(path):
    actual = []
    with open(path, "rb") as f:
        while True:
            msg_id = eccodes.codes_grib_new_from_file(f)
            if msg_id is None:
                break
            actual.append(eccodes.codes_get(msg_id, "shortName"))
            eccodes.codes_release(msg_id)
    missing = set(SINGLE_PARAMS) - set(actual)
    return len(actual), missing


def download_with_retry(client, date_str, time_val, step, target):
    fname = os.path.basename(target)
    target_tmp = target + ".tmp"

    for attempt in range(1, RETRY_MAX + 1):
        try:
            if os.path.exists(target_tmp):
                os.remove(target_tmp)
            download_one(client, date_str, time_val, step, target_tmp)
            count, missing = verify_grib(target_tmp)

            if missing:
                os.remove(target_tmp)
                return False, f"FAIL {fname}: missing {missing}"

            os.replace(target_tmp, target)
            size_mb = os.path.getsize(target) / 1024 / 1024
            return True, f"OK {fname}  ({count} msgs, {size_mb:.1f}MB)"

        except Exception as e:
            if os.path.exists(target_tmp):
                os.remove(target_tmp)
            if "404" in str(e):
                return False, f"EXPIRED {fname}: 404"
            if attempt < RETRY_MAX:
                logging.warning("Retry %d/%d %s: %s", attempt, RETRY_MAX, fname, e)
                time.sleep(RETRY_INTERVAL)
            else:
                return False, f"FAIL {fname}: {e}"

    return False, "UNREACHABLE"