"""
测试 AIFS 模型 (AIFS-Single, step=0) 从 ECMWF 源的下载能力和速度。

功能:
  AIFS 是 ECMWF 基于机器学习的预报模型。从 ecmwf 源下载 AIFS 数据,
  分别测试单一层变量、气压层变量、合并下载, 记录下载速度。

运行:
  python test/test_aifs.py

预期输出示例:
  ============================================================
    ECMWF 源 AIFS 模型 测速
  ============================================================

  [1/3] 单一层变量 (2t/msl/tp/ssrd, 4条消息)
    [aifs源 单一层变量] 耗时 2.8s, 文件大小 0.80MB, 下载速度 0.29MB/s
    -> PASS

  [2/3] 气压层变量 (q/u/v/t x9层, 36条消息)
    [aifs源 气压层变量] 耗时 9.5s, 文件大小 12.00MB, 下载速度 1.26MB/s
    -> PASS

  [3/3] 合并下载 (单一层+气压层, 40条消息)
    [aifs源 合并下载] 耗时 12.3s, 文件大小 12.80MB, 下载速度 1.04MB/s
    -> PASS

  --- 结果: 3/3 通过 ---
"""
import os
import time
import tempfile
from ecmwf.opendata import Client
from test_utils import (
    SINGLE_PARAMS, LEVEL_PARAMS, LEVELS, ALL_PARAMS,
    get_recent_date, verify_grib, download_and_measure, run_tests, TestFail,
)


def main():
    date = get_recent_date()
    print(f"测试日期: {date}")
    tmpdir = tempfile.mkdtemp(prefix="test_aifs_")

    client = lambda: Client(source="ecmwf", model="aifs-single")

    def test_single():
        target = os.path.join(tmpdir, "aifs_single.grib2")
        count, params = download_and_measure(
            client(), "aifs源 单一层变量", target,
            date=date, time=0, type="fc", step=0, param=SINGLE_PARAMS,
        )
        if count != len(SINGLE_PARAMS):
            raise TestFail(f"expected {len(SINGLE_PARAMS)} msgs, got {count}")
        if params != set(SINGLE_PARAMS):
            raise TestFail(f"param mismatch: {params ^ set(SINGLE_PARAMS)}")

    def test_pressure():
        target = os.path.join(tmpdir, "aifs_levels.grib2")
        count, params = download_and_measure(
            client(), "aifs源 气压层变量", target,
            date=date, time=0, type="fc", step=0,
            param=LEVEL_PARAMS, levelist=LEVELS,
        )
        expected = len(LEVEL_PARAMS) * len(LEVELS)
        if count != expected:
            raise TestFail(f"expected {expected} msgs, got {count}")
        if params != set(LEVEL_PARAMS):
            raise TestFail(f"param mismatch: {params ^ set(LEVEL_PARAMS)}")

    def test_combined():
        target = os.path.join(tmpdir, "aifs_combined.grib2")
        s = os.path.join(tmpdir, "s.grib2")
        l = os.path.join(tmpdir, "l.grib2")
        c = client()
        t0 = time.time()
        c.retrieve(date=date, time=0, type="fc", step=0, param=SINGLE_PARAMS, target=s)
        c.retrieve(date=date, time=0, type="fc", step=0, param=LEVEL_PARAMS, levelist=LEVELS, target=l)
        with open(target, "wb") as out:
            for t in (s, l):
                with open(t, "rb") as f:
                    out.write(f.read())
        os.remove(s)
        os.remove(l)
        elapsed = time.time() - t0
        size_mb = os.path.getsize(target) / (1024 * 1024)
        speed = size_mb / elapsed if elapsed > 0 else 0
        print(f"  [aifs源 合并下载] 耗时 {elapsed:.1f}s, 文件大小 {size_mb:.2f}MB, 下载速度 {speed:.2f}MB/s")

        count, params = verify_grib(target)
        expected = len(SINGLE_PARAMS) + len(LEVEL_PARAMS) * len(LEVELS)
        if count != expected:
            raise TestFail(f"expected {expected} msgs, got {count}")
        if params != set(ALL_PARAMS):
            raise TestFail(f"param mismatch: {params ^ set(ALL_PARAMS)}")

    ok = run_tests("ECMWF 源 AIFS 模型 测速", [
        ("单一层变量 (2t/msl/tp/ssrd, 4条消息)", test_single),
        ("气压层变量 (q/u/v/t x9层, 36条消息)", test_pressure),
        ("合并下载 (单一层+气压层, 40条消息)", test_combined),
    ])

    for f in os.listdir(tmpdir):
        os.remove(os.path.join(tmpdir, f))
    os.rmdir(tmpdir)

    if not ok:
        exit(1)


if __name__ == "__main__":
    main()