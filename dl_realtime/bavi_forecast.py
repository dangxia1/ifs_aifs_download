"""巴威个例预报场: 2026-07-09 00z 起报, step 0-72 (每6h, 13张) 东亚图.

流程: 下载(google) → IVT → AR 检测 → 东亚双面板图 (IFS|AIFS)
数据: /shared_data/zongshen/ec_realtime/bavi_forecast/ (与图分开)
图:   /shared_data/zongshen/bavi_case/bavi_forecast/
标题/布局: 与 dl_realtime east_asia 模板一致 (模型名 + YYYY/MM/DD HH:00, 上下)
并行: 13 进程 (每 step 一个进程: 下载+IVT+AR+作图)

用法: python bavi_forecast.py
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
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
from visualize_ivt import (REGIONS, CMAP, IVT_LEVELS, MODEL_NAMES,
                           _read_ivt, _read_ar, _panel, _read_tp,
                           _compute_axis_center, AXIS_MIN_LEN,
                           _valid_time_from_path)

# 参数
RUN_DATE = "2026-07-09"
RUN_TIME = 0
DOWNLOAD_STEPS = list(range(0, 97, 6))  # 下载 0~96 (降水差分需要 84/96)
PLOT_STEPS = list(range(0, 73, 6))      # 图 0~72 = 13 张
REGION = "east_asia"
MODELS = {"ifs": "ifs", "aifs-single": "aifs"}
SOURCE = "google"
OUT_DATA = "/shared_data/zongshen/ec_realtime/bavi_forecast"   # 数据 (与实时数据同盘)
OUT_FIG = "/shared_data/zongshen/bavi_case/bavi_forecast"      # 图
THRESHOLD_DIR = "/shared_data_5/ntfs2/liangju/ARIA_Asia_v15/ERA5"

# 7 月 → month_idx 6
THRESHOLDS = _load_monthly_thresholds(THRESHOLD_DIR)
THRESH_2D = _seasonal_threshold(THRESHOLDS, 6)


def _process_step(step):
    """单 step worker (阶段1): 下载 ifs+aifs → IVT → AR (不画图, 平滑在阶段2)."""
    try:
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

            # 仅画图时次 (0~72) 需要 AR; 84/96 只用于降水差分, 跳过 AR 省时间
            if step in PLOT_STEPS and not os.path.exists(arp):
                detect_ar_from_nc(np_, arp, THRESH_2D)

        return f"step{step:03d} 数据就绪"
    except Exception as e:
        return f"step{step:03d} FAIL: {e}"


def _plot_worker(args):
    """阶段2 画图 worker: 东亚双面板 (上下, 同 dl_realtime 模板) + 降水标注 + 平滑 plume."""
    step, pl_i_s, pl_a_s = args
    try:
        base_i = f"{OUT_DATA}/ifs/step{step}/{RUN_DATE}_ifs_t{RUN_TIME:02d}_step{step}"
        base_a = f"{OUT_DATA}/aifs/step{step}/{RUN_DATE}_aifs-single_t{RUN_TIME:02d}_step{step}"
        # 标题格式与 dl_realtime 一致: 模型名 + YYYY/MM/DD HH:00 (预报时间)
        title_i = f"{MODEL_NAMES['ifs']} {_valid_time_from_path(base_i + '_ivt.nc', step)}"
        title_a = f"{MODEL_NAMES['aifs-single']} {_valid_time_from_path(base_a + '_ivt.nc', step)}"

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
        if pl_i_s is not None and not np.array_equal(pl_i, pl_i_s):
            # 平滑/恢复改变 plume → 重算轴; 未变 → 保留 _ar.nc 老师原版轴 (2026-08-06)
            pl_i = pl_i_s
            ax_i, cl_i, cn_i = _compute_axis_center(pl_i, ivt_i, AXIS_MIN_LEN[REGION])
        if pl_a_s is not None and not np.array_equal(pl_a, pl_a_s):
            pl_a = pl_a_s
            ax_a, cl_a, cn_a = _compute_axis_center(pl_a, ivt_a, AXIS_MIN_LEN[REGION])

        cfg = REGIONS[REGION]
        # 东亚: 上下布局 (IFS 上 / AIFS 下), 同 dl_realtime visualize_one_step
        fig, (axT, axB) = plt.subplots(2, 1, figsize=(16, 9))
        fig.patch.set_facecolor("black")
        cs = _panel(axT, cfg, ivt_i, pl_i, ax_i, lat2d_i, lon2d_i, cl_i, cn_i,
                    title_i, REGION, tp_i, tp_i12, tp_i24)
        _panel(axB, cfg, ivt_a, pl_a, ax_a, lat2d_a, lon2d_a, cl_a, cn_a,
               title_a, REGION, tp_a, tp_a12, tp_a24)
        cbar = fig.colorbar(cs, ax=[axT, axB], fraction=0.03,
                            orientation="horizontal", extend="both", pad=0.05,
                            shrink=0.55, anchor=(0.5, 0.0))
        cbar.ax.tick_params(labelsize=10, colors="white")
        cbar.ax.set_xlabel("IVT (kg m$^{-1}$ s$^{-1}$)", size=12, color="white",
                           loc="left")

        os.makedirs(OUT_FIG, exist_ok=True)
        out = f"{OUT_FIG}/east_asia_step{step:03d}.png"
        fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="black")
        plt.close(fig)
        return f"step{step:03d} → {out}"
    except Exception as e:
        return f"step{step:03d} 画图 FAIL: {e}"


def _proc_wrapper(step):
    """mp.Process 目标 (非 daemon, FilFinder2D 可再开子进程)."""
    msg = _process_step(step)
    print(f"  {msg}", flush=True)


def main():
    import multiprocessing as mp

    # 阶段 1: 并行下载 + IVT + AR (13 进程, 非 daemon 供 FilFinder2D)
    print(f"=== 阶段1: 数据 ({len(DOWNLOAD_STEPS)} 个 step, 13 进程) ===")
    procs = [mp.Process(target=_proc_wrapper, args=(s,)) for s in DOWNLOAD_STEPS]
    for p in procs:
        p.start()
    for p in procs:
        p.join()

    # 阶段 2: AR 时间平滑 (方案 B) + 并行画图
    print("=== 阶段2: AR 平滑 + 画图 ===")
    from visualize_ivt import _smooth_ar_temporal

    def _load_series(model_dir, model_tag):
        plumes, ivts, axes, lat2d, lon2d = [], [], [], None, None
        for s in PLOT_STEPS:
            base = f"{OUT_DATA}/{model_dir}/step{s}/{RUN_DATE}_{model_tag}_t{RUN_TIME:02d}_step{s}"
            pl, ax_, _, _, lat2d_, lon2d_, _, _ = _read_ar(base + "_ar.nc")
            ivt, _, _ = _read_ivt(base + "_ivt.nc")
            plumes.append(pl)
            ivts.append(ivt)
            axes.append(ax_)
            lat2d, lon2d = lat2d_, lon2d_
        smooth = _smooth_ar_temporal(plumes, ivts, axes=axes,
                                     lat2d=lat2d, lon2d=lon2d)
        return {s: sm for s, sm in zip(PLOT_STEPS, smooth)}

    smooth_i = _load_series("ifs", "ifs")
    smooth_a = _load_series("aifs", "aifs-single")

    tasks = [(s, smooth_i.get(s), smooth_a.get(s)) for s in PLOT_STEPS]
    NPROC = min(13, len(tasks))
    print(f"{len(tasks)} 张图, {NPROC} 进程 → {OUT_FIG}")
    with mp.Pool(processes=NPROC) as pool:
        for msg in pool.imap_unordered(_plot_worker, tasks):
            print(f"  {msg}")


if __name__ == "__main__":
    main()