"""IVT 水汽输送可视化 — 全球 Robinson 投影，期刊标准 PDF 输出.

每张图: IVT 量级填色 + IVT 矢量箭头 + 500hPa 位势高度 + 降水叠加
"""
import logging
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # 无 GUI 后端，适配 cron/nohup
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import numpy as np
import xarray as xr

from compute_ivt import _read_grib_fields

# 每 4° 抽稀矢量箭头
QUIVER_SKIP = 16  # 0.25° × 16 = 4°

# IVT 色标范围
IVT_VMIN, IVT_VMAX = 0, 1000  # kg·m⁻¹·s⁻¹

# 500 hPa 等高线间距 (gpm)
GH_INTERVAL = 60  # 6 dagpm


def _add_map_features(ax):
    """添加海岸线、国界、经纬网."""
    ax.add_feature(cfeature.LAND, facecolor="#f5f5f0", zorder=0)
    ax.add_feature(cfeature.OCEAN, facecolor="#e8f0f8", zorder=0)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.3, edgecolor="#333")
    ax.add_feature(cfeature.BORDERS, linewidth=0.2, edgecolor="#666")
    gl = ax.gridlines(draw_labels=True, linewidth=0.3, color="#999",
                      alpha=0.5, linestyle="--")
    gl.top_labels = gl.right_labels = False
    gl.xlocator = mticker.FixedLocator(range(-180, 181, 60))
    gl.ylocator = mticker.FixedLocator(range(-90, 91, 30))


def _title_from_filename(nc_path):
    """从文件名提取标题信息. 例: 2026-07-21_ifs_t18_step24_ivt.nc"""
    stem = Path(nc_path).stem  # 去掉 .nc
    if stem.endswith("_ivt"):
        stem = stem[:-4]
    parts = stem.split("_")
    # parts = ['2026-07-21', 'ifs', 't18', 'step24']
    if len(parts) >= 4:
        date, model, time_s, step_s = parts[0], parts[1], parts[2], parts[3]
        model_label = model.upper() if model == "ifs" else "AIFS"
        return f"{model_label}  {date}  {time_s}  {step_s}"
    return stem


def visualize_one(nc_path, grib_path, pdf_path):
    """对一个 NC + grib2 生成单张 PDF."""
    # 1. 读取 IVT 数据
    ds = xr.open_dataset(nc_path)
    ivt = ds["IVT"].values
    ivt_u = ds["IVT_u"].values
    ivt_v = ds["IVT_v"].values
    lat = ds["latitude"].values
    lon = ds["longitude"].values
    ds.close()

    # 2. 读取 grib2 中的 gh@500 和 tp
    fields, glat, glon = _read_grib_fields(grib_path)
    gh500 = fields.get(("gh", 500))  # 500 hPa 位势高度
    tp = fields.get(("tp", None))     # 总降水 (地面场, level=None/0)

    # 3. 创建地图
    fig = plt.figure(figsize=(16, 8))
    ax = plt.axes(projection=ccrs.Robinson(central_longitude=0))
    ax.set_global()
    _add_map_features(ax)

    # 4. IVT 量级填色
    im = ax.pcolormesh(lon, lat, ivt,
                       transform=ccrs.PlateCarree(),
                       cmap="cividis", vmin=IVT_VMIN, vmax=IVT_VMAX,
                       rasterized=True, shading="auto")
    cbar = plt.colorbar(im, ax=ax, orientation="horizontal",
                        shrink=0.6, pad=0.04, aspect=40)
    cbar.set_label("IVT  (kg·m⁻¹·s⁻¹)", fontsize=10)

    # 5. IVT 矢量箭头 (抽稀)
    skip = QUIVER_SKIP
    q = ax.quiver(lon[::skip], lat[::skip],
                  ivt_u[::skip, ::skip], ivt_v[::skip, ::skip],
                  transform=ccrs.PlateCarree(),
                  scale=8000, width=0.002, color="black", alpha=0.7)
    # 图例箭头
    ax.quiverkey(q, 0.92, -0.08, 500, "500 kg·m⁻¹·s⁻¹",
                 labelpos="E", coordinates="axes", fontproperties={"size": 8})

    # 6. 500 hPa 位势高度等高线
    if gh500 is not None:
        levels = np.arange(4800, 6001, GH_INTERVAL)
        ax.contour(lon, lat, gh500, levels=levels,
                   transform=ccrs.PlateCarree(),
                   colors="white", linewidths=0.6, alpha=0.85)
        ax.clabel(ax.contour(lon, lat, gh500, levels=levels,
                             transform=ccrs.PlateCarree(),
                             colors="white", linewidths=0.1, alpha=0),
                  inline=True, fontsize=7, fmt="%d")

    # 7. 降水叠加 (tp 单位 m → 转为 mm，半透明蓝色)
    if tp is not None:
        tp_mm = tp * 1000  # m → mm
        tp_mm = np.clip(tp_mm, 0.1, None)  # 过滤小值
        ax.pcolormesh(lon, lat, tp_mm,
                      transform=ccrs.PlateCarree(),
                      cmap="Blues", vmin=0, vmax=50,
                      rasterized=True, shading="auto", alpha=0.4)

    # 8. 标题
    title = _title_from_filename(nc_path)
    ax.set_title(title, fontsize=12, fontweight="bold", pad=8)

    # 9. 输出
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    fig.savefig(pdf_path, dpi=150, bbox_inches="tight", format="pdf")
    plt.close(fig)
    return os.path.getsize(pdf_path) / 1024


def visualize_all(save_dir, model_dirs):
    """遍历所有 IVT NC 文件，生成 PDF."""
    save_path = Path(save_dir)
    ivt_root = save_path / "ivt"
    fig_root = save_path / "figures"
    total = 0

    for _, subdir in model_dirs.items():
        ivt_dir = ivt_root / subdir
        grib_dir = save_path / subdir
        out_dir = fig_root / subdir
        out_dir.mkdir(parents=True, exist_ok=True)

        for nc_f in sorted(ivt_dir.glob("*_ivt.nc")):
            # 找对应 grib2
            grib_name = nc_f.name.replace("_ivt.nc", ".grib2")
            grib_f = grib_dir / grib_name
            if not grib_f.exists():
                logging.warning("  VIS skip: grib not found for %s", nc_f.name)
                continue

            pdf_name = nc_f.name.replace("_ivt.nc", ".pdf")
            pdf_f = out_dir / pdf_name

            try:
                size_kb = visualize_one(str(nc_f), str(grib_f), str(pdf_f))
                logging.info("  VIS %s/%s  (%.0f KB)", subdir, pdf_name, size_kb)
                total += 1
            except Exception as e:
                logging.error("  VIS FAIL %s: %s", pdf_name, e)

    logging.info("VIS done: %d PDFs → %s", total, fig_root)
