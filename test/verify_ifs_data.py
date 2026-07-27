"""验证两件事：
1. IFS 2025 年是否有 12Z 和 18Z 数据
2. oper/fc (HRES) 与 enfo/cf (ENS控制预报) 是否相同
"""
import os
import sys
import time
import tempfile
import numpy as np
from ecmwf.opendata import Client
import eccodes

TMP = tempfile.gettempdir()


def _download(client, date, time, step, params, target, **kw):
    """带超时的下载."""
    client.retrieve(date=date, time=time, type=kw.pop("type", "fc"),
                    step=step, param=params, target=target, **kw)


def check_availability():
    """检查 2025 年 6 月 15 日各时次是否存在."""
    print("=== 1. 检查 IFS 2025-06-15 各时次 ===")
    for tv in [0, 6, 12, 18]:
        target = os.path.join(TMP, f"_vfy_t{tv:02d}.grib2")
        try:
            client = Client(source="azure", model="ifs")
            client.retrieve(date="2025-06-15", time=tv, type="fc",
                            step=0, param=["2t"], target=target)
            sz = os.path.getsize(target)
            os.remove(target)
            print(f"  {tv:02d}Z: 存在  ({sz:,} bytes)")
        except Exception as e:
            msg = str(e).split("\n")[0][:80]
            print(f"  {tv:02d}Z: 失败 — {msg}")
            if os.path.exists(target):
                os.remove(target)


def _compare_one_time(date_str, time_val, step, params, levels):
    """对比单个时次的 oper/fc vs enfo/cf，返回 True 表示完全相同."""
    print(f"\n  [{date_str} {time_val:02d}Z step={step}]")
    specs = [
        ("oper/fc", Client(source="azure", model="ifs"),
         {"stream": "oper", "type": "fc"}),
        ("enfo/cf", Client(source="azure", model="ifs"),
         {"stream": "enfo", "type": "cf"}),
    ]

    files = {}
    for label, client, kw in specs:
        target = os.path.join(TMP, f"_vfy_{date_str}_{time_val:02d}_{label.replace('/','_')}.grib2")
        try:
            kw_args = {"date": date_str, "time": time_val, "step": step,
                       "param": params, "target": target}
            if levels:
                kw_args["levelist"] = levels
            client.retrieve(type=kw.pop("type"), **kw_args, **kw)
            files[label] = target
        except Exception as e:
            print(f"    {label}: 失败 — {e}")
            return False

    # 逐字段对比
    data = {}
    for label, path in files.items():
        fields = {}
        with open(path, "rb") as f:
            while True:
                msg_id = eccodes.codes_grib_new_from_file(f)
                if msg_id is None: break
                sn = eccodes.codes_get(msg_id, "shortName")
                lev = eccodes.codes_get(msg_id, "level", ktype=str)
                fields[f"{sn}@{lev}"] = eccodes.codes_get_values(msg_id)
                eccodes.codes_release(msg_id)
        data[label] = fields

    for key in sorted(data["oper/fc"]):
        diff = np.max(np.abs(data["oper/fc"][key] - data["enfo/cf"][key]))
        if diff == 0:
            print(f"    {key}: 相同")
        else:
            print(f"    {key}: 有差异 max={diff:.4e}")

    all_same = all(
        np.max(np.abs(data["oper/fc"][k] - data["enfo/cf"][k])) == 0
        for k in data["oper/fc"]
    )

    for path in files.values():
        try: os.remove(path)
        except PermissionError: pass
    return all_same


def compare_oper_enfo():
    """对比 oper/fc 和 enfo/cf — 全部 4 个时次."""
    print("\n=== 2. 对比 oper/fc vs enfo/cf (2025-06-15 step=24, 4时次) ===")
    params = ["2t", "msl", "tp", "q", "u", "v"]
    levels = [1000, 500]
    results = {}
    for tv in [0, 6, 12, 18]:
        results[tv] = _compare_one_time("2025-06-15", tv, 24, params, levels)

    print("\n  汇总:")
    for tv, same in results.items():
        print(f"    {tv:02d}Z: {'完全相同' if same else '有差异'}")
    if all(results.values()):
        print("\n  >>> 结论: 4个时次 oper/fc 与 enfo/cf **完全相同** <<<")
    else:
        print("\n  >>> 结论: 存在差异，见上 <<<")


if __name__ == "__main__":
    check_availability()
    compare_oper_enfo()
