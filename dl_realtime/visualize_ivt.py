"""IVT + AR 可视化 — 参照导师 Basemap 画法, Cartopy 移植."""
import logging
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.ticker as mticker
import cartopy.crs as ccrs
import numpy as np
import xarray as xr

# ── 区域定义 ───────────────────────────────────────────
REGIONS = {
    "global": {
        "proj": ccrs.PlateCarree(),
        "extent": [-179, 180, -88, 88],  # 参照导师: -179~180, -88~88
        "figsize": (16, 8),
        "lat_ticks": range(-80, 81, 30),
        "lon_ticks": range(-180, 181, 30),
        "title_suffix": "Global",
    },
    "east_asia": {
        "proj": ccrs.PlateCarree(),
        "extent": [105, 150, 10, 50],
        "figsize": (10, 8),
        "lat_ticks": range(10, 51, 10),
        "lon_ticks": range(105, 151, 10),
        "title_suffix": "East Asia",
    },
    "north_china": {
        "proj": ccrs.PlateCarree(),
        "extent": [113, 120, 35, 45],
        "figsize": (9, 7),
        "lat_ticks": range(35, 46, 2),
        "lon_ticks": range(113, 121, 2),
        "title_suffix": "North China",
    },
}

BJ_LON, BJ_LAT = 116.4, 39.9
IVT_LEVELS = np.arange(50, 850, 50)  # 参照导师: 50~850, 每50
AXIS_COLOR = "purple"


def _truncate_cmap(cmap_name="nipy_spectral_r", lo=0.2, hi=0.9, n=256):
    base = plt.get_cmap(cmap_name)
    return mcolors.LinearSegmentedColormap.from_list(
        f"trunc_{cmap_name}_{lo}_{hi}",
        base(np.linspace(lo, hi, n)),
    )


CMAP = _truncate_cmap()


def _read_ar(ar_path):
    ds = xr.open_dataset(ar_path)
    plume = ds["AR_plume"].values.astype(bool)
    axis_ = ds["AR_axis"].values.astype(bool)
    lat = ds["latitude"].values
    lon = ds["longitude"].values
    ds.close()
    # 经度 0~360 → -180~180
    lon_plot = lon.copy()
    lon_plot[lon_plot > 180] -= 360
    idx = np.argsort(lon_plot)
    return (plume[:, idx], axis_[:, idx], lat, lon_plot[idx])


def _read_ivt(nc_path):
    ds = xr.open_dataset(nc_path)
    ivt = ds["IVT"].values
    lat = ds["latitude"].values
    lon = ds["longitude"].values
    ds.close()
    lon_plot = lon.copy()
    lon_plot[lon_plot > 180] -= 360
    idx = np.argsort(lon_plot)
    return (ivt[:, idx], lat, lon_plot[idx])


def _gridlines(ax, cfg):
    gl = ax.gridlines(draw_labels=True, linewidth=0.3, color="grey",
                      alpha=0.6, linestyle="--")
    gl.top_labels = gl.right_labels = False
    gl.left_labels = True
    gl.bottom_labels = True
    gl.xlocator = mticker.FixedLocator(cfg["lon_ticks"])
    gl.ylocator = mticker.FixedLocator(cfg["lat_ticks"])
    gl.xlabel_style = {"size": 8, "color": "white"}
    gl.ylabel_style = {"size": 8, "color": "white"}


def visualize_one_region(ivt_path, ar_path, pdf_path, region_name):
    cfg = REGIONS[region_name]

    ivt, lat, lon = _read_ivt(ivt_path)
    plume, axis_, ar_lat, ar_lon = _read_ar(ar_path)

    # 暗色背景 (参照导师 bluemarble 风格)
    fig = plt.figure(figsize=cfg["figsize"], facecolor="black")
    ax = plt.axes(projection=cfg["proj"])
    ax.set_facecolor("black")
    ax.set_extent(cfg["extent"], crs=ccrs.PlateCarree())

    # 海岸线 (灰色细线)
    ax.coastlines(linewidth=0.2, color="grey", zorder=2)

    _gridlines(ax, cfg)

    # ---- contourf 第 1 层：全 IVT 场 alpha=0.2 (导师风格) ----
    ax.contourf(lon, lat, ivt, levels=IVT_LEVELS, cmap=CMAP,
                alpha=0.2, extend="max", transform=ccrs.PlateCarree(), zorder=1)

    # ---- contourf 第 2 层：AR plume 内 IVT alpha=1 ----
    ivt_ar = np.where(plume, ivt, np.nan)
    cs = ax.contourf(lon, lat, ivt_ar, levels=IVT_LEVELS, cmap=CMAP,
                     alpha=1.0, extend="max",
                     transform=ccrs.PlateCarree(), zorder=3)

    # ---- contour 薄黑线叠加 (参照导师) ----
    ax.contour(lon, lat, ivt, levels=IVT_LEVELS,
               colors="black", linewidths=0.1,
               transform=ccrs.PlateCarree(), zorder=4)

    # ---- AR 河轴 ----
    y_idx, x_idx = np.where(axis_)
    if len(y_idx) > 0:
        ax.scatter(ar_lon[x_idx], ar_lat[y_idx], s=0.2, c=AXIS_COLOR,
                   transform=ccrs.PlateCarree(), zorder=5, alpha=0.8)

    # ---- 北京红星 ----
    if region_name == "north_china":
        ax.plot(BJ_LON, BJ_LAT, marker="*", color="red", markersize=14,
                transform=ccrs.PlateCarree(), zorder=6)

    # ---- 色标 (底部水平, 参照导师布局) ----
    cb_ax = fig.add_axes([0.2, 0.04, 0.62, 0.02])
    cbar = fig.colorbar(cs, cax=cb_ax, orientation="horizontal", extend="max")
    cbar.ax.tick_params(labelsize=10, colors="white")
    cbar.ax.set_xlabel("kg m$^{-1}$ s$^{-1}$", size=10, color="white")

    # ---- 标题 (白色) ----
    ax.set_title(cfg["title_suffix"], fontsize=14, color="white", pad=10)

    # 标注 (右下角)
    ax.text(0.99, 0.01, "ARIA-Globe vn.17", transform=ax.transAxes,
            fontsize=7, color="white", ha="right", va="bottom")

    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    fig.savefig(pdf_path, dpi=150, bbox_inches="tight", format="pdf",
                facecolor="black", edgecolor="none")
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