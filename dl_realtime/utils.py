"""实时下载共享模块 — 加载配置 / 日志 / 下载 / 校验 / 重试."""
import logging
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

# 非终端环境禁用进度条，避免 nohup/cron 日志刷屏
if not sys.stdout.isatty():
    os.environ.setdefault("TQDM_DISABLE", "1")

import yaml
import eccodes
from ecmwf.opendata import Client

# ── 项目根目录 (dl_3163/) ──────────────────────────────
ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config_realtime.yaml"

_DEFAULTS = {
    "steps": {"ifs": list(range(0, 145, 6)), "aifs-single": list(range(0, 145, 6))},
    "single_params": ["tp"],
    "level_params": ["q", "u", "v", "t", "gh"],
    "levels": [1000, 925, 850, 700, 500, 300, 250, 200, 50],
    "models": {"ifs": "ifs", "aifs-single": "aifs"},
    "source": "ecmwf",
    "retry_max": 3,
    "retry_interval": 10,
    "save_dir": "data",
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

# 对外暴露的配置常量
MODEL_STEPS = _cfg["steps"]      # {"ifs": [...], "aifs-single": [...]}
MODEL_DIRS = _cfg["models"]      # {"ifs": "ifs", "aifs-single": "aifs"}
MODELS = list(MODEL_DIRS.keys()) # ["ifs", "aifs-single"]
SOURCE = _cfg["source"]
SINGLE_PARAMS = _cfg["single_params"]
LEVEL_PARAMS = _cfg["level_params"]
LEVELS = _cfg["levels"]
RETRY_MAX = _cfg["retry_max"]
RETRY_INTERVAL = _cfg["retry_interval"]
SAVE_DIR = Path(_cfg["save_dir"])
THRESHOLD_DIR = _cfg.get("threshold_dir", "")
LOG_DIR = SAVE_DIR / "log"


# ── 日志 ─────────────────────────────────────────────────
def setup_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.FileHandler(LOG_DIR / f"{ts}.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


# ── ECMWF 最新预报时次获取 ──────────────────────────────
def find_latest_run(model):
    """每个模型独立获取最新可用起报时次 (IFS 和 AIFS 发布时间可能不同)."""
    client = Client(source=SOURCE, model=model)
    dt = client.latest(type="fc", step=0, param=[SINGLE_PARAMS[0]])
    date_str = dt.strftime("%Y-%m-%d")
    time_val = dt.hour
    logging.info("Latest run %s: %s %02dz [OK]", model, date_str, time_val)
    return date_str, time_val


# ── 下载 + 校验 ─────────────────────────────────────────
def download_one(client, date_str, time_val, step, target):
    """下载地面场 + 高空场，合并写入 target."""
    tmp1 = target + ".s.tmp"
    tmp2 = target + ".l.tmp"
    try:
        client.retrieve(
            date=date_str, time=time_val, type="fc", step=step,
            param=SINGLE_PARAMS, target=tmp1,
        )
        client.retrieve(
            date=date_str, time=time_val, type="fc", step=step,
            param=LEVEL_PARAMS, levelist=LEVELS, target=tmp2,
        )
        with open(target, "wb") as out:
            for t in (tmp1, tmp2):
                with open(t, "rb") as f:
                    out.write(f.read())
    finally:
        for t in (tmp1, tmp2):
            if os.path.exists(t):
                os.remove(t)


def verify_grib(path):
    """返回 (消息数, 缺失要素集合)."""
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
    """下载 + 校验 + 重试. 返回 (ok, msg)."""
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


# ── 路径工具 ────────────────────────────────────────────
def clear_model_dir(model):
    """清空 {save_dir}/{dir}/，确保只保留最新."""
    d = SAVE_DIR / MODEL_DIRS[model]
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True, exist_ok=True)


def model_dir(model):
    """返回 {save_dir}/{dir}/."""
    return str(SAVE_DIR / MODEL_DIRS[model])


def filename(date_str, model, time_val, step):
    return f"{date_str}_{model}_t{time_val:02d}_step{step}.grib2"