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
        "lat_0": 10, "lat_1": 55, "lon_0": 73, "lon_1": 160,
        "parallels": np.arange(10., 56., 10.),
        "meridians": np.arange(73., 161., 10.),
        "title": "East Asia",
    },
    "north_china": {
        "lat_0": 30, "lat_1": 50, "lon_0": 105, "lon_1": 125,
        "parallels": np.arange(30., 51., 5.),
        "meridians": np.arange(105., 126., 5.),
        "title": "North China",
    },
}

BJ_LON, BJ_LAT = 116.4, 39.9
AXIS_COLOR = "purple"

# 模型展示名 (老师要求)
MODEL_NAMES = {
    "ifs": "数值天气预报模型(IFS)",
    "aifs-single": "人工智能预报模型(AIFS)",
}

# ── AR 时间连续性平滑 (方案 B: 高斯窗口投票 + IVT 约束 + 只补不删) ──
# 每格点: score[t] = Σ w_k × AR[t+k] (窗口 5, 边界归一化)
# 补 AR: score ≥ 阈值 AND IVT ≥ 250; 原始 AR 恒保留
_AR_WEIGHTS = np.array([0.15, 0.25, 0.30, 0.20, 0.10])  # t-2..t+2
_AR_THRESHOLD = 0.25  # 窗口内有 AR 且 IVT 达标 → 补 (可调)
_AR_IVT_MIN = 250.0


def _compute_axis_center(plume, ivt):
    """对 (平滑) plume 计算河轴骨架 + IVT 加权质心.

    与原版 detect_ar 一致的精炼: skeletonize → 保留主干链(去分叉) →
    沿梯度偏移到 IVT 极大值 → 短段过滤; 质心为连通域 IVT 加权.
    返回: (axis_2d_bool, cent_cl_1d, cent_cn_1d)
    """
    from skimage.morphology import skeletonize
    from skimage.measure import label
    from scipy import ndimage
    from scipy.signal import convolve2d

    binary = plume.astype(bool)
    seg = label(binary, connectivity=2)

    # 1. 骨架
    skel = skeletonize(binary)

    # 2. 保留主干链 (去分叉): 按连通域长度取前 2 长
    lab_skel = label(skel, connectivity=2)
    sizes = np.bincount(lab_skel.ravel())
    if len(sizes) > 2:
        top = sorted(range(1, len(sizes)),
                     key=lambda i: sizes[i], reverse=True)[:2]
        skel = np.isin(lab_skel, top)

    # 3. 沿梯度偏移到 IVT 极大值 (detect_ar 的 _skeleton_refine 逻辑)
    grad_y = ndimage.sobel(ivt.astype(float), axis=0)
    grad_x = ndimage.sobel(ivt.astype(float), axis=1)
    norm = np.hypot(grad_x, grad_y)
    valid = norm > 0
    nx = np.where(valid, -grad_x / norm, 0)
    ny = np.where(valid, grad_y / norm, 0)

    kernel = np.ones((3, 3))
    nbr = convolve2d(skel.astype(int), kernel, mode="same") - 1
    branch = (nbr > 2) & skel

    y, x = np.where(skel)
    if len(y) > 0:
        shifts = np.linspace(-8, 8, 15)
        dy = (y[:, None] + ny[y, x][:, None] * shifts).round().astype(int)
        dx = (x[:, None] + nx[y, x][:, None] * shifts).round().astype(int)
        vd = ((dx >= 0) & (dx < ivt.shape[1]) & (dy >= 0) & (dy < ivt.shape[0]))
        vals = np.full(dy.shape, -np.inf)
        vals[vd] = ivt[dy[vd], dx[vd]]
        best = np.argmax(vals, axis=1)
        skel2 = np.zeros_like(skel, dtype=bool)
        for i, (yy, xx) in enumerate(zip(y, x)):
            if branch[yy, xx]:
                skel2[yy, xx] = True
            else:
                skel2[dy[i, best[i]], dx[i, best[i]]] = True
        skel = skel2

    # 4. 短段过滤 (<20 像素)
    lab_skel = label(skel, connectivity=2)
    sizes = np.bincount(lab_skel.ravel())
    for rid, sz in enumerate(sizes):
        if rid > 0 and sz < 20:
            skel[lab_skel == rid] = False

    # 5. 质心: 每连通域 IVT 加权 → 位置索引数组 (与 _read_ar 的 cl/cn 一致)
    cent = np.zeros_like(binary, dtype=int)
    for seg_n in range(1, np.max(seg) + 1):
        m = seg == seg_n
        w = ivt[m]
        wsum = w.sum()
        if wsum > 0:
            ys, xs = np.where(m)
            cy = int(np.sum(ys * w) / wsum)
            cx = int(np.sum(xs * w) / wsum)
            cent[cy, cx] += 1
    cl, cn = np.where(cent > 0)
    return skel, cl, cn


