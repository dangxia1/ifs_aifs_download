"""巴威个例 step=0 华北图 (2026-07-09 00z ~ 07-13 18z, 20 时次).

先对比验证 IFS/AIFS step0 的 IVT 差异:
  差异可忽略 → 单图 (只画 IFS)
  有明显差异 → 双面板对比 (IFS|AIFS)
标题: 北京时间 MM/DD HH:00
输出: /shared_data/zongshen/bavi_case/step=0/  (10 进程并行)

用法: python bavi_step0.py
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import xarray as xr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(__file__))
from visualize_ivt import (REGIONS, CMAP, IVT_LEVELS, _read_ivt, _read_ar,
                           _panel)

BASE = "/shared_data/zongshen/ec_monthly_ivt/202607"
OUT = "/shared_data/zongshen/bavi_case/step=0"
REGION = "north_china"
DIFF_THRESHOLD = 1.0  # kg/m/s, 超过则认为双图

# 20 个时次: 7/9 ~ 7/13 每天 00/06/12/18z
TIMES = []
for day in range(9, 14):
    for t in [0, 6, 12, 18]:
        TIMES.append((f"2026-07-{day:02d}", t))


def _bj_label(date_str, utc_hour, step=0):
    """起报时间(UTC) → 北京时间标签. 例: 07/09 08:00"""
    bj = datetime.strptime(date_str, "%Y-%m-%d") + timedelta(hours=utc_hour + 8 + step)
    return f"北京时间 {bj.strftime('%m/%d')} {bj.hour:02d}:00"


def _check_dual(date_str, t):
    """对比 IFS/AIFS step0 IVT 差异, 返回是否双图."""
    ds_i = xr.open_dataset(f"{BASE}/ifs/step0/{date_str}_ifs_t{t:02d}_step0_ivt.nc")
    ds_a = xr.open_dataset(f"{BASE}/aifs/step0/{date_str}_aifs-single_t{t:02d}_step0_ivt.nc")
    diff = float(np.nanmax(np.abs(ds_i["IVT"].values - ds_a["IVT"].values)))
    ds_i.close()
    ds_a.close()
    return diff > DIFF_THRESHOLD, diff


def _draw(args):
    """单时次画图 worker."""
    date_str, t, dual = args
    title = _bj_label(date_str, t)

    ivt_i, _, _ = _read_ivt(f"{BASE}/ifs/step0/{date_str}_ifs_t{t:02d}_step0_ivt.nc")
    pl_i, ax_i, _, _, lat2d_i, lon2d_i, cl_i, cn_i = _read_ar(
        f"{BASE}/ifs/step0/{date_str}_ifs_t{t:02d}_step0_ar.nc")
    cfg = REGIONS[REGION]

    if dual:
        # 双面板 IFS|AIFS
        ivt_a, _, _ = _read_ivt(f"{BASE}/aifs/step0/{date_str}_aifs-single_t{t:02d}_step0_ivt.nc")
        pl_a, ax_a, _, _, lat2d_a, lon2d_a, cl_a, cn_a = _read_ar(
            f"{BASE}/aifs/step0/{date_str}_aifs-single_t{t:02d}_step0_ar.nc")
        fig, (axL, axR) = plt.subplots(1, 2, figsize=(16, 9))
        fig.patch.set_facecolor("black")
        cs = _panel(axL, cfg, ivt_i, pl_i, ax_i, lat2d_i, lon2d_i, cl_i, cn_i,
                    f"IFS {title}", REGION)
        _panel(axR, cfg, ivt_a, pl_a, ax_a, lat2d_a, lon2d_a, cl_a, cn_a,
               f"AIFS {title}", REGION)
        cbar_ax = [axL, axR]
    else:
        # 单面板 (IFS)
        fig, ax = plt.subplots(figsize=(9, 9))
        fig.patch.set_facecolor("black")
        cs = _panel(ax, cfg, ivt_i, pl_i, ax_i, lat2d_i, lon2d_i, cl_i, cn_i,
                    f"IFS {title}", REGION)
        cbar_ax = [ax]

    cbar = fig.colorbar(cs, ax=cbar_ax, fraction=0.03, orientation="horizontal",
                        extend="both", pad=0.05)
    cbar.ax.tick_params(labelsize=11, colors="white")
    cbar.ax.set_xlabel("IVT (kg m$^{-1}$ s$^{-1}$)", size=11, color="white")

    os.makedirs(OUT, exist_ok=True)
    out = f"{OUT}/{date_str.replace('-', '')}_{t:02d}z.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="black")
    plt.close(fig)
    return f"saved {out} (dual={dual})"


def main():
    # 1. 先对比 7/9 00z 的差异, 决定全部 20 张用单图还是双图
    dual, diff = _check_dual("2026-07-09", 0)
    print(f"IFS/AIFS step0 IVT 最大差异: {diff:.4f} kg/m/s → "
          f"{'双面板' if dual else '单图(IFS)'}")
    # 稳妥: 再抽查 7/13 12z
    dual2, diff2 = _check_dual("2026-07-13", 12)
    print(f"抽查 7/13 12z: {diff2:.4f} → {'双面板' if dual2 else '单图'}")
    dual = dual or dual2

    # 2. 20 时次并行画图
    tasks = [(d, t, dual) for d, t in TIMES]
    import multiprocessing as mp
    NPROC = min(10, len(tasks))
    print(f"{len(tasks)} 张图, {NPROC} 进程 → {OUT}")
    with mp.Pool(processes=NPROC) as pool:
        for msg in pool.imap_unordered(_draw, tasks):
            print(f"  {msg}")


if __name__ == "__main__":
    main()