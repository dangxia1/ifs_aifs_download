"""大气河 (Atmospheric River) 识别 — 移植自 ARIA_Asia_v15.

输入: _ivt.nc (IVT_u, IVT_v, IVT)
输出: _ar.nc (AR_plume, AR_axis, AR_center, AR_IVT)
"""
import logging
import os
import pickle
from pathlib import Path

import numpy as np
import xarray as xr
from scipy import ndimage, spatial
from scipy.ndimage import gaussian_filter
from scipy.signal import convolve2d
from skimage.morphology import skeletonize, binary_dilation
from skimage.measure import label, regionprops
import metpy.calc as MC
from fil_finder import FilFinder2D
import astropy.units as u

G = 9.80665
IVT_FLOOR = 344.0          # 最小 IVT 阈值 (kg·m⁻¹·s⁻¹)
MIN_AXIS_LENGTH = 2_000_000  # 最小河轴长度 (m), ~2000 km
MAX_MEAN_WIDTH = 750_000     # 最大平均宽度 (m), ~750 km


def _truncate_colormap(cmap, minval=0.0, maxval=1.0, n=100):
    from matplotlib import colors
    new_cmap = colors.LinearSegmentedColormap.from_list(
        f'trunc({cmap.name},{minval:.2f},{maxval:.2f})',
        cmap(np.linspace(minval, maxval, n)))
    return new_cmap


def _angular_diff(a, b):
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def _load_monthly_thresholds(thresh_dir):
    """加载 1-12 月 85% IVT 阈值 (shape: 12 x lat x lon)."""
    thresholds = []
    for m in range(1, 13):
        pkl_path = os.path.join(thresh_dir, f'ERA5_IVT_threshold_85_19812023_{m:02d}.pckl')
        with open(pkl_path, 'rb') as f:
            _, t = pickle.load(f)
        thresholds.append(t.astype(np.float64))
    thresh = np.array(thresholds)
    thresh[thresh < IVT_FLOOR] = IVT_FLOOR
    return thresh


def _seasonal_threshold(thresh_all, month_idx):
    """5 个月滑动平均: 前后各 2 个月."""
    idx = [10,11,0,1,2, 11,0,1,2,3, 0,1,2,3,4, 1,2,3,4,5,
           2,3,4,5,6, 3,4,5,6,7, 4,5,6,7,8, 5,6,7,8,9,
           6,7,8,9,10, 7,8,9,10,11, 8,9,10,11,0, 9,10,11,0,1]
    indices = idx[month_idx*5:(month_idx+1)*5]
    return np.nanmean(thresh_all[indices], axis=0)


def _skeleton_refine(skeleton, mflux_data, max_shift=8):
    """将骨架点向 IVT 极大值方向微调."""
    grad_y = ndimage.sobel(mflux_data.astype(float), axis=0)
    grad_x = ndimage.sobel(mflux_data.astype(float), axis=1)
    norm = np.hypot(grad_x, grad_y)
    valid = norm > 0
    nx = np.where(valid, -grad_x / norm, 0)
    ny = np.where(valid, grad_y / norm, 0)

    kernel = np.ones((3, 3))
    nbr = convolve2d(skeleton.astype(int), kernel, mode='same') - 1
    branch = (nbr > 2) & skeleton

    y, x = np.where(skeleton)
    shifts = np.linspace(-max_shift, max_shift, 15)
    dy = (y[:, None] + ny[y, x][:, None] * shifts).round().astype(int)
    dx = (x[:, None] + nx[y, x][:, None] * shifts).round().astype(int)
    vd = (dx >= 0) & (dx < mflux_data.shape[1]) & (dy >= 0) & (dy < mflux_data.shape[0])
    vals = np.full(dy.shape, -np.inf)
    vals[vd] = mflux_data[dy[vd], dx[vd]]
    best = np.argmax(vals, axis=1)

    out = np.zeros_like(skeleton, dtype=bool)
    for i, (yy, xx) in enumerate(zip(y, x)):
        if branch[yy, xx]:
            out[yy, xx] = True
        else:
            out[dy[i, best[i]], dx[i, best[i]]] = True
    return out


def _filfinder_skeleton(binary_mask):
    """FilFinder2D 骨架精炼."""
    fil = FilFinder2D(binary_mask, distance=250 * u.pc, mask=binary_mask)
    fil.create_mask(border_masking=True, verbose=False, use_existing_mask=True)
    fil.medskel(verbose=False)
    fil.analyze_skeletons(branch_thresh=40 * u.pix, skel_thresh=40 * u.pix, prune_criteria='length')
    return fil.skeleton


