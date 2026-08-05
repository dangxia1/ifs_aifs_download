"""巴威个例预报场: 2026-07-09 00z 起报, step 0-72 (每6h, 13张) 东亚图.

流程: 下载(google) → IVT → AR 检测 → 东亚双面板图 (IFS|AIFS)
数据: /shared_data/zongshen/bavi_case/forecast/data/
图:   /shared_data/zongshen/bavi_case/forecast/figures/
标题: 北京时间 MM/DD HH:00 (预报时间 = 起报北京 + step)
并行: 13 进程 (每 step 一个进程: 下载+IVT+AR+作图)

用法: python bavi_forecast.py
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(__file__))
# detect_ar 在 dl_lastmonth_cal_ivt/ 下
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dl_lastmonth_cal_ivt"))
from ecmwf.opendata import Client
from utils import (SINGLE_PARAMS, LEVEL_PARAMS, LEVELS, download_one, verify_grib)
from compute_ivt import compute_ivt
from detect_ar import _load_monthly_thresholds, _seasonal_threshold, detect_ar_from_nc
from visualize_ivt import (REGIONS, CMAP, IVT_LEVELS, _read_ivt, _read_ar,
                           _panel, _read_tp)

# 参数
RUN_DATE = "2026-07-09"
RUN_TIME = 0
DOWNLOAD_STEPS = list(range(0, 97, 6))  # 下载 0~96 (降水差分需要 84/96)
PLOT_STEPS = list(range(0, 73, 6))      # 图 0~72 = 13 张
REGION = "east_asia"
MODELS = {"ifs": "ifs", "aifs-single": "aifs"}
SOURCE = "google"
OUT_DATA = "/shared_data/zongshen/bavi_case/forecast/data"
OUT_FIG = "/shared_data/zongshen/bavi_case/forecast/figures"
THRESHOLD_DIR = "/shared_data_5/ntfs2/liangju/ARIA_Asia_v15/ERA5"

# 7 月 → month_idx 6
THRESHOLDS = _load_monthly_thresholds(THRESHOLD_DIR)
THRESH_2D = _seasonal_threshold(THRESHOLDS, 6)


def _bj_label(step):
    """起报 7/9 00z + step → 北京时间标签."""
    bj = datetime.strptime(RUN_DATE, "%Y-%m-%d") + timedelta(hours=RUN_TIME + 8 + step)
    return f"北京时间 {bj.strftime('%m/%d')} {bj.hour:02d}:00"


def _process_step(step):
    """单 step worker: 下载 ifs+aifs → IVT → AR → 东亚双面板图 (含降水标注)."""
    try:
        plot = step in PLOT_STEPS  # 仅 0~72 画图, 84/96 只下载供差分

        for model, subdir in MODELS.items():
            client = Client(source=SOURCE, model=model)
            gp = f"{OUT_DATA}/{subdir}/step{step}/{RUN_DATE}_{model}_t{RUN_TIME:02d}_step{step}.grib2"
            np_ = gp.replace(".grib2", "_ivt.nc")
            arp = gp.replace(".grib2", "_ar.nc")

            if not os.path.exists(gp):
                os.makedirs(os.path.dirname(gp), exist_ok=True)
                tmp = gp + ".tmp"
                download_one(client, RUN_DATE, RUN_TIME, step, tmp)
                count, missing = verify_grib(tmp)
                if missing:
                    os.remove(tmp)
                    return f"step{step}: 下载校验失败 missing {missing}"
                os.replace(tmp, gp)

            if not os.path.exists(np_):
                compute_ivt(gp, np_)

            if plot and not os.path.exists(arp):
                detect_ar_from_nc(np_, arp, THRESH_2D)

        if not plot:
            return f"step{step:03d} 下载完成 (差分用, 不画图)"

        # 画东亚双面板图 + 降水标注 (未来 12h/24h)
        title = _bj_label(step)
        base_i = f"{OUT_DATA}/ifs/step{step}/{RUN_DATE}_ifs_t{RUN_TIME:02d}_step{step}"
        base_a = f"{OUT_DATA}/aifs/step{step}/{RUN_DATE}_aifs-single_t{RUN_TIME:02d}_step{step}"

        tp_i = _read_tp(base_i + ".grib2")
        tp_a = _read_tp(base_a + ".grib2")
        tp_i12 = _read_tp(f"{OUT_DATA}/ifs/step{step+12}/{RUN_DATE}_ifs_t{RUN_TIME:02d}_step{step+12}.grib2")
        tp_i24 = _read_tp(f"{OUT_DATA}/ifs/step{step+24}/{RUN_DATE}_ifs_t{RUN_TIME:02d}_step{step+24}.grib2")
        tp_a12 = _read_tp(f"{OUT_DATA}/aifs/step{step+12}/{RUN_DATE}_aifs-single_t{RUN_TIME:02d}_step{step+12}.grib2")
        tp_a24 = _read_tp(f"{OUT_DATA}/aifs/step{step+24}/{RUN_DATE}_aifs-single_t{RUN_TIME:02d}_step{step+24}.grib2")

        ivt_i, _, _ = _read_ivt(base_i + "_ivt.nc")
        pl_i, ax_i, _, _, lat2d_i, lon2d_i, cl_i, cn_i = _read_ar(base_i + "_ar.nc")
        ivt_a, _, _ = _read_ivt(base_a + "_ivt.nc")
        pl_a, ax_a, _, _, lat2d_a, lon2d_a, cl_a, cn_a = _read_ar(base_a + "_ar.nc")

        cfg = REGIONS[REGION]
        fig, (axL, axR) = plt.subplots(1, 2, figsize=(16, 9))
        fig.patch.set_facecolor("black")
        cs = _panel(axL, cfg, ivt_i, pl_i, ax_i, lat2d_i, lon2d_i, cl_i, cn_i,
                    f"IFS {title}", REGION, tp_i, tp_i12, tp_i24)
        _panel(axR, cfg, ivt_a, pl_a, ax_a, lat2d_a, lon2d_a, cl_a, cn_a,
               f"AIFS {title}", REGION, tp_a, tp_a12, tp_a24)
        cbar = fig.colorbar(cs, ax=[axL, axR], fraction=0.03,
                            orientation="horizontal", extend="both", pad=0.05)
        cbar.ax.tick_params(labelsize=11, colors="white")
        cbar.ax.set_xlabel("IVT (kg m$^{-1}$ s$^{-1}$)", size=11, color="white")

        os.makedirs(OUT_FIG, exist_ok=True)
        out = f"{OUT_FIG}/east_asia_step{step:03d}.png"
        fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="black")
        plt.close(fig)
        return f"step{step:03d} → {out}"
    except Exception as e:
        return f"step{step:03d} FAIL: {e}"


def _proc_wrapper(step):
    """mp.Process 目标 (非 daemon, FilFinder2D 可再开子进程)."""
    msg = _process_step(step)
    print(f"  {msg}", flush=True)


def main():
    import multiprocessing as mp
    NPROC = min(13, len(DOWNLOAD_STEPS))
    print(f"{len(DOWNLOAD_STEPS)} 个 step (图 {len(PLOT_STEPS)} 张), {NPROC} 进程 → {OUT_DATA} / {OUT_FIG}")
    # 非 daemon 进程 (Pool 的 daemon worker 无法让 FilFinder2D 再开子进程)
    procs = [mp.Process(target=_proc_wrapper, args=(s,)) for s in DOWNLOAD_STEPS]
    for p in procs:
        p.start()
    for p in procs:
        p.join()


if __name__ == "__main__":
    main()