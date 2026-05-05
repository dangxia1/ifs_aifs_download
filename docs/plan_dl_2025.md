# dl_2025.py 实现计划

- 一键下载 ifs + aifs-single，无需参数。
- 用法: `python scripts/dl_2025.py`

## 参数

所有路径通过 `dl_utils.py` 基于 `_PROJECT_ROOT` 计算为绝对路径。

```python
DATE_START = "2025-05-01"
DATE_END   = "2025-08-31"
SOURCE     = "azure"           # 历史数据，ecmwf源不可用
MODELS     = ["ifs", "aifs-single"]  # 一次跑完两个模型
TIMES      = [0, 6, 12, 18]
STEPS      = [6, 12, 24, 48, 72]
# SAVE_DIR / LOG_DIR 在 dl_utils.py 中定义为绝对路径

SINGLE_PARAMS = ["2t", "msl", "tp", "ssrd"]
LEVEL_PARAMS  = ["q", "u", "v", "t"]
LEVELS        = [1000, 925, 850, 700, 500, 300, 250, 200, 50]
```

## 文件结构

data/raw/
├── 2025/
│   ├── ifs/
│   │   ├── 6/
│   │   ├── 12/
│   │   ├── 24/
│   │   ├── 48/
│   │   └── 72/
│   └── aifs-single/
│       ├── 6/
│       ├── 12/
│       ├── 24/
│       ├── 48/
│       └── 72/
log/
├── 202505/
│   ├── 20250501_download.log    # 每天4时次×5步 = 20条记录
│   ├── 20250502_download.log
│   └── ...
└── 202508/
    └── ...

每个step目录下：{date}_{model}_t{time}_step{step}.grib2  (单层+气压层合并, 40条消息)

## 单文件内容

每个 .grib2 = 4条单层 + 36条气压层 = 40条GRIB消息，约24~25MB（IFS 24.9MB, AIFS 24.4MB）。

## 核心流程

1. 遍历 model (ifs, aifs-single)
2. Client(source="azure", model=model)
3. 遍历 date → time → step:
   a. target = SAVE_DIR + "/{year}/{model}/{step}/{date}_{model}_t{time}_step{step}.grib2"  (绝对路径)
   b. os.path.exists(target) → 跳过
   c. 分别下载 single 和 levels → 临时文件
   d. 二进制合并 → target
   e. eccodes 校验 → 写入日志
   f. 异常时自动重试最多3次，间隔10s

## 校验日志

log/{YYYYMM}/{date}_download.log，每天一个，20条记录：

  [OK] 20250501_t00_step6.grib2: 40 msgs, 24.9 MB, 45s
  [OK] 20250501_t00_step12.grib2: 40 msgs, 25.1 MB, 52s
  ...
  [SKIP] 20250501_t06_step6.grib2
  [FAIL] 20250501_t12_step24.grib2: missing ['t']

## 总数据量估算

123天 × 4时次 × 5步 = 2,460 文件 × ~25MB ≈ 62 GB (per model)
两模型合计 ≈ 124 GB