def _smooth_ar_temporal(plumes, ivts):
    """时间维高斯投票平滑 AR (只补不删).

    plumes: list of 2D bool (按 step 升序), ivts: list of 2D float
    返回: list of 2D bool (平滑后 plume)
    """
    n = len(plumes)
    out = []
    for t in range(n):
        score = np.zeros_like(plumes[0], dtype=float)
        total_w = 0.0
        for k, w in enumerate(_AR_WEIGHTS):
            idx = t + k - 2
            if 0 <= idx < n:
                score += w * plumes[idx]
                total_w += w
        score /= total_w  # 边界归一化
        smooth = plumes[t] | ((score >= _AR_THRESHOLD) & (ivts[t] >= _AR_IVT_MIN))
        out.append(smooth)
    return out

# ── 降水等级 (绿色系, 与 IVT 蓝黄橙红区分) ──
# 判断: 未来 12h 或 24h 累计达到任一阈值即标注
PRECIP_LEVELS = [  # (12h_min_mm, 24h_min_mm, color, 点大小)
    (15.0, 25.0, "#9CCC65", 6),    # 大雨
    (30.0, 50.0, "#43A047", 8),    # 暴雨
    (70.0, 100.0, "#1B5E20", 10),  # 大暴雨
    (140.0, 250.0, "#00897B", 12), # 特大暴雨
]
PRECIP_SKIP = 8  # 每 8 格点抽稀 (0.25° → 每 2° 一个点)


def _read_tp(grib_path):
    """从 grib 读 tp 场 (统一转 mm). 返回 2D 数组或 None.

    单位差异 (实测): IFS tp 单位 m, AIFS tp 单位 mm → 按 units 判断, 未知时按量级猜测.
    """
    if not grib_path or not os.path.exists(grib_path):
        return None
    import eccodes
    with open(grib_path, "rb") as f:
        while True:
            msg_id = eccodes.codes_grib_new_from_file(f)
            if msg_id is None:
                break
            if eccodes.codes_get(msg_id, "shortName") == "tp":
                ni = eccodes.codes_get(msg_id, "Ni")
                nj = eccodes.codes_get(msg_id, "Nj")
                vals = eccodes.codes_get_values(msg_id).reshape(nj, ni)
                try:
                    unit = eccodes.codes_get(msg_id, "units", ktype=str)
                except Exception:
                    unit = ""
                if unit == "m":
                    vals = vals * 1000.0
                elif unit in ("mm", "kg m-2", "kg m**-2"):
                    pass  # 已是 mm
                else:
                    # 未知单位: 按量级猜测 (m 值通常 < 50, mm 值通常 > 50)
                    if float(vals.max()) <= 50:
                        vals = vals * 1000.0
                eccodes.codes_release(msg_id)
                return vals
            eccodes.codes_release(msg_id)
    return None


