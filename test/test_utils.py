"""
共享工具: 测试参数、日期、GRIB 校验、下载测速。

功能:
  1. 气象参数常量: 单一层变量 4 个, 气压层变量 4 个 × 9 层
  2. 日期获取: 实时源用 UTC 前 2 天, Azure 用 UTC 前一年
  3. verify_grib(): 用 eccodes 校验 grib2 文件, 返回 (消息数, {参数集合})
  4. download_and_measure(): 下载 + 输出耗时/大小/速度

预期输出:
  - get_recent_date() → "2026-05-13" (运行时 UTC 减 2 天)
  - get_azure_date() → "2025-06-15"
  - verify_grib(path) → (40, {"2t","msl","tp","ssrd","q","u","v","t"})
"""
import os
import time
import tempfile
from datetime import datetime, timedelta, timezone

# ── 测试参数 ──────────────────────────────────────────
SINGLE_PARAMS = ["2t", "msl", "tp", "ssrd"]          # 单一层: 2米气温, 海平面气压, 总降水, 地表太阳辐射
LEVEL_PARAMS = ["q", "u", "v", "t"]                   # 气压层: 比湿, 纬向风, 经向风, 气温
LEVELS = [1000, 925, 850, 700, 500, 300, 250, 200, 50]
ALL_PARAMS = SINGLE_PARAMS + LEVEL_PARAMS

# ── 日期工具 ──────────────────────────────────────────
def get_recent_date():
    """UTC 前 2 天, 保证在 ecmwf 实时源 ~4 天保留窗口内。"""
    return (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d")

def get_azure_date():
    """Azure 上一定存在的固定历史日期。"""
    return "2025-06-15"

# ── GRIB 校验 ─────────────────────────────────────────
def verify_grib(path):
    """用 eccodes 打开 grib2 文件, 返回 (消息条数, {参数名集合})。"""
    import eccodes
    with open(path, "rb") as f:
        params = []
        while True:
            msg_id = eccodes.codes_grib_new_from_file(f)
            if msg_id is None:
                break
            params.append(eccodes.codes_get(msg_id, "shortName"))
            eccodes.codes_release(msg_id)
    return len(params), set(params)

# ── 下载与测速 ────────────────────────────────────────
def download_and_measure(client, label, target, **retrieve_kwargs):
    """下载 GRIB 并输出测速信息。返回 (count, params)。"""
    t0 = time.time()
    client.retrieve(**retrieve_kwargs, target=target)
    elapsed = time.time() - t0
    size_mb = os.path.getsize(target) / (1024 * 1024)
    speed = size_mb / elapsed if elapsed > 0 else 0
    print(f"  [{label}] 耗时 {elapsed:.1f}s, 文件大小 {size_mb:.2f}MB, 下载速度 {speed:.2f}MB/s")
    return verify_grib(target)

# ── 运行辅助 ──────────────────────────────────────────
class TestFail(Exception):
    """测试失败异常。"""
    pass

def run_tests(name, tests):
    """按顺序运行一组测试, 打印结果。"""
    print(f"{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    passed = 0
    for i, (desc, fn) in enumerate(tests, 1):
        try:
            print(f"\n[{i}/{len(tests)}] {desc}")
            fn()
            print(f"  -> PASS")
            passed += 1
        except Exception as e:
            print(f"  -> FAIL: {e}")
    print(f"\n--- 结果: {passed}/{len(tests)} 通过 ---\n")
    return passed == len(tests)