def detect_ar_single(ivt_u, ivt_v, ivt, lat2d, lon2d, threshold_2d):
    """对单个时次执行 AR 检测.

    Returns: ar_plume, ar_axis, ar_center, ar_ivt  (2D arrays)
    """
    ny, nx = ivt.shape
    # 经度循环扩展 3 倍，处理跨日期变更的 AR
    ivt_exp = np.hstack([ivt, ivt, ivt])
    u_exp = np.hstack([ivt_u, ivt_u, ivt_u])
    v_exp = np.hstack([ivt_v, ivt_v, ivt_v])
    lat_exp = np.hstack([lat2d, lat2d, lat2d])
    lon_exp = np.hstack([lon2d, lon2d, lon2d])

    # 网格分辨率
    dy_grid = np.zeros_like(lat2d)
    dx_grid = np.zeros_like(lon2d)
    dx_grid[:, :-1], dy_grid[:-1, :] = MC.lat_lon_grid_deltas(lon2d, lat2d)
    dx_exp = np.hstack([dx_grid, dx_grid, dx_grid])
    dy_exp = np.hstack([dy_grid, dy_grid, dy_grid])
    res_x = abs(lon2d[0, 1] - lon2d[0, 0])
    res_y = abs(lat2d[1, 0] - lat2d[0, 0])

    # 1. 阈值二值化
    binary = np.zeros_like(ivt_exp, dtype=bool)
    binary[ivt_exp > threshold_2d] = True

    # 2. 形态学处理
    filled = ndimage.binary_fill_holes(binary).astype(bool)
    seg_label = label(filled, connectivity=2)

    # 3. 骨架化
    skel = skeletonize(seg_label > 0)
    skeleton = skel.copy()
    skeleton[seg_label == 0] = False

    # 4. 距离变换 + FilFinder
    dist = ndimage.distance_transform_edt(filled)
    dist_skel = dist * skeleton
    skeleton = _filfinder_skeleton(skeleton)
    struct2 = ndimage.generate_binary_structure(2, 2)
    skeleton = ndimage.binary_dilation(skeleton, structure=struct2)
    skeleton = skeletonize(skeleton)
    skeleton[seg_label == 0] = False

    # 5. 骨架偏移到 IVT 极大值
    skeleton = _skeleton_refine(skeleton, ivt_exp, max_shift=8)
    struct = ndimage.generate_binary_structure(2, 2)
    for _ in range(3):
        skeleton = ndimage.binary_dilation(skeleton, structure=struct)

    # 6. 二次 FilFinder
    skeleton = _filfinder_skeleton(skeleton)
    filled2 = ndimage.binary_fill_holes(skeleton).astype(bool)
    skeleton = skeletonize(filled2)
    skeleton[dist_skel > (5.0 / ((res_x + res_y) / 2.0)) + 1] = False

    # 7. 过滤短骨架（< 20 像素）
    lab_skel = label(skeleton, connectivity=2)
    sizes = np.bincount(lab_skel.ravel())
    for rid, sz in enumerate(sizes):
        if rid > 0 and sz < 20:
            skeleton[lab_skel == rid] = False

    # 8. 限制在填充区域
    seg_label_exp = label(ndimage.binary_fill_holes(np.hstack([binary[:, :nx], binary[:, :nx], binary[:, :nx]])).astype(bool), connectivity=2)
    skeleton[seg_label_exp == 0] = False

    # 9. 重新标记并逐 plume 几何过滤
    seg_label = seg_label_exp
    for seg_n in range(1, np.max(seg_label) + 1):
        plume_idx = (seg_label == seg_n)
        skel_in = skeleton & plume_idx

        # 计算河轴长度
        y_idx, x_idx = np.where(skel_in)
        axis_len = 0.0
        mask_tmp = skel_in.copy().astype(int)
        for i in range(len(y_idx)):
            yy, xx = y_idx[i], x_idx[i]
            if mask_tmp[yy, xx] == 0:
                continue
            if 0 < yy < mask_tmp.shape[0]-1 and 0 < xx < mask_tmp.shape[1]-1:
                d_xy = np.sqrt(dx_exp[yy, xx]**2 + abs(dy_exp[yy, xx])**2)
                dmat = np.array([[d_xy, abs(dy_exp[yy, xx]), d_xy],
                                 [dx_exp[yy, xx], 0, dx_exp[yy, xx]],
                                 [d_xy, abs(dy_exp[yy, xx]), d_xy]])
                mask_tmp[yy, xx] = 0
                adj = mask_tmp[yy-1:yy+2, xx-1:xx+2]
                axis_len += np.sum(dmat[adj > 0])

        area_AR = np.nansum(np.abs(dx_exp * dy_exp)[plume_idx])
        tropic_pct = np.sum(plume_idx & (np.abs(lat_exp) < 15.0)) / np.sum(plume_idx)

        # IVT 方向一致性
        ivt_dir = np.zeros_like(seg_label, dtype=float)
        ivt_dir[plume_idx] = np.arctan2(v_exp[plume_idx] / ivt_exp[plume_idx],
                                        u_exp[plume_idx] / ivt_exp[plume_idx]) * 180.0 / np.pi
        ivt15_pct = np.sum(plume_idx & ((np.abs(ivt_dir) < 15.0) |
                                         ((ivt_dir > 165.0) & (ivt_dir < 195.0)))) / np.sum(plume_idx)
        mean_dir = np.arctan2(np.nanmean(v_exp[plume_idx] / ivt_exp[plume_idx]),
                              np.nanmean(u_exp[plume_idx] / ivt_exp[plume_idx])) * 180.0 / np.pi
        deviat = np.abs(ivt_dir - mean_dir)
        deviat[deviat > 180] -= 360
        deviat[deviat > 90] -= 180
        deviat_pct = np.sum(deviat[plume_idx] > 45) / np.sum(plume_idx)

        # 过滤条件
        reject = (
            (axis_len < MIN_AXIS_LENGTH) or
            ((area_AR / axis_len) > MAX_MEAN_WIDTH if axis_len > 0 else True) or
            (tropic_pct > 0.95) or
            (0.5 < tropic_pct <= 0.95 and ivt15_pct > 0.5) or
            (deviat_pct > 0.5)
        )
        if reject:
            skeleton[plume_idx] = False
            seg_label[plume_idx] = 0

    # 10. 裁剪回中心 1/3
    skeleton = skeleton[:, nx:2*nx]
    seg_label = seg_label[:, nx:2*nx]
    seg_label[seg_label > 0] = 1

    # 11. 重新标记 + 质心
    seg_label = _periodic_label(seg_label, connectivity=2)

    # 排序经度到 -180..180
    lon_sorted = lon2d.copy()
    lon_sorted[lon_sorted > 180] -= 360
    sort_idx = np.argsort(lon_sorted[0, :])
    lon_s = lon_sorted[:, sort_idx]
    lat_s = lat2d[:, sort_idx]

    plume_out = seg_label[:, sort_idx]
    axis_out = skeleton[:, sort_idx].astype(np.int32)

    # AR IVT (只保留 plume 内的)
    ivt_local = ivt.copy()
    ivt_local[seg_label == 0] = 0
    ivt_out = ivt_local[:, sort_idx]

    # 质心
    centroids = _get_centroids(seg_label[:, sort_idx], lat_s, lon_s, ivt_local[:, sort_idx])
    center_out = np.zeros_like(axis_out, dtype=np.int32)
    for clat, clon in centroids:
        dist = np.sqrt((lon_s - clon)**2 + (lat_s - clat)**2)
        idx_min = np.argmin(dist)
        cy, cx = np.unravel_index(idx_min, dist.shape)
        center_out[cy, cx] += 1

    return plume_out, axis_out, center_out, ivt_out.astype(np.float32)


