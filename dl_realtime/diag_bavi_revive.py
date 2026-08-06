"""巴威个例 48h 恢复诊断 (2026-08-06): 一次输出 IFS/AIFS 每时次状态 + 48h 卡点.

用法 (服务器): python diag_bavi_revive.py
输出: 每时次 原始/平滑后 AR 格数; step048 若空, 打印消亡恢复三个条件
(先验帧有AR? / 高斯先验≥0.5格数 / 轴长km vs 1500 / IVT最大 vs 500) →
直接定位卡在哪个条件, 便于调阈值.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dl_lastmonth_cal_ivt"))
from visualize_ivt import (_read_ivt, _read_ar, _smooth_ar_temporal,
                           _compute_axis_center, _axis_length_km,
                           REVIVE_PRIOR_TH, AXIS_LEN_REVIVE_KM,
                           IVT_REVIVE_MAX)

RUN_DATE = "2026-07-09"
RUN_TIME = 0
PLOT_STEPS = list(range(0, 73, 6))  # 13 时次
OUT_DATA = "/shared_data/zongshen/ec_realtime/bavi_forecast"


def _series(model_dir, tag):
    plumes, ivts, axes, lat2d, lon2d = [], [], [], None, None
    for s in PLOT_STEPS:
        base = (f"{OUT_DATA}/{model_dir}/step{s}/"
                f"{RUN_DATE}_{tag}_t{RUN_TIME:02d}_step{s}")
        pl, ax_, _, _, lat2d_, lon2d_, _, _ = _read_ar(base + "_ar.nc")
        ivt, _, _ = _read_ivt(base + "_ivt.nc")
        plumes.append(pl)
        ivts.append(ivt)
        axes.append(ax_)
        lat2d, lon2d = lat2d_, lon2d_
    smooth = _smooth_ar_temporal(plumes, ivts, axes=axes,
                                 lat2d=lat2d, lon2d=lon2d)
    return plumes, smooth, ivts, lat2d, lon2d


def main():
    for model_dir, tag in (("ifs", "ifs"), ("aifs", "aifs-single")):
        print(f"===== {tag} =====")
        plumes, smooth, ivts, lat2d, lon2d = _series(model_dir, tag)
        for s, p, sm in zip(PLOT_STEPS, plumes, smooth):
            mark = "  ← 空时次" if not sm.any() else ""
            print(f"  step{s:03d}: 原始 {int(p.sum()):6d} 格 → "
                  f"平滑 {int(sm.sum()):6d} 格{mark}")
        t = PLOT_STEPS.index(48)
        if smooth[t].any():
            print(f"  step048 平滑后非空 ({int(smooth[t].sum())} 格) → "
                  f"图上应画有 AR, 不是空时次问题")
            continue
        # 消亡恢复三条件逐项检查 (与 _revive_series 逻辑一致)
        refs = ((t - 1, 0.5), (t + 1, 0.3), (t + 2, 0.2))
        acc, wsum, have = None, 0.0, []
        for r, w in refs:
            if 0 <= r < len(smooth) and smooth[r].any():
                acc = w * smooth[r] if acc is None else acc + w * smooth[r]
                wsum += w
                have.append(r)
        if acc is None:
            print(f"  [卡点1] 先验帧均无 AR (参考 {[r for r, _ in refs if 0 <= r < len(smooth)]}, "
                  f"有AR的: {have}) → 无素材可恢复")
            continue
        prior = acc / max(wsum, 1e-9)
        prior_bool = prior >= REVIVE_PRIOR_TH
        print(f"  先验: 有AR帧 {have}, 加权和 {wsum:.1f}, "
              f"prior≥{REVIVE_PRIOR_TH} 格 {int(prior_bool.sum())}")
        if not prior_bool.any():
            print(f"  [卡点2] 高斯先验达不到 {REVIVE_PRIOR_TH} → 先验太弱")
            continue
        ax_ref, _, _ = _compute_axis_center(prior_bool, ivts[t])
        len_km = _axis_length_km(ax_ref, lat2d, lon2d)
        ref_max = float(np.nanmax(ivts[t][prior_bool]))
        print(f"  轴长 {len_km:.0f} km (需 > {AXIS_LEN_REVIVE_KM:.0f}), "
              f"先验范围当前 IVT 最大 {ref_max:.0f} (需 > {IVT_REVIVE_MAX:.0f})")
        if not (len_km > AXIS_LEN_REVIVE_KM and ref_max > IVT_REVIVE_MAX):
            print(f"  [卡点3] 轴长或 IVT 不达标 → 调 AXIS_LEN_REVIVE_KM / IVT_REVIVE_MAX")
        else:
            print(f"  [卡点4] 条件全过但熵权/退化兜底无输出 → 看 _revive_ar_mask")


if __name__ == "__main__":
    main()
