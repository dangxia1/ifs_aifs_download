"""IVT + AR 可视化 — 3 区域 (全球/东亚/华北), Cartopy PDF."""
import logging
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import numpy as np
import xarray as xr

# ── 区域定义 ───────────────────────────────────────────
REGIONS = {
    "global": {
        "proj": ccrs.Robinson(central_longitude=0),
        "extent": None,
        "title_suffix": "Global",
    },
    "east_asia": {
        "proj": ccrs.PlateCarree(),
        "extent": [105, 150, 10, 50],
        "title_suffix": "East Asia",
    },
    "north_china": {
        "proj": ccrs.PlateCarree(),
        "extent": [113, 120, 35, 45],
        "title_suffix": "North China",
    },
}

# 北京坐标
BJ_LON, BJ_LAT = 116.4, 39.9

# 等值线
IVT_CONTOURS = np.arange(100, 1600, 100)
AXIS_COLOR = "#8b008b"  # 紫色河轴


def _base_map(ax, region_name):
    """深蓝海洋 + 绿黄陆地."""
    ax.add_feature(cfeature.OCEAN, facecolor="#1a3a5c", zorder=0)
    ax.add_feature(cfeature.LAND, facecolor="#8fbc8f", zorder=0)
    ax.add_feature(cfeature.LAKES, facecolor="#1a3a5c", zorder=0)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.3, edgecolor="#ccc", zorder=1)
    ax.add_feature(cfeature.BORDERS, linewidth=0.2, edgecolor="#666", zorder=1)

    gl = ax.gridlines(draw_labels=True, linewidth=0.2, color="#999", alpha=0.4, linestyle="--")
    gl.top_labels = gl.right_labels = False
    if region_name == "global":
        gl.xlocator = mticker.FixedLocator(range(-180, 181, 60))
        gl.ylocator = mticker.FixedLocator(range(-90, 91, 30))


def _read_ar(ar_path):
    """读取 AR NetCDF."""
    ds = xr.open_dataset(ar_path)
    plume = ds["AR_plume"].values.astype(bool)
    axis_ = ds["AR_axis"].values.astype(bool)
    lat = ds["latitude"].values
    lon = ds["longitude"].values
    ds.close()
    return plume, axis_, lat, lon


def _read_ivt(nc_path):
    """读取 IVT NetCDF."""
    ds = xr.open_dataset(nc_path)
    ivt = ds["IVT"].values
    lat = ds["latitude"].values
    lon = ds["longitude"].values
    ds.close()
    return ivt, lat, lon


def _title_from_path(path):
    stem = Path(path).stem.replace("_ivt", "")
    parts = stem.split("_")
    if len(parts) >= 4:
        model = parts[1].upper() if parts[1] == "ifs" else "AIFS"
        return f"{model}  {parts[0]}  {parts[2]}  {parts[3]}"
    return stem


def visualize_one_region(ivt_path, ar_path, pdf_path, region_name):
    """单文件 + 单区域 → PDF."""
    cfg = REGIONS[region_name]

    # 读取数据
    ivt, lat, lon = _read_ivt(ivt_path)
    plume, axis_, ar_lat, ar_lon = _read_ar(ar_path)

    # 创建地图
    fig = plt.figure(figsize=(10, 8) if region_name == "global" else (9, 7))
    ax = plt.axes(projection=cfg["proj"])
    if cfg["extent"]:
        ax.set_extent(cfg["extent"], crs=ccrs.PlateCarree())
    else:
        ax.set_global()
    _base_map(ax, region_name)

    # IVT 等值线 — 羽流外 alpha=0.3
    ivt_out = np.where(plume, np.nan, ivt)
    cs1 = ax.contour(lon, lat, ivt_out, levels=IVT_CONTOURS,
                     colors="#ff6b35", linewidths=0.4, alpha=0.3,
                     transform=ccrs.PlateCarree())

    # IVT 等值线 — 羽流内 alpha=1
    ivt_in = np.where(plume, ivt, np.nan)
    cs2 = ax.contour(lon, lat, ivt_in, levels=IVT_CONTOURS,
                     colors="#ff6b35", linewidths=0.6, alpha=1.0,
                     transform=ccrs.PlateCarree())
    ax.clabel(cs2, inline=True, fontsize=6, fmt="%d")

    # AR 河轴
    y_idx, x_idx = np.where(axis_)
    if len(y_idx) > 0:
        ax.scatter(ar_lon[x_idx], ar_lat[y_idx], s=0.3, c=AXIS_COLOR,
                   transform=ccrs.PlateCarree(), zorder=5, alpha=0.8)

    # 华北区域标北京
    if region_name == "north_china":
        ax.plot(BJ_LON, BJ_LAT, marker="*", color="red", markersize=14,
                transform=ccrs.PlateCarree(), zorder=6)

    # 标题 + 标注
    title = f"{_title_from_path(ivt_path)} — {cfg['title_suffix']}"
    ax.set_title(title, fontsize=10, fontweight="bold", pad=6)
    ax.text(0.99, 0.01, "ARIA-Globe vn.17", transform=ax.transAxes,
            fontsize=7, color="white", ha="right", va="bottom",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="black", alpha=0.5))

    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    fig.savefig(pdf_path, dpi=150, bbox_inches="tight", format="pdf")
    plt.close(fig)
    return os.path.getsize(pdf_path) / 1024


def visualize_all(save_dir, model_dirs):
    """遍历所有 IVT NC + AR NC，3 区域 × 每文件，每次运行覆盖旧图."""
    import shutil
    sp = Path(save_dir)
    fig_root = sp / "figures"

    # 清空旧的 figure 目录，确保只保留最新一次运行的结果
    if fig_root.exists():
        shutil.rmtree(fig_root)

    total = 0

    for _, subdir in model_dirs.items():
        ivt_dir = sp / "ivt" / subdir
        ar_dir = sp / "ar" / subdir

        for nc_f in sorted(ivt_dir.glob("*_ivt.nc")):
            ar_f = ar_dir / nc_f.name.replace("_ivt.nc", "_ar.nc")
            if not ar_f.exists():
                logging.warning("  VIS skip: AR not found for %s", nc_f.name)
                continue

            for region_name in REGIONS:
                out_dir = fig_root / region_name / subdir
                out_dir.mkdir(parents=True, exist_ok=True)
                pdf_f = out_dir / nc_f.name.replace("_ivt.nc", ".pdf")

                try:
                    kb = visualize_one_region(str(nc_f), str(ar_f), str(pdf_f), region_name)
                    total += 1
                except Exception as e:
                    logging.error("  VIS FAIL %s/%s: %s", region_name, pdf_f.name, e)

    logging.info("VIS done: %d PDFs → %s", total, fig_root)
