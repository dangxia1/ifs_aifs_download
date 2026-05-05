# dl_2026.py 实现计划

## 与 dl_2025.py 的差异

| | dl_2025.py | dl_2026.py |
|---|---|---|
| 日期范围 | 2025-05-01 ~ 2025-08-31 | 2026-05-01 ~ 2026-08-31 |
| 数据源 | azure（历史数据） | **ecmwf**（近/未来数据，速度快） |
| 模型 | `--model` 分别运行 | **一次运行同时下载 ifs + aifs-single** |
| 运行模式 | 全量日期遍历（一次性） | **每次跑最近5天**（UTC-5 ~ UTC-1） |
| 用途 | 一次性补齐历史 | 日常定时运行，追新数据 |

## 参数

所有路径通过 `dl_utils.py` 基于 `_PROJECT_ROOT` 计算为绝对路径，脚本可在任意目录执行。

```python
SOURCE     = "ecmwf"
MODELS     = ["ifs", "aifs-single"]  # 一次跑完两个模型
TIMES      = [0, 6, 12, 18]
STEPS      = [6, 12, 24, 48, 72]
# SAVE_DIR / LOG_DIR 在 dl_utils.py 中定义为绝对路径:
#   _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#   SAVE_DIR = os.path.join(_PROJECT_ROOT, "data", "raw")
#   LOG_DIR  = os.path.join(_PROJECT_ROOT, "log")
SINGLE_PARAMS = ["2t", "msl", "tp", "ssrd"]
LEVEL_PARAMS  = ["q", "u", "v", "t"]
LEVELS        = [1000, 925, 850, 700, 500, 300, 250, 200, 50]
```

## 文件结构

同 dl_2025.py: `data/raw/{year}/{model}/{step}/{date}_{model}_t{time}_step{step}.grib2`

## 核心流程

```
1. 生成本次日期列表 days = [UTC-5, UTC-4, UTC-3, UTC-2, UTC-1]
2. 遍历 model → date → time → step (2模型 × 20文件/天 = 40文件/天):
   a. 检查 target 是否存在 → 跳过
   b. 分别下载 single + levels → 临时文件
   c. 二进制合并 → target
   d. eccodes 校验 (40条消息)
   e. 写入日志 log/{YYYYMM}/{date}_download.log
   f. 异常自动重试3次，间隔10s
```

## 运行时机

- 每日定时运行（如 cron）即可覆盖最近5天
- ecmwf 源仅保留~4天数据，需在此窗口内下载
- 首次运行时如果日期已过期，ecmwf源会返回404，自动跳过

## 校验日志

同 dl_2025.py，日志格式一致，方便统一查看：

```
[OK] 20260501_t00_step6.grib2: 40 msgs, 24.9 MB, 12s
[SKIP] 20260501_t00_step12.grib2
[FAIL] 20260501_t06_step24.grib2: 404 Not Found
```

## 命令行

```bash
python scripts/dl_2026.py
```
一键下载 ifs + aifs-single 两个模型。

## 测试计划

1. 跑一次，确认两个模型数据都正常下载
2. 检查日志和文件结构
3. 再跑一次确认 skip 逻辑正常

## 实测结果 (2026-05-04)

- 首次运行: 115/120 文件成功, 2.9 GB (3天有效 + 5文件AIFS t00过期)
- AIFS 5.1 t00 过期后用 `dl_miss.py` 从 azure 补全
- 404 跳过修复: 不重试直接标记 [EXPIRED]

## 配套工具

- `dl_miss.py`: azure 源补缺口，扫描缺失文件并下载
  ```bash
  python scripts/dl_miss.py 2026-05-01 2026-05-01
  ```

## 总数据量

每次运行: 2模型 × 5天 × 4时次 × 5步 = 200 文件 × ~25MB ≈ 5 GB

每日增量: 2模型 × 1天 × 20文件 × 25MB ≈ 1 GB/day
