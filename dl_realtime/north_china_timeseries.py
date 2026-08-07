"""北京地区 AR 强度时间序列 0-144h + 柱状图 (IFS/AIFS 双子图).

AR 强度 5 级 (IVT 250-1500):
  1 级 250-500   蓝
  2 级 500-750   黄
  3 级 750-1000  橙
  4 级 1000-1250 橙红
  5 级 1250+     红

时序经过 AR 时间平滑 (高斯投票 + 双向恢复), 与可视化图一致.
无大气河 (IVT<250) = 灰柱 | 未识别出大气河 (IVT≥250 但无 AR) = 不画柱 (留空, 网页图例有说明)
柱高 = AR 区域 IVT 积分/面积 (平均 IVT); 柱色等级按该平均值定 (2026-08-06 老师要求).
"""
import os
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import xarray as xr

# 中文字体 (自动生成 fonts/, 不依赖系统字体)
from make_font import ensure_font
_FONT_CANDIDATES = [
    os.environ.get("FONT_DIR", ""),
    "/shared_data/zongshen/fonts/NotoSansCJKsc-Regular.otf",
    os.path.join(os.path.dirname(__file__), "fonts", "NotoSansCJKsc-Regular.otf"),
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/msyh.ttc",
]
_FONT_NAME = "Noto Sans CJK SC"
ensure_font()  # 自动生成子集字体 (幂等)
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

# ── 区域: 北京地区 (北京 116.4E, 39.9N 为中心 ±1.5°, 2026-08-06 由华北缩小) ──
NC_LAT = (38.5, 41.5)
NC_LON = (115, 118)

# ── 5 级定义 ──
LEVEL_BOUNDS = [250, 500, 750, 1000, 1250, 1500]
LEVEL_COLORS = {
    0: "#444444",  # 无 AR
    1: "#3498db",  # 蓝
    2: "#f1c40f",  # 黄
    3: "#e67e22",  # 橙
    4: "#d35400",  # 橙红
    5: "#e74c3c",  # 红
    -1: "#444444",  # 未识别出大气河 (IVT≥250 但无 AR): 不画柱, 颜色仅兜底
}
LEVEL_LABELS = ["1级", "2级", "3级", "4级", "5级"]


def _region_mask(lat, lon):
    """北京地区布尔掩膜."""
    return (lat >= NC_LAT[0]) & (lat <= NC_LAT[1]) & \
           (lon >= NC_LON[0]) & (lon <= NC_LON[1])