def _precip_marks(ax, m, lon2d, lat2d, tp_now, tp_f12, tp_f24):
    """未来 12h/24h 降水分级, 绿色圆点标注在面板上.

    每格点: 12h 和 24h 两口径分别判断, 取满足的最高等级, 只标一次.
    """
    if tp_now is None:
        return
    p12 = tp_f12 - tp_now if tp_f12 is not None else None
    p24 = tp_f24 - tp_now if tp_f24 is not None else None
    if p12 is None and p24 is None:
        return

    # 逐格点计算最高等级 (从高到低判断)
    level = np.zeros(lon2d.shape, dtype=int)
    for lvl, (m12, m24, _, _) in enumerate(PRECIP_LEVELS, 1):
        hit = np.zeros(lon2d.shape, dtype=bool)
        if p12 is not None:
            hit |= p12 >= m12
        if p24 is not None:
            hit |= p24 >= m24
        level[hit & (level == 0)] = lvl  # 只填未定级的格点

    # 每个等级画一次 (抽稀)
    sub_level = level[::PRECIP_SKIP, ::PRECIP_SKIP]
    sub_lon = lon2d[::PRECIP_SKIP, ::PRECIP_SKIP]
    sub_lat = lat2d[::PRECIP_SKIP, ::PRECIP_SKIP]
    for lvl, (_, _, color, size) in enumerate(PRECIP_LEVELS, 1):
        ys, xs = np.where(sub_level == lvl)
        if len(ys) == 0:
            continue
        x, y = m(sub_lon[ys, xs], sub_lat[ys, xs])
        ax.scatter(x, y, s=size, c=color,
                   edgecolors="black" if size >= 10 else "none",
                   linewidths=0.4, zorder=6)

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
           title, region_name, tp_now=None, tp_f12=None, tp_f24=None):
    """画单个模型面板 (照搬导师 Basemap 风格). tp_*: 降水标注用 (None 则不标)."""
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
                    fontsize=12, color="white", textcolor="white", linewidth=0.1)
    m.drawmeridians(cfg["meridians"], labels=[0, 0, 0, 1],
                    fontsize=12, color="white", textcolor="white", linewidth=0.1)

    # 北京红星
    if region_name == "north_china":
        bx, by = m(BJ_LON, BJ_LAT)
        ax.plot(bx, by, marker="*", color="red", markersize=14, zorder=6)

    # 降水标注 (绿色圆点, 未来 12h/24h 累计分级)
    _precip_marks(ax, m, lon2d, lat2d, tp_now, tp_f12, tp_f24)

    # 子标题
    ax.set_title(title, fontsize=17, color="white", pad=8)
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


def visualize_one_step(ivt_ifs, ar_ifs, ivt_aifs, ar_aifs, png_path, region_name,
                       grib_ifs=None, grib_aifs=None, step_extra=(),
                       pl_i_s=None, pl_a_s=None):
    """双面板: 全球上下 (IFS上/AIFS下), 其他左右; 单 step → 单 PNG.

    grib_ifs/grib_aifs: 当前 step 的 grib 路径 (读 tp, 用于降水标注; None 则不标)
    step_extra: 额外 step 的 grib 路径列表, 对应 (N+12, N+24) 用于未来降水差分
    pl_i_s/pl_a_s: AR 时间平滑后的 plume (方案 B), None 则用原始 plume
    """
    cfg = REGIONS[region_name]

    ivt_i, lat1d_i, lon1d_i = _read_ivt(ivt_ifs)
    pl_i, ax_i, _, _, lat2d_i, lon2d_i, cl_i, cn_i = _read_ar(ar_ifs)
    ivt_a, lat1d_a, lon1d_a = _read_ivt(ivt_aifs)
    pl_a, ax_a, _, _, lat2d_a, lon2d_a, cl_a, cn_a = _read_ar(ar_aifs)
    if pl_i_s is not None:
        pl_i = pl_i_s
        ax_i, cl_i, cn_i = _compute_axis_center(pl_i, ivt_i)  # 平滑区重算河轴/质心
    if pl_a_s is not None:
        pl_a = pl_a_s
        ax_a, cl_a, cn_a = _compute_axis_center(pl_a, ivt_a)

    # 降水 tp: 当前 + 未来 (N+12, N+24)
    tp_i = _read_tp(grib_ifs)
    tp_a = _read_tp(grib_aifs)
    tp_i12 = _read_tp(step_extra[0]) if len(step_extra) > 0 else None
    tp_i24 = _read_tp(step_extra[1]) if len(step_extra) > 1 else None
    tp_a12 = _read_tp(step_extra[2]) if len(step_extra) > 2 else None
    tp_a24 = _read_tp(step_extra[3]) if len(step_extra) > 3 else None

    if region_name == "global":
        fig, (axT, axB) = plt.subplots(2, 1, figsize=(16, 9))
    else:
        fig, (axL, axR) = plt.subplots(1, 2, figsize=(16, 9))
    fig.patch.set_facecolor("black")

    step_str = str(Path(png_path).stem).split("_")[-1]  # stepN
    step_h = int(step_str.replace("step", ""))
    valid_time = _valid_time_from_path(ivt_ifs, step_h)
    model_i = MODEL_NAMES.get("ifs", "IFS")
    model_a = MODEL_NAMES.get("aifs-single", "AIFS")

    if region_name == "global":
        cs = _panel(axT, cfg, ivt_i, pl_i, ax_i, lat2d_i, lon2d_i, cl_i, cn_i,
                    f"{model_i} {valid_time}", region_name, tp_i, tp_i12, tp_i24)
        _panel(axB, cfg, ivt_a, pl_a, ax_a, lat2d_a, lon2d_a, cl_a, cn_a,
               f"{model_a} {valid_time}", region_name, tp_a, tp_a12, tp_a24)
        cbar_ax = [axT, axB]
    else:
        cs = _panel(axL, cfg, ivt_i, pl_i, ax_i, lat2d_i, lon2d_i, cl_i, cn_i,
                    f"{model_i} {valid_time}", region_name, tp_i, tp_i12, tp_i24)
        _panel(axR, cfg, ivt_a, pl_a, ax_a, lat2d_a, lon2d_a, cl_a, cn_a,
               f"{model_a} {valid_time}", region_name, tp_a, tp_a12, tp_a24)
        cbar_ax = [axL, axR]

    # 5 级色标: label 放大 2 倍 (13→26), 放左侧居中
    cbar = fig.colorbar(cs, ax=cbar_ax, fraction=0.03,
                        orientation="horizontal", extend="both", pad=0.05)
    cbar.ax.tick_params(labelsize=14, colors="white")
    cbar.ax.set_xlabel("IVT (kg m$^{-1}$ s$^{-1}$)", size=26, color="white",
                       loc="left")

    os.makedirs(os.path.dirname(png_path), exist_ok=True)
    fig.savefig(png_path, dpi=150, bbox_inches="tight", facecolor="black")
    plt.close(fig)
    return os.path.getsize(png_path) / 1024


