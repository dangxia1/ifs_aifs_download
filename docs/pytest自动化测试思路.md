# pytest 自动化测试

## 什么是"自动化"

之前的 `test/dl_*.py` 是手动脚本——每次要打开文件、一个个运行、肉眼看出不出错。改为 pytest 后：

- `pytest test/` 一条命令自动发现并运行所有测试
- 每个测试有明确的 **PASSED / FAILED** 结果，不用肉眼判断
- 测试失败时自动打印预期值 vs 实际值

## 怎么用

```bash
conda activate ifs_aifs
cd ifs-aifs-ai

pytest test/ -v              # 运行全部测试，显示详细结果
pytest test/test_ecmwf.py -v # 只跑 ecmwf 源相关测试
pytest test/ -v -k "aifs"    # 只跑名字含 "aifs" 的测试
pytest test/ -v -m "not integration"  # 跳过需联网的测试（不会真跳过，见下方说明）
```

所有测试默认标记为 `integration`（需要网络），所以 `-m integration` 等于全跑。

## 测试内容

```
test/
├── conftest.py       # 公共 fixtures（自动取2天前日期、verify_grib校验函数）
├── test_ecmwf.py     # ecmwf 源：单层 / 气压层 / 合并下载
├── test_aifs.py      # AIFS 模型：合并下载
└── test_azure.py     # Azure 源：单层 / 气压层 / 合并下载 / 跨源对比
```

| 测试 | 做什么 | 验证什么 |
|---|---|---|
| `test_download_single_level` | step=0 下载 2t/msl/tp/ssrd | 得到 4 条 GRIB 消息，参数不缺失 |
| `test_download_pressure_levels` | step=0 下载 q/u/v/t × 9 层 | 得到 36 条消息 |
| `test_download_combined` | 分两次下载 → 合并为单文件 | 合并后含全部 40 条消息 |
| `test_aifs_combined` | 同上，用 `model="aifs-single"` | AIFS 数据也完整 |
| `test_cross_source_match` | 同一日期 ecmwf vs azure | 两源参数集合一致 |

## 怎么看结果

```bash
$ pytest test/ -v
test/test_ecmwf.py::test_download_single_level PASSED     [ 12%]
test/test_ecmwf.py::test_download_pressure_levels PASSED   [ 25%]
...
test/test_azure.py::test_cross_source_match FAILED         [100%]

FAILED test/test_azure.py::test_cross_source_match - AssertionError: Mismatch — only azure: set()
  only ecmwf: {'t'}
```

- 全绿 = 数据源正常，API 无变化
- 偶尔 FAIL 一两个 = 可能是网络波动，重跑一次
- 大批 FAIL = API 或数据格式变了，需要排查