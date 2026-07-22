"""垂直积分水汽通量 IVT 计算 (1000-300 hPa).

IVT = (1/g) * integral(q * V, dp, 300hPa, 1000hPa)
每个下载的 grib2 文件对应生成一个 NetCDF.
"""
import logging
import os
from pathlib import Path

import eccodes
import numpy as np
import xarray as xr

# 积分用气压层级 (hPa)，从低到高
IVT_LEVELS = [1000, 925, 850, 700, 500, 300]
G = 9.80665  # m/s^2


def _read_grib_fields(path):
    """读取 grib2 文件，返回 { (shortName, level): 2D_array } 和 lat/lon."""
    fields = {}
    lat = lon = None
    with open(path, "rb") as f:
        while True:
            msg_id = eccodes.codes_grib_new_from_file(f)
            if msg_id is None:
                break
            sn = eccodes.codes_get(msg_id, "shortName")
            lev = eccodes.codes_get(msg_id, "level")
            ni = eccodes.codes_get(msg_id, "Ni")
            nj = eccodes.codes_get(msg_id, "Nj")
            vals = eccodes.codes_get_values(msg_id).reshape(nj, ni)
            fields[(sn, lev)] = vals
            if lat is None:
                lat = eccodes.codes_get_array(msg_id, "latitudes").reshape(nj, ni)[:, 0]
                lon = eccodes.codes_get_array(msg_id, "longitudes").reshape(nj, ni)[0, :]
            eccodes.codes_release(msg_id)
    return fields, lat, lon


def compute_ivt(grib_path, nc_path):
    """从单个 grib2 计算 IVT，保存为 NetCDF."""
    fields, lat, lon = _read_grib_fields(grib_path)

    # 提取 q, u, v 在 IVT_LEVELS 上的 3D 数组 [level, lat, lon]
    q = np.array([fields[("q", l)] for l in IVT_LEVELS])
    u = np.array([fields[("u", l)] for l in IVT_LEVELS])
    v = np.array([fields[("v", l)] for l in IVT_LEVELS])

    # 气压层厚度 (Pa)，从低到高: p[k+1] < p[k]
    p_pa = np.array(IVT_LEVELS) * 100  # hPa → Pa
    dp = np.abs(np.diff(p_pa))  # [nlayer], 每层厚度

    # 梯形法则: 层平均 q*V × 层厚
    qu_layer = (q[:-1] * u[:-1] + q[1:] * u[1:]) / 2  # [nlayer, lat, lon]
    qv_layer = (q[:-1] * v[:-1] + q[1:] * v[1:]) / 2

    ivt_u = np.sum(qu_layer * dp[:, None, None], axis=0) / G  # kg/(m·s)
    ivt_v = np.sum(qv_layer * dp[:, None, None], axis=0) / G
    ivt = np.sqrt(ivt_u**2 + ivt_v**2)

    ds = xr.Dataset(
        {"IVT": (["latitude", "longitude"], ivt.astype(np.float32)),
         "IVT_u": (["latitude", "longitude"], ivt_u.astype(np.float32)),
         "IVT_v": (["latitude", "longitude"], ivt_v.astype(np.float32))},
        coords={"latitude": lat.astype(np.float32), "longitude": lon.astype(np.float32)},
        attrs={"units": "kg m-1 s-1", "source": os.path.basename(grib_path),
               "levels_hPa": str(IVT_LEVELS), "description": "IVT integrated 1000-300 hPa"},
    )
    ds.to_netcdf(nc_path)
    size_mb = os.path.getsize(nc_path) / 1024 / 1024
    return len(IVT_LEVELS), size_mb


def compute_all_ivt(save_dir, model_dirs):
    """遍历所有已下载 grib2，逐个计算 IVT.

    save_dir:   /shared_data/zongshen/ec实时数据更新
    model_dirs: {"ifs": "ifs", "aifs-single": "aifs"}
    """
    save_path = Path(save_dir)
    ivt_root = save_path / "ivt"
    total = 0

    for _, subdir in model_dirs.items():
        src_dir = save_path / subdir
        out_dir = ivt_root / subdir
        out_dir.mkdir(parents=True, exist_ok=True)

        for f in src_dir.glob("*.grib2"):
            nc_name = f.stem + "_ivt.nc"
            nc_path = out_dir / nc_name

            nlev, size_mb = compute_ivt(str(f), str(nc_path))
            logging.info("  IVT %s/%s  (%d levels, %.1fMB)",
                         subdir, nc_name, nlev, size_mb)
            total += 1

    logging.info("IVT done: %d files → %s", total, ivt_root)