def _load_smooth_plumes(ivt_dir, ar_dir, max_step):
    """读全部时次 plume+ivt → 时间平滑 → {step_tag: smooth_plume_2d}."""
    files = sorted(ivt_dir.glob("*_ivt.nc"))
    recs = []
    for f in files:
        step_n = f.name.replace("_ivt.nc", "").rsplit("_", 1)[-1]
        step_h = int(step_n.replace("step", ""))
        if step_h > max_step:
            continue
        ar_f = ar_dir / f.name.replace("_ivt.nc", "_ar.nc")
        if not ar_f.exists():
            continue
        ivt, _, _ = _read_ivt(str(f))
        plume, _, _, _, _, _, _, _ = _read_ar(str(ar_f))
        recs.append((step_n, plume, ivt))
    if not recs:
        return {}
    recs.sort(key=lambda r: int(r[0].replace("step", "")))
    smooth = _smooth_ar_temporal([r[1] for r in recs], [r[2] for r in recs])
    return {r[0]: s for r, s in zip(recs, smooth)}


def _vis_worker(args):
    """单图 worker (mp.Pool 需要顶层函数). 返回日志消息字符串."""
    (ivt_i, ar_i, ivt_a, ar_a, png_f, region_name,
     grib_ifs, grib_aifs, step_extra, pl_i_s, pl_a_s) = args
    try:
        kb = visualize_one_step(ivt_i, ar_i, ivt_a, ar_a, png_f, region_name,
                                grib_ifs, grib_aifs, step_extra, pl_i_s, pl_a_s)
        return f"  VIS {region_name}/{Path(png_f).name} ({kb:.0f} KB)"
    except Exception as e:
        return f"  VIS FAIL {region_name}/{Path(png_f).name}: {e}"


