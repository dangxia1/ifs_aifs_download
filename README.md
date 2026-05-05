# IFS / AIFS 气象数据下载

下载 ECMWF IFS 和 AIFS 气象预报数据（GRIB2格式）。

## 项目简介

- **2025-05-01 ~ 2025-08-31 历史数据**: `dl_2025.py`（azure源，计划中）
- **2026-05-01 ~ 2026-08-31 业务数据**: `dl_2026.py`（ecmwf源，已完成）

无需参数，一键下载 ifs + aifs-single。过期文件用 `dl_miss.py` 从 azure 补。

## 数据参数

| 类型 | 参数 | 层数 |
|---|---|---|
| 单层(surface) | 2t, msl, tp, ssrd | 1 |
| 气压层(pressure) | q, u, v, t | 1000~50 hPa (9层) |
| 起报时刻 | 00, 06, 12, 18 UTC | |
| 预报步长 | 6, 12, 24, 48, 72 h | |

## 环境配置

```bash
conda create -n ifs_aifs python=3.10
conda activate ifs_aifs
pip install -r requirements.txt
```

## 项目结构

```
scripts/      # 下载脚本
docs/         # 文档与计划
test/         # 测试脚本（数据源验证、下载测试）
data/raw/     # 下载数据输出目录
log/          # 下载日志
```

## 文档

- [ecmwf-opendata 官方API](docs/ecmwf-opendata.md)
- [数据源选择与GRIB校验](docs/数据源、校验和下载.md)
- [dl_2025.py 实现计划](docs/plan_dl_2025.md)
- [Git 使用指南](docs/git指南.md)

## License

下载数据遵循 ECMWF CC BY 4.0 许可。
