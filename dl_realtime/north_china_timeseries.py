"""华北 AR 强度时间序列 0-144h + 柱状图 (IFS/AIFS 双子图).

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
import matplotlib.font_manager as fm
import xarray as xr

# 中文字体 (最稳妥: 项目内置 fonts/, 随包分发)
_FONT_CANDIDATES = [
    os.path.join(os.path.dirname(__file__), "fonts", "NotoSansCJK-Regular.ttc"),
    os.path.join(os.path.dirname(__file__), "fonts", "NotoSansCJKsc-Regular.otf"),
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/msyh.ttc",
]
_FONT_NAME = "Noto Sans CJK SC"
for _fp in _FONT_CANDIDATES:
    if os.path.exists(_fp):
        try:
            fm.fontManager.addfont(_fp)
            fm._load_fontmanager(try_read_cache=False)  # 重建缓存
            fm.findfont(_FONT_NAME)  # 验证
            break
        except Exception:
            continue
plt.rcParams["font.sans-serif"] = [
    "Noto Sans CJK SC", "SimHei", "Microsoft YaHei",
    "WenQuanYi Zen Hei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

# ── 区域: 华北 ──
NC_LAT = (35, 45)
NC_LON = (113, 120)

# ── 5 级定义 ──
LEVEL_BOUNDS = [250, 500, 750, 1000, 1250, 1500]
LEVEL_COLORS = {
    0: "#444444",  # 无 AR
    1: "#3498db",  # 蓝
    2: "#f1c40f",  # 黄
    3: "#e67e22",  # 橙
    4: "#d35400",  # 橙红
    5: "#e74c3c",  # 红
    -1: "none",    # 透明 (IVT 达标但未识别)
}
LEVEL_LABELS = ["1级", "2级", "3级", "4级", "5级"]


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


def _run_time_bj(first_nc):
    """从 IVT 文件名解析起报时间 → 北京时间. 例: 08/04 02:00"""
    from datetime import datetime, timedelta
    parts = Path(first_nc).stem.split("_")
    if len(parts) >= 3:
        date, t_tag = parts[0], parts[2]
        utc_hour = int(t_tag[1:])
        bj = datetime.strptime(date, "%Y-%m-%d") + timedelta(hours=utc_hour + 8)
        return f"{bj.strftime('%m/%d')} {bj.hour:02d}:00"
    return ""


def compute_timeseries(ivt_dir_aifs, ivt_dir_ifs, ar_dir_aifs, ar_dir_ifs, fig_path):
    """计算华北时间序列, 输出 IFS/AIFS 双子图 PNG."""
    records = []  # [{step_h, model, max_ivt, has_ar, level}]
    run_time = ""

    for model, ivt_d, ar_d in [
        ("IFS", ivt_dir_ifs, ar_dir_ifs),
        ("AIFS", ivt_dir_aifs, ar_dir_aifs),
    ]:
        ivt_path = Path(ivt_d)
        ar_path = Path(ar_d)
        files = sorted(ivt_path.glob("*_ivt.nc"))
        if not run_time and files:
            run_time = _run_time_bj(files[0])

        for nc_f in files:
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
            max_ivt = float(np.nanmax(np.where(mask, ivt, 0)))
            has_ar = (plume & mask).any()
            level = _level(max_ivt) if has_ar else (-1 if max_ivt >= 250 else 0)

            records.append({
                "step": step, "model": model,
                "max_ivt": max_ivt, "has_ar": has_ar, "level": level,
            })

    # ── 双子图: IFS 上 / AIFS 下 ──
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 8))
    fig.patch.set_facecolor("#0e1117")

    y_ticks = [250, 500, 750, 1000, 1250, 1500]

    for ax, model in [(ax1, "IFS"), (ax2, "AIFS")]:
        ax.set_facecolor("#0e1117")
        recs = sorted([r for r in records if r["model"] == model],
                      key=lambda r: r["step"])
        if not recs:
            ax.set_visible(False)
            continue

        x = np.arange(len(recs))
        colors = [LEVEL_COLORS[r["level"]] for r in recs]
        values = [r["max_ivt"] for r in recs]

        bars = ax.bar(x, values, color=colors,
                      edgecolor=[c if c != "none" else "#555" for c in colors],
                      linewidth=0.5)

        # 透明柱: IVT 达标但未识别
        for i, r in enumerate(recs):
            if r["level"] == -1:
                bars[i].set_facecolor("none")
                bars[i].set_hatch("//")

        # X 轴标签 (每 12h 标一个)
        labels = [f"{r['step']}h" if r["step"] % 12 == 0 else "" for r in recs]
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=8, color="#ddd")
        ax.tick_params(axis="y", colors="#ddd")

        # Y 轴: 250-1500 刻度
        ax.set_ylim(0, 1650)
        ax.set_yticks(y_ticks)
        ax.set_yticklabels([str(v) for v in y_ticks], fontsize=8, color="#ddd")

        # 等级虚线
        for lvl, bound in enumerate(LEVEL_BOUNDS[:-1], 1):
            ax.axhline(y=bound, color=LEVEL_COLORS[lvl], linewidth=0.6,
                       linestyle="--", alpha=0.5)

        ax.set_title(f"{model} | 起报 {run_time} · 华北 IVT 强度演变 (0-144h)",
                     color="white", fontsize=12, fontweight="bold", pad=5)
        ax.spines["bottom"].set_color("#555")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#555")

    # 图例 (共用一个, 放右上)
    from matplotlib.patches import Patch
    legend = [Patch(facecolor=LEVEL_COLORS[l], edgecolor=LEVEL_COLORS[l],
                    label=LEVEL_LABELS[l - 1]) for l in range(1, 6)]
    legend.append(Patch(facecolor="none", edgecolor="#555", hatch="//",
                        label="达标未识别"))
    ax2.legend(handles=legend, loc="upper right", fontsize=8,
               facecolor="#222", edgecolor="#555", labelcolor="#ddd")

    ax2.set_xlabel("step (h)", color="#ddd", fontsize=10)
    fig.text(0.02, 0.5, "Max IVT (kg·m⁻¹·s⁻¹)", rotation=90,
             color="#ddd", fontsize=10, va="center")

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
