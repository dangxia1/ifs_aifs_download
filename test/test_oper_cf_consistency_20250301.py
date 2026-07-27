"""Compare IFS oper(fc) and ifs-env(cf) consistency for a single date and sample.

- Parameters are loaded from scripts/config.yaml (times/steps/single_params/level_params/levels).
- Randomly samples 1 of configured times and 1 of configured steps each run.
- Downloads both dataset variants from ecmwf by default,
  downloads surface + pressure level fields, and compares message-level hash equality.
"""

import os
import hashlib
import random
import tempfile
from array import array
from typing import Dict, List, Tuple

from ecmwf.opendata import Client
import eccodes
import yaml

from test_utils import TestFail, run_tests


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(PROJECT_ROOT, "scripts", "config.yaml")
SEED = int(os.environ.get("IFS_ENV_CMP_SEED", "20250301"))
SAMPLE_COUNT = int(os.environ.get("IFS_ENV_CMP_SAMPLE_COUNT", "1"))
DATE = os.environ.get("IFS_ENV_CMP_DATE", "2026-07-23")
SOURCE = os.environ.get("IFS_ENV_CMP_SOURCE", "ecmwf")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return {
        "times": cfg.get("times", [0, 6, 12, 18]),
        "steps": cfg.get("steps", [0, 6, 12, 24, 48, 72]),
        "single_params": cfg.get("single_params", ["2t", "msl", "tp", "ssrd"]),
        "level_params": cfg.get("level_params", ["q", "u", "v", "t"]),
        "levels": cfg.get("levels", [1000, 925, 850, 700, 500, 300, 250, 200, 50]),
    }


def _key(msg_id) -> Tuple:
    return (
        eccodes.codes_get(msg_id, "shortName"),
        eccodes.codes_get(msg_id, "typeOfLevel"),
        eccodes.codes_get(msg_id, "level"),
        eccodes.codes_get(msg_id, "number") if eccodes.codes_is_defined(msg_id, "number") else None,
        eccodes.codes_get(msg_id, "paramId"),
    )


def _values_hash(msg_id) -> str:
    values = eccodes.codes_get_double_array(msg_id, "values")
    return hashlib.sha256(array("d", values).tobytes()).hexdigest()


def message_signatures(path: str) -> Dict[Tuple, List[str]]:
    sigs: Dict[Tuple, List[str]] = {}
    with open(path, "rb") as f:
        while True:
            msg_id = eccodes.codes_grib_new_from_file(f)
            if msg_id is None:
                break
            k = _key(msg_id)
            h = _values_hash(msg_id)
            sigs.setdefault(k, []).append(h)
            eccodes.codes_release(msg_id)
    return sigs


def merge_surface_and_level(client: Client, date: str, time_val: int, step: int, stream: str, ftype: str, target: str,
                           single_params, level_params, levels) -> None:
    s_tmp = target + ".s.grib2"
    l_tmp = target + ".l.grib2"
    try:
        client.retrieve(
            date=date, time=time_val, stream=stream, type=ftype, step=step,
            param=single_params, target=s_tmp,
        )
        client.retrieve(
            date=date, time=time_val, stream=stream, type=ftype, step=step,
            param=level_params, levelist=levels, target=l_tmp,
        )
        with open(target, "wb") as out:
            for part in (s_tmp, l_tmp):
                with open(part, "rb") as f:
                    out.write(f.read())
    finally:
        for part in (s_tmp, l_tmp):
            if os.path.exists(part):
                os.remove(part)


def compare_signatures(oper_file: str, ifs_env_file: str) -> None:
    sig_oper = message_signatures(oper_file)
    sig_env = message_signatures(ifs_env_file)
    if set(sig_oper.keys()) != set(sig_env.keys()):
        only_oper = set(sig_oper.keys()) - set(sig_env.keys())
        only_env = set(sig_env.keys()) - set(sig_oper.keys())
        raise TestFail(f"field key set mismatch: only_oper={only_oper}, only_env={only_env}")
    for k in sorted(sig_oper.keys()):
        if sorted(sig_oper[k]) != sorted(sig_env[k]):
            raise TestFail(f"field {k} values mismatch")


def main():
    cfg = load_config()
    date = DATE
    rng = random.Random(SEED)
    times = rng.sample(cfg["times"], min(SAMPLE_COUNT, len(cfg["times"])))
    steps = rng.sample(cfg["steps"], min(SAMPLE_COUNT, len(cfg["steps"])))
    print(f"Date: {date}")
    print(f"Selected times: {sorted(times)}")
    print(f"Selected steps: {sorted(steps)}")
    print(f"Using seed: {SEED}")

    ifs_client = Client(source=SOURCE, model="ifs")
    tmpdir = tempfile.mkdtemp(prefix="test_oper_cf_")

    def test_consistency():
        for t in sorted(times):
            for step in sorted(steps):
                oper_target = os.path.join(tmpdir, f"oper_fc_t{t:02d}_step{step}.grib2")
                env_target = os.path.join(tmpdir, f"ifs_env_cf_t{t:02d}_step{step}.grib2")
                merge_surface_and_level(
                    ifs_client, date, t, step, "oper", "fc", oper_target,
                    cfg["single_params"], cfg["level_params"], cfg["levels"]
                )
                merge_surface_and_level(
                    ifs_client, date, t, step, "enfo", "cf", env_target,
                    cfg["single_params"], cfg["level_params"], cfg["levels"]
                )
                compare_signatures(oper_target, env_target)

                os.remove(oper_target)
                os.remove(env_target)

    ok = run_tests(f"IFS oper(fc) vs ifs-env(cf) consistency on {date}", [
        ("random sample consistency check", test_consistency),
    ])

    for f in os.listdir(tmpdir):
        os.remove(os.path.join(tmpdir, f))
    os.rmdir(tmpdir)

    if not ok:
        exit(1)


if __name__ == "__main__":
    main()
