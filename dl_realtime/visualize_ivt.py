"""IVT + AR 可视化 — 3 区域 contourf 填色, Cartopy PDF.

改动:
- contour → contourf 填色 (老师要求)
- cmap: nipy_spectral_r, truncation 0.2-0.9
- AR 区域 alpha=1, 非 AR 区域 alpha=0.3
- 去掉国界线 (政治不正确)
- 中国标准版图 + 省界: 待 shapefile 就绪后叠加
"""
import logging
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
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
        "figsize": (16, 8),
    },
    "east_asia": {
        "proj": ccrs.PlateCarree(),
        "extent": [105, 150, 10, 50],
        "title_suffix": "East Asia",
        "figsize": (10, 8),
    },
    "north_china": {
        "proj": ccrs.PlateCarree(),
        "extent": [113, 120, 35, 45],
        "title_suffix": "North China",
        "figsize": (9, 7),
    },
}

BJ_LON, BJ_LAT = 116.4, 39.9
IVT_LEVELS = np.arange(100, 1600, 100)
AXIS_COLOR = "#8b008b"


def _truncate_cmap(cmap_name="nipy_spectral_r", lo=0.2, hi=0.9, n=256):
    """切割 colormap，去掉两端极端色."""
    base = plt.get_cmap(cmap_name)
    return mcolors.LinearSegmentedColormap.from_list(
        f"trunc_{cmap_name}_{lo}_{hi}",
        base(np.linspace(lo, hi, n)),
    )


CMAP = _truncate_cmap()


def _base_map(ax, region_name):
    """深蓝海洋 + 绿黄陆地，海岸线（无国界）."""
    ax.add_feature(cfeature.OCEAN, facecolor="#1a3a5c", zorder=0)
    ax.add_feature(cfeature.LAND, facecolor="#8fbc8f", zorder=0)
    ax.add_feature(cfeature.LAKES, facecolor="#1a3a5c", zorder=0)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.3, edgecolor="#ccc", zorder=1)
    # 不画国界线 —— 政治不正确

    gl = ax.gridlines(draw_labels=True, linewidth=0.2, color="#999",
                      alpha=0.4, linestyle="--")
    gl.top_labels = gl.right_labels = False
    if region_name == "global":
        gl.xlocator = mticker.FixedLocator(range(-180, 181, 60))
        gl.ylocator = mticker.FixedLocator(range(-90, 91, 30))


def _read_ar(ar_path):
    ds = xr.open_dataset(ar_path)
    plume = ds["AR_plume"].values.astype(bool)
    axis_ = ds["AR_axis"].values.astype(bool)
    lat = ds["latitude"].values
    lon = ds["longitude"].values
    ds.close()
    return plume, axis_, lat, lon


def _read_ivt(nc_path):
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
    cfg = REGIONS[region_name]
    ivt, lat, lon = _read_ivt(ivt_path)
    plume, axis_, ar_lat, ar_lon = _read_ar(ar_path)

    fig = plt.figure(figsize=cfg["figsize"])
    ax = plt.axes(projection=cfg["proj"])
    if cfg["extent"]:
        ax.set_extent(cfg["extent"], crs=ccrs.PlateCarree())
    else:
        ax.set_global()
    _base_map(ax, region_name)

    # ---- contourf 第 1 层：全 IVT 场（非 AR 区 alpha=0.3） ----
    cs_base = ax.contourf(lon, lat, ivt, levels=IVT_LEVELS, cmap=CMAP,
                          alpha=0.3, extend="max",
                          transform=ccrs.PlateCarree())

    # ---- contourf 第 2 层：AR plume 内 IVT（alpha=1） ----
    ivt_ar = np.where(plume, ivt, np.nan)
    cs_ar = ax.contourf(lon, lat, ivt_ar, levels=IVT_LEVELS, cmap=CMAP,
                        alpha=1.0, extend="max",
                        transform=ccrs.PlateCarree())

    # ---- AR 河轴 ----
    y_idx, x_idx = np.where(axis_)
    if len(y_idx) > 0:
        ax.scatter(ar_lon[x_idx], ar_lat[y_idx], s=0.3, c=AXIS_COLOR,
                   transform=ccrs.PlateCarree(), zorder=5, alpha=0.8)

    # ---- 北京红星 ----
    if region_name == "north_china":
        ax.plot(BJ_LON, BJ_LAT, marker="*", color="red", markersize=14,
                transform=ccrs.PlateCarree(), zorder=6)

    # ---- 色标（底部水平） ----
    cbar = plt.colorbar(cs_ar, ax=ax, orientation="horizontal",
                        shrink=0.55, pad=0.04, aspect=40, extend="max")
    cbar.set_label("IVT  (kg·m⁻¹·s⁻¹)", fontsize=10)

    # ---- 标题 + 标注 ----
    title = f"{_title_from_path(ivt_path)} — {cfg['title_suffix']}"
    ax.set_title(title, fontsize=11, fontweight="bold", pad=6)
    ax.text(0.99, 0.01, "ARIA-Globe vn.17", transform=ax.transAxes,
            fontsize=7, color="white", ha="right", va="bottom",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="black", alpha=0.5))

    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    fig.savefig(pdf_path, dpi=150, bbox_inches="tight", format="pdf")
    plt.close(fig)
    return os.path.getsize(pdf_path) / 1024


def visualize_all(save_dir, model_dirs):
    import shutil
    sp = Path(save_dir)
    fig_root = sp / "figures"
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