def visualize_all(save_dir, model_dirs, max_step=144):
    """对每个区域生成双面板 PNG (默认到 step=144), 每次运行覆盖旧图.

    降水标注: 需当前/未来 grib 的 tp (N+12, N+24), 缺失则不标.
    AR 平滑: 方案 B 时间高斯投票 (只补不删), 见 _smooth_ar_temporal.
    """
    import shutil
    sp = Path(save_dir)
    fig_root = sp / "figures"
    if fig_root.exists():
        shutil.rmtree(fig_root)

    # 目录: figures/{region}/step{N}.png
    ivt_dir = {subdir: sp / "ivt" / subdir for subdir in model_dirs.values()}
    ar_dir = {subdir: sp / "ar" / subdir for subdir in model_dirs.values()}
    grib_dir = {subdir: sp / subdir for subdir in model_dirs.values()}
    sub_ifs = model_dirs["ifs"]
    sub_aifs = model_dirs["aifs-single"]

    # AR 时间平滑 (只补不删): 全时次预读
    smooth_i = _load_smooth_plumes(ivt_dir[sub_ifs], ar_dir[sub_ifs], max_step)
    smooth_a = _load_smooth_plumes(ivt_dir[sub_aifs], ar_dir[sub_aifs], max_step)

    # 收集任务
    tasks = []
    for region_name in REGIONS:
        out_dir = fig_root / region_name
        out_dir.mkdir(parents=True, exist_ok=True)

        ivt_files_ifs = sorted(ivt_dir[sub_ifs].glob("*_ivt.nc"))
        for ivt_i in ivt_files_ifs:
            step_tag = ivt_i.name.replace("_ivt.nc", "")
            step_n = step_tag.rsplit("_", 1)[-1]  # step24
            step_h = int(step_n.replace("step", ""))

            # 图只画到 max_step (额外 step 仅用于降水差分)
            if step_h > max_step:
                continue

            ar_i = ar_dir[sub_ifs] / ivt_i.name.replace("_ivt.nc", "_ar.nc")
            ivt_a = ivt_dir[sub_aifs] / ivt_i.name.replace("_ifs_", "_aifs-single_")
            ar_a = ar_dir[sub_aifs] / ivt_a.name.replace("_ivt.nc", "_ar.nc")

            if not (ar_i.exists() and ivt_a.exists() and ar_a.exists()):
                logging.warning("  VIS skip %s (missing pairs)", step_n)
                continue

            png_f = out_dir / f"{step_n}.png"

            # 降水差分用 grib: 当前 N, 未来 N+12, N+24
            grib_ifs = grib_dir[sub_ifs] / ivt_i.name.replace("_ivt.nc", ".grib2")
            grib_aifs = grib_dir[sub_aifs] / ivt_a.name.replace("_ivt.nc", ".grib2")

            base_tag_i = ivt_i.name.replace("_ivt.nc", "").rsplit("_", 1)[0]  # ..._step 前的部分
            base_tag_a = ivt_a.name.replace("_ivt.nc", "").rsplit("_", 1)[0]

            g12_i = grib_dir[sub_ifs] / f"{base_tag_i}_step{step_h + 12}.grib2"
            g24_i = grib_dir[sub_ifs] / f"{base_tag_i}_step{step_h + 24}.grib2"
            g12_a = grib_dir[sub_aifs] / f"{base_tag_a}_step{step_h + 12}.grib2"
            g24_a = grib_dir[sub_aifs] / f"{base_tag_a}_step{step_h + 24}.grib2"

            step_extra = (
                str(g12_i) if g12_i.exists() else None,
                str(g24_i) if g24_i.exists() else None,
                str(g12_a) if g12_a.exists() else None,
                str(g24_a) if g24_a.exists() else None,
            )

            tasks.append((str(ivt_i), str(ar_i), str(ivt_a), str(ar_a),
                          str(png_f), region_name,
                          str(grib_ifs) if grib_ifs.exists() else None,
                          str(grib_aifs) if grib_aifs.exists() else None,
                          step_extra,
                          smooth_i.get(step_n), smooth_a.get(step_n)))

    if not tasks:
        logging.info("VIS done: 0 PNGs (no tasks)")
        return

    # 多进程并行 (每进程独立 matplotlib, 提速 ~N 倍; 内存约 N × 1GB, 视服务器内存调)
    import multiprocessing as mp
    NPROC = min(15, len(tasks))
    logging.info("VIS parallel: %d tasks, %d processes", len(tasks), NPROC)
    with mp.Pool(processes=NPROC) as pool:
        for msg in pool.imap_unordered(_vis_worker, tasks):
            logging.info(msg)

    logging.info("VIS done: %d PNGs → %s", len(tasks), fig_root)
