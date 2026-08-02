"""IVT + AR 可视化 — 照搬导师 Basemap 画法."""
import logging
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import xarray as xr
from mpl_toolkits.basemap import Basemap

# ── 区域 ────────────────────────────────────────────────
REGIONS = {
    "global": {
        "width": 8000000, "height": 7500000,
        "lat_0": -88, "lat_1": 88, "lon_0": -179, "lon_1": 180,
        "parallels": np.arange(-80., 81., 30.),
        "meridians": np.arange(-180., 181., 30.),
        "figsize": (13, 8),
        "title": "Global",
    },
    "east_asia": {
        "width": 5000000, "height": 4500000,
        "lat_0": 10, "lat_1": 50, "lon_0": 105, "lon_1": 150,
        "parallels": np.arange(10., 51., 10.),
        "meridians": np.arange(105., 151., 10.),
        "figsize": (10, 8),
        "title": "East Asia",
    },
    "north_china": {
        "width": 900000, "height": 1200000,
        "lat_0": 35, "lat_1": 45, "lon_0": 113, "lon_1": 120,
        "parallels": np.arange(35., 46., 2.),
        "meridians": np.arange(113., 121., 2.),
        "figsize": (9, 7),
        "title": "North China",
    },
}

BJ_LON, BJ_LAT = 116.4, 39.9
IVT_LEVELS = np.arange(250., 850., 50.)
AXIS_COLOR = "purple"


def _truncate_cmap(cmap_name="nipy_spectral_r", lo=0.1, hi=0.85, n=256):
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
    center = ds["AR_center"].values
    lat = ds["latitude"].values
    lon = ds["longitude"].values
    ds.close()
    # 经度 0~360 → -180~180 排序
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
    lon[lon > 180] -= 360
    idx = np.argsort(lon)
    return (ivt[:, idx], lat, lon[idx])


def _title_from_path(path):
    stem = Path(path).stem.replace("_ivt", "")
    parts = stem.split("_")
    if len(parts) >= 4:
        model = parts[1].upper() if parts[1] == "ifs" else "AIFS"
        # parts[0]=date, parts[2]=tHH, parts[3]=stepNN
        t_str = parts[2][1:]  # "06" from "t06"
        s_str = parts[3][4:]  # "24" from "step24"
        return f"{t_str}:00 UTC {parts[0][5:]} {model} +{s_str}h"
    return stem


def visualize_one_region(ivt_path, ar_path, pdf_path, region_name):
    cfg = REGIONS[region_name]
    ivt, lat1d, lon1d = _read_ivt(ivt_path)
    plume, axis_, ar_lat1d, ar_lon1d, lat2d, lon2d, ce_lats, ce_lons = _read_ar(ar_path)

    lon2d_p, lat2d_p = np.meshgrid(lon1d, lat1d)

    # ── 照搬导师: Basemap + bluemarble ──
    fig, ax = plt.subplots(figsize=cfg["figsize"])
    ax.set_facecolor("black")

    m = Basemap(width=cfg["width"], height=cfg["height"],
                projection="cyl", area_thresh=10., resolution="l",
                llcrnrlat=cfg["lat_0"], urcrnrlat=cfg["lat_1"],
                llcrnrlon=cfg["lon_0"], urcrnrlon=cfg["lon_1"],
                lat_ts=14.5, ax=ax)

    m.bluemarble(zorder=0)

    x, y = m(lon2d_p, lat2d_p)
    title = f"{_title_from_path(ivt_path)}"

    # ---- contourf 第 1 层：全 IVT alpha=0.2 ----
    ax.contourf(x, y, ivt, levels=IVT_LEVELS, extend="max",
                cmap=CMAP, alpha=0.2)

    # ---- contourf 第 2 层：AR plume 内 IVT alpha=1 ----
    ivt_ar = np.where(plume, ivt, np.nan)
    cs = ax.contourf(x, y, ivt_ar, levels=IVT_LEVELS, extend="max",
                     cmap=CMAP)

    # ---- AR 河轴 ----
    y_a, x_a = np.where(axis_)
    if len(y_a) > 0:
        x_axis, y_axis = m(lon2d_p[y_a, x_a], lat2d_p[y_a, x_a])
        ax.scatter(x_axis, y_axis, c=AXIS_COLOR, s=0.2)

    # ---- AR 质心 (红色十字) ----
    if len(ce_lats) > 0:
        x_cent, y_cent = m(lon2d_p[ce_lats, ce_lons],
                           lat2d_p[ce_lats, ce_lons])
        ax.scatter(x_cent, y_cent, marker="+", c="red", s=100, linewidths=1.)

    # ---- 海岸线 + 经纬网 ----
    m.drawcoastlines(color="grey", linewidth=0.2, zorder=0)
    m.drawparallels(cfg["parallels"], labels=[1, 0, 0, 0],
                    fontsize=10, color="white", textcolor="white", linewidth=0.1)
    m.drawmeridians(cfg["meridians"], labels=[0, 0, 0, 1],
                    fontsize=10, color="white", textcolor="white", linewidth=0.1)

    # ---- 北京红星 ----
    if region_name == "north_china":
        bx, by = m(BJ_LON, BJ_LAT)
        ax.plot(bx, by, marker="*", color="red", markersize=14, zorder=6)

    # ---- 色标 ----
    cbar = plt.colorbar(cs, fraction=0.046, orientation="horizontal",
                        extend="max", pad=0.06)
    cbar.ax.tick_params(labelsize=14, colors="white")
    cbar.ax.set_xlabel("kg m$^{-1}$ s$^{-1}$", size=14, color="white")

    # ---- 标题 ----
    ax.set_title(title, fontsize=15, color="white", pad=8)
    ax.tick_params(axis="both", colors="white")

    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    fig.savefig(pdf_path, dpi=300, bbox_inches="tight", facecolor="black")
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
