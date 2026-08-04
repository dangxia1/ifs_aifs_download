"""台风巴威 (2026-07) 华北暴雨个例图 — 提取 7/13-14 step=0 画华北双面板图.

数据源: ec_monthly_ivt/202607/{ifs,aifs}/step0/ (月度项目产物)
输出:   /shared_data/zongshen/bavi_case/  (双面板 IFS|AIFS, 华北区域)

用法: python bavi_case.py [起始日] [结束日]
      默认: 2026-07-13 ~ 2026-07-14
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from visualize_ivt import visualize_one_step

BASE = "/shared_data/zongshen/ec_monthly_ivt/202607"
OUT = "/shared_data/zongshen/bavi_case"
DATES = ["2026-07-13", "2026-07-14"]
TIMES = [0, 6, 12, 18]
REGION = "north_china"


def _bavi_worker(args):
    """单图 worker (mp.Pool 需要顶层函数)."""
    ivt_i, ar_i, ivt_a, ar_a, out, region = args
    try:
        visualize_one_step(ivt_i, ar_i, ivt_a, ar_a, out, region)
        return f"saved {out}"
    except Exception as e:
        return f"FAIL {out}: {e}"

# 可选命令行参数指定日期范围
if len(sys.argv) >= 3:
    DATES = sys.argv[1:3]

os.makedirs(OUT, exist_ok=True)

# 收集任务
tasks = []
for date in DATES:
    for t in TIMES:
        stem_i = f"{date}_ifs_t{t:02d}_step0"
        stem_a = f"{date}_aifs-single_t{t:02d}_step0"

        ivt_i = f"{BASE}/ifs/step0/{stem_i}_ivt.nc"
        ar_i = f"{BASE}/ifs/step0/{stem_i}_ar.nc"
        ivt_a = f"{BASE}/aifs/step0/{stem_a}_ivt.nc"
        ar_a = f"{BASE}/aifs/step0/{stem_a}_ar.nc"

        if not all(os.path.exists(p) for p in [ivt_i, ar_i, ivt_a, ar_a]):
            print(f"skip {date} t{t:02d}z (missing files)")
            continue

        # 输出名以 step0 结尾 (visualize_one_step 从文件名解析 step)
        out = f"{OUT}/{date.replace('-', '')}_{t:02d}z_step0.png"
        tasks.append((ivt_i, ar_i, ivt_a, ar_a, out, REGION))

# 多进程并行 (8 张同时跑)
if tasks:
    import multiprocessing as mp
    NPROC = min(8, len(tasks))
    print(f"{len(tasks)} 张图, {NPROC} 进程并行 → {OUT}")
    with mp.Pool(processes=NPROC) as pool:
        for i, _ in enumerate(pool.imap_unordered(_bavi_worker, tasks)):
            print(f"  [{i+1}/{len(tasks)}] 完成")
    print(f"Done: {len(tasks)} 张 → {OUT}")
else:
    print("无可用任务 (数据缺失)")