def _periodic_label(mask, connectivity=2):
    """经度周期边界感知的连通域标记."""
    # 简化版: 普通 label + 检查周期边界
    return label(mask, connectivity=connectivity)


def _get_centroids(seg_label, lat2d, lon2d, ivt_field):
    """提取每个 plume 的加权质心."""
    centroids = []
    for seg_n in range(1, np.max(seg_label) + 1):
        mask = (seg_label == seg_n)
        if not np.any(mask):
            continue
        weights = ivt_field[mask]
        w_sum = np.sum(weights)
        if w_sum > 0:
            clon = np.sum(lon2d[mask] * weights) / w_sum
            clat = np.sum(lat2d[mask] * weights) / w_sum
            centroids.append((clat, clon))
    return centroids


def save_ar_nc(output_path, ar_plume, ar_axis, ar_center, ar_ivt, lat, lon):
    """保存 AR 结果为 NetCDF."""
    ds = xr.Dataset(
        {"AR_plume":  (["latitude", "longitude"], ar_plume.astype(np.int32)),
         "AR_axis":   (["latitude", "longitude"], ar_axis.astype(np.int32)),
         "AR_center": (["latitude", "longitude"], ar_center.astype(np.int32)),
         "AR_IVT":    (["latitude", "longitude"], ar_ivt)},
        coords={"latitude": lat[:, 0].astype(np.float32),
                "longitude": lon[0, :].astype(np.float32)},
    )
    ds.to_netcdf(output_path)
    return os.path.getsize(output_path) / 1024


