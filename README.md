# IFS / AIFS 气象数据下载

下载 ECMWF IFS 和 AIFS 气象预报数据（GRIB2格式）。

## 项目简介

- **2025-05-01 ~ 2025-08-31 历史数据**: `dl_2025.py`（azure源，一键ifs+aifs）
- **2026-05-01 ~ 2026-08-31 业务数据**: `dl_2026.py`（ecmwf源，一键ifs+aifs，每日）

过期文件用 `dl_miss.py` 从 azure 补。

## 数据参数

| 类型 | 参数 | 层数 |
|---|---|---|
| 单层(surface) | 2t, msl, tp, ssrd | 1 |
| 气压层(pressure) | q, u, v, t | 1000~50 hPa (9层) |
| 起报时刻 | 00, 06, 12, 18 UTC | |
| 预报步长 | 6, 12, 24, 48, 72 h | |


## 快速开始

```bash
# 1. 安装依赖
conda create -n ifs_aifs python=3.10
conda activate ifs_aifs
pip install -r requirements.txt

# 2. 预建目录结构（可选，下载时也会自动创建）
python scripts/setup.py 2026-05-01 2026-08-31

# 3. 日常下载（拉取最近5天 ifs + aifs-single）
python scripts/dl_2026.py

# 4. 补历史数据（2025-05~08，azure 源）
python scripts/dl_2025.py

# 5. 补缺口（ecmwf 源过期后从 azure 补）
python scripts/dl_miss.py 2026-05-01 2026-05-01
```

| 脚本 | 用途 | 运行频率 |
|---|---|---|
| `setup.py` | 预建目录 | 首次即可 |
| `dl_2026.py` | 下载最近5天（ecmwf源） | 每日 |
| `dl_2025.py` | 下载2025历史数据（azure源） | 一次性 |
| `dl_miss.py` | 补过期文件（azure源） | 按需 |

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
