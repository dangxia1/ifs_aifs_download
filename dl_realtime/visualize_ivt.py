"""IVT + AR 可视化 — 双面板 (左 IFS 右 AIFS), PNG 输出.

每个区域 25 张图 (step 0-144h, 6h 步长).
"""
import logging
import os
import warnings
warnings.filterwarnings("ignore")  # 屏蔽 Basemap/FilFinder 等无关警告
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.font_manager as fm
import numpy as np
import xarray as xr
from mpl_toolkits.basemap import Basemap

# ── 中文字体 (自动生成 fonts/, 不依赖系统字体) ──
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
            # 关键: 重建字体缓存, 否则 findfont 找不到刚注册的字体
            fm._load_fontmanager(try_read_cache=False)
            fm.findfont(_FONT_NAME)  # 验证可找到, 找不到会抛异常
            break
        except Exception:
            continue
plt.rcParams["font.sans-serif"] = [
    "Noto Sans CJK SC", "SimHei", "Microsoft YaHei",
    "WenQuanYi Zen Hei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

# ── 区域 ────────────────────────────────────────────────
REGIONS = {
    "global": {
        "lat_0": -88, "lat_1": 88, "lon_0": -179, "lon_1": 180,
        "parallels": np.arange(-80., 81., 30.),
        "meridians": np.arange(-180., 181., 30.),
        "title": "Global",
    },
    "east_asia": {
        "lat_0": 10, "lat_1": 50, "lon_0": 105, "lon_1": 150,
        "parallels": np.arange(10., 51., 10.),
        "meridians": np.arange(105., 151., 10.),
        "title": "East Asia",
    },
    "north_china": {
        "lat_0": 35, "lat_1": 45, "lon_0": 113, "lon_1": 120,
        "parallels": np.arange(35., 46., 2.),
        "meridians": np.arange(113., 121., 2.),
        "title": "North China",
    },
}

BJ_LON, BJ_LAT = 116.4, 39.9
AXIS_COLOR = "purple"

# ── AR 强度 5 级 (导师要求: IVT 250-1500, 蓝/黄/橙/橙红/红) ──
IVT_LEVELS = [250, 500, 750, 1000, 1250, 1500]
LEVEL_COLORS = ["#3498db", "#f1c40f", "#e67e22", "#d35400", "#e74c3c"]
CMAP = mcolors.ListedColormap(LEVEL_COLORS, name="ar_5level")


def _read_ar(ar_path):
    ds = xr.open_dataset(ar_path)
    plume = ds["AR_plume"].values.astype(bool)
    axis_ = ds["AR_axis"].values.astype(bool)
    center = ds["AR_center"].values
    lat = ds["latitude"].values
    lon = ds["longitude"].values
    ds.close()
    lon[lon > 180] -= 360
    idx = np.argsort(lon)
    lon2d, lat2d = np.meshgrid(lon[idx], lat)
    cent_lats, cent_lons = np.where(center[:, idx] > 0)
    return (plume[:, idx], axis_[:, idx],
            lat, lon[idx], lat2d, lon2d,
            cent_lats, cent_lons)


def _read_ivt(nc_path):
    ds = xr.open_dataset(nc_path)
    ivt = ds["IVT"].values
    lat = ds["latitude"].values
    lon = ds["longitude"].values
    ds.close()
    # 经度统一为 -180~180 并排序 (ECMWF 原始 0~360, 单调递增 → 转换后仍单调,
    # argsort 恒等, 排序安全; 若文件已是 -180~180 同样安全)
    lon[lon > 180] -= 360
    idx = np.argsort(lon)
    return (ivt[:, idx], lat, lon[idx])


def _panel(ax, cfg, ivt, plume, axis_, lat2d, lon2d, ce_lats, ce_lons,
           title, region_name):
    """画单个模型面板 (照搬导师 Basemap 风格)."""
    ax.set_facecolor("black")

    m = Basemap(projection="cyl", area_thresh=10., resolution="l",
                llcrnrlat=cfg["lat_0"], urcrnrlat=cfg["lat_1"],
                llcrnrlon=cfg["lon_0"], urcrnrlon=cfg["lon_1"],
                lat_ts=14.5, ax=ax)

    # 全分辨率 bluemarble, 每张图独立 warp (无缓存, 路径统一, 无颠倒/拼接 bug)
    m.bluemarble(zorder=0)

    x, y = m(lon2d, lat2d)

    # contourf 第 1 层: 全 IVT alpha=0.2
    ax.contourf(x, y, ivt, levels=IVT_LEVELS, extend="max",
                cmap=CMAP, alpha=0.2)

    # contour 薄黑线叠加 (参照导师)
    ax.contour(x, y, ivt, levels=IVT_LEVELS, colors="black", linewidths=0.1)

    # contourf 第 2 层: AR 内 IVT alpha=1
    ivt_ar = np.where(plume, ivt, np.nan)
    cs = ax.contourf(x, y, ivt_ar, levels=IVT_LEVELS, extend="max",
                     cmap=CMAP)

    # AR 河轴
    y_a, x_a = np.where(axis_)
    if len(y_a) > 0:
        x_axis, y_axis = m(lon2d[y_a, x_a], lat2d[y_a, x_a])
        ax.scatter(x_axis, y_axis, c=AXIS_COLOR, s=0.2)

    # AR 质心 (红色十字)
    if len(ce_lats) > 0:
        x_cent, y_cent = m(lon2d[ce_lats, ce_lons], lat2d[ce_lats, ce_lons])
        ax.scatter(x_cent, y_cent, marker="+", c="red", s=100, linewidths=1.)

    # 海岸线 + 经纬网
    m.drawcoastlines(color="grey", linewidth=0.2, zorder=0)
    m.drawparallels(cfg["parallels"], labels=[1, 0, 0, 0],
                    fontsize=10, color="white", textcolor="white", linewidth=0.1)
    m.drawmeridians(cfg["meridians"], labels=[0, 0, 0, 1],
                    fontsize=10, color="white", textcolor="white", linewidth=0.1)

    # 北京红星
    if region_name == "north_china":
        bx, by = m(BJ_LON, BJ_LAT)
        ax.plot(bx, by, marker="*", color="red", markersize=14, zorder=6)

    # 子标题
    ax.set_title(title, fontsize=14, color="white", pad=6)
    ax.tick_params(axis="both", colors="white")
    return cs


def _valid_time_from_path(path, step_h):
    """预报时间 = 起报(北京时间 UTC+8) + step 小时. 例: 起报 06z + step6 → 2026/08/04 20:00"""
    from datetime import datetime, timedelta
    stem = Path(path).stem
    parts = stem.split("_")
    if len(parts) >= 3:
        date, t_tag = parts[0], parts[2]
        utc_hour = int(t_tag[1:])
        bj = datetime.strptime(date, "%Y-%m-%d") + timedelta(hours=utc_hour + 8)
        valid = bj + timedelta(hours=step_h)
        return f"{valid.strftime('%Y/%m/%d')} {valid.hour:02d}:00"
    return ""


def visualize_one_step(ivt_ifs, ar_ifs, ivt_aifs, ar_aifs, png_path, region_name):
    """双面板: 全球上下 (IFS上/AIFS下), 其他左右; 单 step → 单 PNG."""
    cfg = REGIONS[region_name]

    ivt_i, lat1d_i, lon1d_i = _read_ivt(ivt_ifs)
    pl_i, ax_i, _, _, lat2d_i, lon2d_i, cl_i, cn_i = _read_ar(ar_ifs)
    ivt_a, lat1d_a, lon1d_a = _read_ivt(ivt_aifs)
    pl_a, ax_a, _, _, lat2d_a, lon2d_a, cl_a, cn_a = _read_ar(ar_aifs)

    if region_name == "global":
        fig, (axT, axB) = plt.subplots(2, 1, figsize=(16, 9))
    else:
        fig, (axL, axR) = plt.subplots(1, 2, figsize=(16, 9))
    fig.patch.set_facecolor("black")

    step_str = str(Path(png_path).stem).split("_")[-1]  # stepN
    step_h = int(step_str.replace("step", ""))
    valid_time = _valid_time_from_path(ivt_ifs, step_h)

    if region_name == "global":
        cs = _panel(axT, cfg, ivt_i, pl_i, ax_i, lat2d_i, lon2d_i, cl_i, cn_i,
                    f"IFS {valid_time}", region_name)
        _panel(axB, cfg, ivt_a, pl_a, ax_a, lat2d_a, lon2d_a, cl_a, cn_a,
               f"AIFS {valid_time}", region_name)
        cbar_ax = [axT, axB]
    else:
        cs = _panel(axL, cfg, ivt_i, pl_i, ax_i, lat2d_i, lon2d_i, cl_i, cn_i,
                    f"IFS {valid_time}", region_name)
        _panel(axR, cfg, ivt_a, pl_a, ax_a, lat2d_a, lon2d_a, cl_a, cn_a,
               f"AIFS {valid_time}", region_name)
        cbar_ax = [axL, axR]

    # 5 级色标
    cbar = fig.colorbar(cs, ax=cbar_ax, fraction=0.03,
                        orientation="horizontal", extend="both", pad=0.05)
    cbar.ax.tick_params(labelsize=11, colors="white")
    cbar.ax.set_xlabel("IVT (kg m$^{-1}$ s$^{-1}$) — 蓝<500 黄<750 橙<1000 橙红<1250 红≥1250",
                       size=11, color="white")

    os.makedirs(os.path.dirname(png_path), exist_ok=True)
    fig.savefig(png_path, dpi=150, bbox_inches="tight", facecolor="black")
    plt.close(fig)
    return os.path.getsize(png_path) / 1024


def visualize_all(save_dir, model_dirs):
    """对每个区域生成 25 张双面板 PNG, 每次运行覆盖旧图."""
    import shutil
    sp = Path(save_dir)
    fig_root = sp / "figures"
    if fig_root.exists():
        shutil.rmtree(fig_root)

    # 目录: figures/{region}/step{N}.png
    ivt_dir = {subdir: sp / "ivt" / subdir for subdir in model_dirs.values()}
    ar_dir = {subdir: sp / "ar" / subdir for subdir in model_dirs.values()}
    sub_ifs = model_dirs["ifs"]
    sub_aifs = model_dirs["aifs-single"]

    total = 0
    for region_name in REGIONS:
        out_dir = fig_root / region_name
        out_dir.mkdir(parents=True, exist_ok=True)

        # 按 step 匹配 IFS/AIFS 文件
        ivt_files_ifs = sorted(ivt_dir[sub_ifs].glob("*_ivt.nc"))
        for ivt_i in ivt_files_ifs:
            step_tag = ivt_i.name.replace("_ivt.nc", "")  # {date}_{model}_t{time}_step{N}
            # 取 step 部分
            step_n = step_tag.rsplit("_", 1)[-1]  # step24

            ar_i = ar_dir[sub_ifs] / ivt_i.name.replace("_ivt.nc", "_ar.nc")
            ivt_a = ivt_dir[sub_aifs] / ivt_i.name.replace("_ifs_", "_aifs-single_")
            ar_a = ar_dir[sub_aifs] / ivt_a.name.replace("_ivt.nc", "_ar.nc")

            if not (ar_i.exists() and ivt_a.exists() and ar_a.exists()):
                logging.warning("  VIS skip %s (missing pairs)", step_n)
                continue

            png_f = out_dir / f"{step_n}.png"
            try:
                kb = visualize_one_step(str(ivt_i), str(ar_i),
                                        str(ivt_a), str(ar_a),
                                        str(png_f), region_name)
                total += 1
                logging.info("  VIS %s/%s.png (%.0f KB)", region_name, step_n, kb)
            except Exception as e:
                logging.error("  VIS FAIL %s/%s: %s", region_name, step_n, e)

    logging.info("VIS done: %d PNGs → %s", total, fig_root)
