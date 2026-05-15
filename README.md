# IFS / AIFS 气象数据下载

下载 ECMWF IFS 和 AIFS 气象预报数据（GRIB2格式）。

## 项目简介

- **2025-03-15 ~ 2025-10-31 历史数据(汛期)**: `dl_anytime.py`（azure 源）
- **2026-04-01 ~ 2026-10-31 业务数据(汛期)**: `dl_2026.py`（ecmwf 源，每日）

过期文件用 `dl_anytime.py` 从 azure 补。

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
python scripts/setup.py 2026-04-01 2026-10-31

# 3. 日常下载（拉取最近3-4天 ifs + aifs-single）
python scripts/dl_2026.py

# 4. 补历史数据（2025-05~08，azure 源）
python scripts/dl_anytime.py 2025-03-15 2025-10-31

# 5. 补缺口（ecmwf 源过期后从 azure 补）
python scripts/dl_anytime.py 2026-04-01 2026-04-01
```

| 脚本 | 用途 | 运行频率 |
|---|---|---|
| `setup.py` | 预建目录 | 首次即可 |
| `dl_2026.py` | 下载最近3-4天（ecmwf源） | 每日 |
| `dl_anytime.py` | 任意日期下载（azure 源） | 按需 |
| `check_miss.py` | 扫描缺失文件 | 按需 |

## 项目结构

```
scripts/      # 下载脚本 + config.yaml 配置文件
docs/         # 文档与计划
test/         # 独立测速脚本（直接运行验证各数据源下载）
data/raw/     # 下载数据输出目录
log/          # 下载日志
```

## 文档

- [ecmwf-opendata 官方API](docs/ecmwf-opendata.md)
- [数据源选择与GRIB校验](docs/数据源、校验和下载.md)
- [项目进展与脚本指南](docs/项目进展.md)
- [研究方向与执行计划](docs/研究方向.md)
- [Git 使用指南](docs/git指南.md)
- [Cron 定时运行](docs/cron.md)

## License

下载数据遵循 ECMWF CC BY 4.0 许可。