def consolidate_monthly_ar(save_dir, model_dirs, ym):
    """将单文件 _ar.nc 拼接为月度 AR NetCDF."""
    from pathlib import Path
    sp = Path(save_dir) / ym

    for _, subdir in model_dirs.items():
        ar_files = sorted((sp / subdir).rglob("*_ar.nc"))
        if not ar_files:
            logging.warning("AR consolidate %s: no files", subdir)
            continue

        datasets = []
        for f in ar_files:
            ds = xr.open_dataset(f)
            # 从文件名提取时间: {date}_{model}_t{time}_step{step}_ar.nc
            fname = f.name
            parts = fname.replace("_ar.nc", "").split("_")
            date_str = parts[0]
            time_str = parts[2]  # t00, t06, ...
            step_str = parts[3]  # step0, step3, ...
            t_hour = int(time_str[1:])
            s_hour = int(step_str[4:])
            # 起报时间 + step = 有效时间
            import pandas as pd
            base = pd.Timestamp(f"{date_str} {t_hour:02d}:00:00")
            valid = base + pd.Timedelta(hours=s_hour)
            ds = ds.expand_dims(time=[valid])
            datasets.append(ds)

        monthly = xr.concat(datasets, dim="time")
        monthly = monthly.sortby("time")
        out_path = sp / f"AR_{subdir}_{ym}.nc"
        monthly.to_netcdf(out_path)
        sz_mb = os.path.getsize(out_path) / 1024 / 1024
        logging.info("AR monthly %s/%s  (%d timesteps, %.1fMB)",
                     ym, out_path.name, len(datasets), sz_mb)


def detect_ar_from_nc(ivt_nc_path, ar_nc_path, threshold_2d):
    """从 IVT NetCDF 读取数据，执行 AR 检测，保存 AR NetCDF."""
    ds = xr.open_dataset(ivt_nc_path)
    ivt_u = ds["IVT_u"].values
    ivt_v = ds["IVT_v"].values
    ivt = ds["IVT"].values
    lat1d = ds["latitude"].values
    lon1d = ds["longitude"].values
    ds.close()

    lat2d, lon2d = np.meshgrid(lon1d, lat1d)  # y=lat, x=lon
    lat2d = lat2d.T if lat2d.shape != ivt.shape else lat2d  # ensure shape match
    # 重构: lat2d (ny, nx), lon2d (ny, nx)
    lat2d = np.tile(lat1d[:, None], (1, len(lon1d)))
    lon2d = np.tile(lon1d[None, :], (len(lat1d), 1))

    plume, axis, center, ar_ivt = detect_ar_single(ivt_u, ivt_v, ivt, lat2d, lon2d, threshold_2d)
    size_kb = save_ar_nc(ar_nc_path, plume, axis, center, ar_ivt, lat2d, lon2d)
    return size_kb


def detect_all_ar(save_dir, model_dirs, threshold_dir, ym):
    """遍历已下载的 IVT NC，逐个检测 AR."""
    from pathlib import Path
    sp = Path(save_dir) / ym
    thresholds = _load_monthly_thresholds(threshold_dir)

    for _, subdir in model_dirs.items():
        src_dir = sp / subdir
        total = 0
        for nc_f in sorted(src_dir.rglob("*_ivt.nc")):
            # 提取月份
            month_val = int(ym[4:6])
            thresh_2d = _seasonal_threshold(thresholds, month_val - 1)

            ar_f = nc_f.parent / nc_f.name.replace("_ivt.nc", "_ar.nc")
            try:
                size_kb = detect_ar_from_nc(str(nc_f), str(ar_f), thresh_2d)
                logging.info("  AR %s/%s  (%.0f KB)", subdir, ar_f.name, size_kb)
                total += 1
            except Exception as e:
                logging.error("  AR FAIL %s: %s", ar_f.name, e)
        logging.info("AR done %s: %d files", subdir, total)