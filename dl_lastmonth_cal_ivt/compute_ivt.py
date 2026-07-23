"""垂直积分水汽通量 IVT 计算 (1000-300 hPa).

每个下载的 grib2 文件对应生成一个 NetCDF.
"""
import logging
import os

import eccodes
import numpy as np
import xarray as xr

IVT_LEVELS = [1000, 925, 850, 700, 500, 300]
G = 9.80665


def _read_grib_fields(path):
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
    fields, lat, lon = _read_grib_fields(grib_path)

    q = np.array([fields[("q", l)] for l in IVT_LEVELS])
    u = np.array([fields[("u", l)] for l in IVT_LEVELS])
    v = np.array([fields[("v", l)] for l in IVT_LEVELS])

    p_pa = np.array(IVT_LEVELS) * 100
    dp = np.abs(np.diff(p_pa))

    qu_layer = (q[:-1] * u[:-1] + q[1:] * u[1:]) / 2
    qv_layer = (q[:-1] * v[:-1] + q[1:] * v[1:]) / 2

    ivt_u = np.sum(qu_layer * dp[:, None, None], axis=0) / G
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
    return len(IVT_LEVELS), os.path.getsize(nc_path) / 1024 / 1024