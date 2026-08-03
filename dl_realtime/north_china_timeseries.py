"""华北 AR 强度时间序列 0-144h + 柱状图.

AR 强度 5 级 (IVT 250-1500):
  1 级 250-500   蓝
  2 级 500-750   黄
  3 级 750-1000  橙
  4 级 1000-1250 橙红
  5 级 1250+     红

无 AR=0  |  IVT 达标但未识别=透明柱
"""
import os
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import xarray as xr

# ── 区域: 华北 ──
NC_LAT = (35, 45)
NC_LON = (113, 120)

# ── 5 级定义 ──
LEVEL_BOUNDS = [250, 500, 750, 1000, 1250, 9999]
LEVEL_COLORS = {
    0: "#444444",  # 无 AR
    1: "#3498db",  # 蓝
    2: "#f1c40f",  # 黄
    3: "#e67e22",  # 橙
    4: "#d35400",  # 橙红
    5: "#e74c3c",  # 红
    -1: "none",    # 透明 (IVT 达标但未识别)
}
LEVEL_LABELS = ["无", "1级", "2级", "3级", "4级", "5级"]


def _region_mask(lat, lon):
    """华北区域布尔掩膜."""
    return (lat >= NC_LAT[0]) & (lat <= NC_LAT[1]) & \
           (lon >= NC_LON[0]) & (lon <= NC_LON[1])


def _level(max_ivt):
    """IVT 最大值 → 等级 (1-5)."""
    for i, bound in enumerate(LEVEL_BOUNDS):
        if max_ivt < bound:
            return i + 1 if i < 5 else 5
    return 5


def compute_timeseries(ivt_dir_aifs, ivt_dir_ifs, ar_dir_aifs, ar_dir_ifs, fig_path):
    """计算华北时间序列, 输出 PNG 柱状图."""
    records = []  # [{step_h, model, max_ivt, has_ar, level}]

    for model, ivt_d, ar_d in [
        ("IFS", ivt_dir_ifs, ar_dir_ifs),
        ("AIFS", ivt_dir_aifs, ar_dir_aifs),
    ]:
        ivt_path = Path(ivt_d)
        ar_path = Path(ar_d)
        for nc_f in sorted(ivt_path.glob("*_ivt.nc")):
            # 文件名: {date}_{model}_t{time}_step{N}_ivt.nc → step 是倒数第 2 段
            step = int(nc_f.stem.split("_")[-2].replace("step", ""))
            ar_f = ar_path / nc_f.name.replace("_ivt.nc", "_ar.nc")
            if not ar_f.exists():
                continue

            ds_i = xr.open_dataset(nc_f)
            ds_a = xr.open_dataset(ar_f)
            ivt = ds_i["IVT"].values
            plume = ds_a["AR_plume"].values.astype(bool)
            lat = ds_i["latitude"].values
            lon = ds_i["longitude"].values
            ds_i.close()
            ds_a.close()

            mask = _region_mask(lat[:, None], lon[None, :])
            nc_ivt = ivt * mask
            nc_plume = plume & mask

            max_ivt = float(np.nanmax(np.where(mask, ivt, 0)))
            has_ar = nc_plume.any()
            level = _level(max_ivt) if has_ar else (-1 if max_ivt >= 250 else 0)

            records.append({
                "step": step, "model": model,
                "max_ivt": max_ivt, "has_ar": has_ar, "level": level,
            })

    # ── 柱状图 ──
    records.sort(key=lambda r: (r["model"] != "IFS", r["step"]))
    fig, ax = plt.subplots(figsize=(16, 5))
    fig.patch.set_facecolor("#0e1117")
    ax.set_facecolor("#0e1117")

    x = np.arange(len(records))
    colors = [LEVEL_COLORS[r["level"]] for r in records]
    values = [r["max_ivt"] for r in records]
    edgecolor = [c if c != "none" else "#555" for c in colors]

    bars = ax.bar(x, values, color=colors, edgecolor=edgecolor, linewidth=0.5)

    # 透明柱: IVT 达标但未识别
    for i, r in enumerate(records):
        if r["level"] == -1:
            bars[i].set_facecolor("none")
            bars[i].set_hatch("//")

    # X 轴标签: step (每 12h 标一个)
    labels = [f"{r['step']}h\n{r['model']}" if r["step"] % 12 == 0 else ""
              for r in records]
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7, color="#ddd", ha="center")
    ax.tick_params(axis="both", colors="#ddd")

    # Y 轴 + 阈值虚线
    ax.set_ylabel("Max IVT (kg·m⁻¹·s⁻¹)", color="#ddd", fontsize=10)
    ax.set_ylim(0, max(max(values, default=1000) + 200, 1200))
    for lvl, bound in enumerate(LEVEL_BOUNDS[:-1], 1):
        ax.axhline(y=bound, color=LEVEL_COLORS[lvl], linewidth=0.5,
                   linestyle="--", alpha=0.4)
        ax.text(-0.5, bound + 10, f"L{lvl}", color=LEVEL_COLORS[lvl],
                fontsize=7, va="bottom")

    # 图例
    from matplotlib.patches import Patch
    legend = [Patch(facecolor=LEVEL_COLORS[l], edgecolor=LEVEL_COLORS[l],
                    label=LEVEL_LABELS[l]) for l in range(1, 6)]
    legend.append(Patch(facecolor="none", edgecolor="#555", hatch="//",
                        label="达标未识别"))
    ax.legend(handles=legend, loc="upper right", fontsize=8,
              facecolor="#222", edgecolor="#555", labelcolor="#ddd")

    ax.set_title("North China AR Intensity Timeseries (0-144h)",
                 color="white", fontsize=13, fontweight="bold")
    ax.spines["bottom"].set_color("#555")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#555")

    os.makedirs(os.path.dirname(fig_path), exist_ok=True)
    fig.savefig(fig_path, dpi=150, bbox_inches="tight",
                facecolor="#0e1117", edgecolor="none")
    plt.close(fig)


def compute_timeseries_from_realtime(save_dir, fig_path):
    """从实时数据目录提取华北时序."""
    ivt_dir_aifs = os.path.join(save_dir, "ivt", "aifs")
    ivt_dir_ifs = os.path.join(save_dir, "ivt", "ifs")
    ar_dir_aifs = os.path.join(save_dir, "ar", "aifs")
    ar_dir_ifs = os.path.join(save_dir, "ar", "ifs")
    compute_timeseries(ivt_dir_aifs, ivt_dir_ifs, ar_dir_aifs, ar_dir_ifs, fig_path)