def _level(ivt_value):
    """IVT 数值 → 等级 (1-5). 2026-08-06: 柱色按平均 IVT 定 (传 avg_ivt)."""
    for i, bound in enumerate(LEVEL_BOUNDS):
        if ivt_value < bound:
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
    """计算北京地区时间序列, 输出 IFS/AIFS 双子图 PNG.

    时序预读全部时次 → _smooth_ar_temporal (高斯投票 + 双向恢复),
    与可视化图用同一套平滑结果——否则恢复出的大气河不会出现在时序图上.
    未识别出大气河 (IVT≥250 但平滑后无 AR) 的时次 avg_ivt=NaN → 不画柱 (留空).
    """
    from visualize_ivt import _smooth_ar_temporal
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

        # 预读全时次 (按 step 升序): 文件名 {date}_{model}_t{time}_step{N}_ivt.nc
        entries = []  # (step, ivt, plume, axis, lat, lon)
        for nc_f in files:
            step = int(nc_f.stem.split("_")[-2].replace("step", ""))
            ar_f = ar_path / nc_f.name.replace("_ivt.nc", "_ar.nc")
            if not ar_f.exists():
                continue
            ds_i = xr.open_dataset(nc_f)
            ds_a = xr.open_dataset(ar_f)
            ivt = ds_i["IVT"].values
            plume = ds_a["AR_plume"].values.astype(bool)
            axis = ds_a["AR_axis"].values.astype(bool)
            lat = ds_i["latitude"].values
            lon = ds_i["longitude"].values
            ds_i.close()
            ds_a.close()
            entries.append((step, ivt, plume, axis, lat, lon))
        entries.sort(key=lambda e: e[0])
        if not entries:
            continue

        # 时间平滑 (与 visualize_ivt 的 meshgrid 顺序一致: lon2d=X, lat2d=Y)
        plumes = [e[2] for e in entries]
        ivts = [e[1] for e in entries]
        axes = [e[3] for e in entries]
        lon2d, lat2d = np.meshgrid(entries[0][5], entries[0][4])
        smooth = _smooth_ar_temporal(plumes, ivts, axes=axes,
                                     lat2d=lat2d, lon2d=lon2d)

        for (step, ivt, plume, axis, lat, lon), plume_s in zip(entries, smooth):
            mask = _region_mask(lat[:, None], lon[None, :])
            max_ivt = float(np.nanmax(np.where(mask, ivt, 0)))
            has_ar = (plume_s & mask).any()
            # 柱高 = AR 羽流内 IVT 积分/面积 (面积平均); 柱色等级按该平均值定
            # (2026-08-06 老师要求). 不除以整个区域面积——非 AR 区 IVT 很低会稀释.
            if has_ar:
                avg_ivt = float(np.nanmean(ivt[plume_s & mask]))
                level = _level(avg_ivt)
            else:
                avg_ivt = float("nan") if max_ivt >= 250 else 0.0
                # 未识别出大气河 (IVT≥250 但无 AR): 不画柱 (留空)
                level = -1 if max_ivt >= 250 else 0

            records.append({
                "step": step, "model": model,
                "max_ivt": max_ivt, "avg_ivt": avg_ivt,
                "has_ar": has_ar, "level": level,
            })

    # ── 双子图: IFS 上 / AIFS 下 ── (hspace=0.4 拉开上下间距, 老师要求 2026-08-07)
    from visualize_ivt import MODEL_NAMES
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 8),
                                   gridspec_kw={"hspace": 0.4})
    fig.patch.set_facecolor("#0e1117")

    y_ticks = [250, 500, 750, 1000, 1250, 1500]

    for ax, model in [(ax1, "ifs"), (ax2, "aifs-single")]:
        ax.set_facecolor("#0e1117")
        recs = sorted([r for r in records if r["model"] ==
                       ("IFS" if model == "ifs" else "AIFS")],
                      key=lambda r: r["step"])
        if not recs:
            ax.set_visible(False)
            continue

        x = np.arange(len(recs))
        colors = [LEVEL_COLORS[r["level"]] for r in recs]
        values = [r["avg_ivt"] for r in recs]  # NaN = 未识别出大气河 → 不画柱

        bars = ax.bar(x, values, color=colors,
                      edgecolor=colors, linewidth=0.5)

        # X 轴标签 (每 12h 标一个)
        labels = [f"{r['step']}h" if r["step"] % 12 == 0 else "" for r in recs]
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=14, color="#ddd")
        ax.tick_params(axis="y", labelsize=14, colors="#ddd")

        # Y 轴: 250-1500 刻度
        ax.set_ylim(0, 1650)
        ax.set_yticks(y_ticks)
        ax.set_yticklabels([str(v) for v in y_ticks], fontsize=14, color="#ddd")

        # 等级虚线
        for lvl, bound in enumerate(LEVEL_BOUNDS[:-1], 1):
            ax.axhline(y=bound, color=LEVEL_COLORS[lvl], linewidth=0.6,
                       linestyle="--", alpha=0.5)

        model_name = MODEL_NAMES.get(model, model.upper())
        ax.set_title(f"{model_name} | 起报 {run_time} · 北京地区 大气河 平均 IVT 强度演变 (0-144h)",
                     color="white", fontsize=16, fontweight="bold", pad=5)
        ax.spines["bottom"].set_color("#555")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#555")

    # 图例: 图内左上角 (老师要求 2026-08-06: 不占纵轴左侧空间, 不与纵轴相交;
    # 标题 "AR 强度" 用白色, 整体放大)
    from matplotlib.patches import Patch
    # 图例只留 5 级 AR 强度 (用户要求: 无大气河/未识别不放图例, 网页下方有说明)
    legend = [Patch(facecolor=LEVEL_COLORS[l], edgecolor=LEVEL_COLORS[l],
                    label=LEVEL_LABELS[l - 1]) for l in range(1, 6)]
    leg = ax2.legend(handles=legend, loc="upper left",
                     bbox_to_anchor=(0.012, 0.985), bbox_transform=ax2.transAxes,
                     fontsize=16, facecolor="#222", edgecolor="#555",
                     labelcolor="#ddd", title="AR 强度", title_fontsize=18)
    leg.get_title().set_color("white")  # "AR 强度" 4 字用白色 (老师要求)

    ax2.set_xlabel("step (h)", color="#ddd", fontsize=18)
    fig.text(0.012, 0.5, "平均 IVT (kg·m⁻¹·s⁻¹)", rotation=90,
             color="#ddd", fontsize=16, va="center")

    os.makedirs(os.path.dirname(fig_path), exist_ok=True)
    fig.savefig(fig_path, dpi=150, bbox_inches="tight",
                facecolor="#0e1117", edgecolor="none")
    plt.close(fig)


def compute_timeseries_from_realtime(save_dir, fig_path):
    """从实时数据目录提取北京地区时序."""
    ivt_dir_aifs = os.path.join(save_dir, "ivt", "aifs")
    ivt_dir_ifs = os.path.join(save_dir, "ivt", "ifs")
    ar_dir_aifs = os.path.join(save_dir, "ar", "aifs")
    ar_dir_ifs = os.path.join(save_dir, "ar", "ifs")
    compute_timeseries(ivt_dir_aifs, ivt_dir_ifs, ar_dir_aifs, ar_dir_ifs, fig_path)
