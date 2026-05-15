"""
测试 Azure 源 (IFS 模型, 历史数据) 的下载能力和速度, 以及跨源一致性。

功能:
  从 Azure blob 下载 IFS 历史数据, 测试单一层变量、气压层变量、合并下载。
  额外做跨源对比: 同一日期从 ecmwf 和 azure 分别下载, 验证参数集合一致。

运行:
  python test/test_azure.py

预期输出示例:
  ============================================================
    Azure 源 (IFS 历史数据) 测速
  ============================================================

  [1/4] 单一层变量 (2t/msl/tp/ssrd, 4条消息)
    [azure源 单一层变量] 耗时 1.5s, 文件大小 1.00MB, 下载速度 0.67MB/s
    -> PASS

  [2/4] 气压层变量 (q/u/v/t x9层, 36条消息)
    [azure源 气压层变量] 耗时 4.3s, 文件大小 15.00MB, 下载速度 3.49MB/s
    -> PASS

  [3/4] 合并下载 (单一层+气压层, 40条消息)
    [azure源 合并下载] 耗时 5.8s, 文件大小 16.00MB, 下载速度 2.76MB/s
    -> PASS

  [4/4] 跨源对比 (ecmwf vs azure 同一日期, 参数集合是否一致)
    [ecmwf源 跨源对比] 耗时 12.0s, 文件大小 16.00MB, 下载速度 1.33MB/s
    [azure源 跨源对比] 耗时 4.5s, 文件大小 16.00MB, 下载速度 3.56MB/s
    -> PASS

  --- 结果: 4/4 通过 ---
"""
import os
import time
import tempfile
from ecmwf.opendata import Client
from test_utils import (
    SINGLE_PARAMS, LEVEL_PARAMS, LEVELS, ALL_PARAMS,
    get_recent_date, get_azure_date, verify_grib, download_and_measure,
    run_tests, TestFail,
)


def _download_all(client, label, tmpdir, suffix):
    """下载单一层 + 气压层并合并为一个文件, 输出测速。返回 (count, params)。"""
    target = os.path.join(tmpdir, f"{suffix}.grib2")
    s = os.path.join(tmpdir, f"s_{suffix}.grib2")
    l = os.path.join(tmpdir, f"l_{suffix}.grib2")
    t0 = time.time()
    client.retrieve(date=date, time=0, type="fc", step=0, param=SINGLE_PARAMS, target=s)
    client.retrieve(date=date, time=0, type="fc", step=0, param=LEVEL_PARAMS, levelist=LEVELS, target=l)
    with open(target, "wb") as out:
        for t in (s, l):
            with open(t, "rb") as f:
                out.write(f.read())
    os.remove(s)
    os.remove(l)
    elapsed = time.time() - t0
    size_mb = os.path.getsize(target) / (1024 * 1024)
    speed = size_mb / elapsed if elapsed > 0 else 0
    print(f"  [{label}] 耗时 {elapsed:.1f}s, 文件大小 {size_mb:.2f}MB, 下载速度 {speed:.2f}MB/s")
    return verify_grib(target)


date = None  # 跨源对比需要同一个 recent_date


def main():
    global date
    date = get_recent_date()
    azure_date = get_azure_date()
    print(f"Azure 测试日期: {azure_date}")
    tmpdir = tempfile.mkdtemp(prefix="test_azure_")

    def test_single():
        target = os.path.join(tmpdir, "azure_single.grib2")
        count, params = download_and_measure(
            Client(source="azure"), "azure源 单一层变量", target,
            date=azure_date, time=0, type="fc", step=0, param=SINGLE_PARAMS,
        )
        if count != len(SINGLE_PARAMS):
            raise TestFail(f"expected {len(SINGLE_PARAMS)} msgs, got {count}")
        if params != set(SINGLE_PARAMS):
            raise TestFail(f"param mismatch: {params ^ set(SINGLE_PARAMS)}")

    def test_pressure():
        target = os.path.join(tmpdir, "azure_levels.grib2")
        count, params = download_and_measure(
            Client(source="azure"), "azure源 气压层变量", target,
            date=azure_date, time=0, type="fc", step=0,
            param=LEVEL_PARAMS, levelist=LEVELS,
        )
        expected = len(LEVEL_PARAMS) * len(LEVELS)
        if count != expected:
            raise TestFail(f"expected {expected} msgs, got {count}")
        if params != set(LEVEL_PARAMS):
            raise TestFail(f"param mismatch: {params ^ set(LEVEL_PARAMS)}")

    def test_combined():
        count, params = _download_all(
            Client(source="azure"), "azure源 合并下载", tmpdir, "azure_combined",
        )
        expected = len(SINGLE_PARAMS) + len(LEVEL_PARAMS) * len(LEVELS)
        if count != expected:
            raise TestFail(f"expected {expected} msgs, got {count}")
        if params != set(ALL_PARAMS):
            raise TestFail(f"param mismatch: {params ^ set(ALL_PARAMS)}")

    def test_cross_source():
        print(f"  跨源对比日期: {date}")
        _, azure_p = _download_all(
            Client(source="azure"), "azure源 跨源对比", tmpdir, "azure_cross",
        )
        _, ecmwf_p = _download_all(
            Client(source="ecmwf"), "ecmwf源 跨源对比", tmpdir, "ecmwf_cross",
        )
        if azure_p != ecmwf_p:
            raise TestFail(
                f"only azure: {azure_p - ecmwf_p}, only ecmwf: {ecmwf_p - azure_p}"
            )

    ok = run_tests("Azure 源 (IFS 历史数据) 测速", [
        ("单一层变量 (2t/msl/tp/ssrd, 4条消息)", test_single),
        ("气压层变量 (q/u/v/t x9层, 36条消息)", test_pressure),
        ("合并下载 (单一层+气压层, 40条消息)", test_combined),
        ("跨源对比 (ecmwf vs azure 同一日期, 参数集合是否一致)", test_cross_source),
    ])

    for f in os.listdir(tmpdir):
        os.remove(os.path.join(tmpdir, f))
    os.rmdir(tmpdir)

    if not ok:
        exit(1)


if __name__ == "__main__":
    main()