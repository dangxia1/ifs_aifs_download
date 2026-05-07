# pytest 自动化测试思路

将 `test/` 下手动测试脚本改为 pytest 自动化测试。

## 文件规划

```
test/
├── conftest.py       # 共享 fixtures、常量、工具函数
├── test_ecmwf.py     # ecmwf 源 (IFS) 3 个测试
├── test_aifs.py      # AIFS 模型 1 个测试
└── test_azure.py     # Azure 源 + 跨源对比 4 个测试
```

旧 6 个 `dl_*.py` 脚本删除。

## conftest.py

- **常量**: `SINGLE_PARAMS` / `LEVEL_PARAMS` / `LEVELS` / `ALL_PARAMS`，与 `dl_utils.py` 一致
- **`recent_date` fixture**: 自动取 2 天前日期，确保 ecmwf 源在 4 天保留窗口内
- **`azure_date` fixture**: 选取 `recent_date`参数的上一年同日日期，数据在 Azure 上始终可用
- **`verify_grib(path)`**: 读取 GRIB 文件，返回 `(消息数, 参数集合)` 供 assert
- **`integration` marker**: 所有测试标记 `pytest.mark.integration`，CI 中可用 `pytest -m "not integration"` 跳过

## test_ecmwf.py — ecmwf 源 (IFS)

| 测试 | 内容 |
|---|---|
| `test_download_single_level` | step=0 下载单层 4 参数，验证 4 条消息、参数完整 |
| `test_download_pressure_levels` | step=0 下载气压层 4×9=36 条，验证数量、参数覆盖 |
| `test_download_combined` | 分两次调 API → 磁盘合并 → 单文件含全部 40 条消息 |

## test_aifs.py — AIFS 模型

| 测试 | 内容 |
|---|---|
| `test_aifs_combined` | `Client(source="ecmwf", model="aifs-single")` 下载合并，验证 40 条 |

## test_azure.py — Azure 源

| 测试 | 内容 |
|---|---|
| `test_download_single_level` | Azure 单层下载，验证 4 条消息 |
| `test_download_pressure_levels` | Azure 气压层下载，验证 36 条 |
| `test_download_combined` | Azure 合并下载，验证 40 条 |
| `test_cross_source_match` | 同一 `recent_date` 分别从 ecmwf 和 azure 下载，assert 参数集合一致 |

## 运行

```bash
pytest test/ -v                     # 全部
pytest test/ -v -m integration      # 仅集成测试（默认）
pytest test/ -v -m "not integration"  # 跳过需联网的测试
```

## 依赖

`requirements.txt` 新增 `pytest>=8`。