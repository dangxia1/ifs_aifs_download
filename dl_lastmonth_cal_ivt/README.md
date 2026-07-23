# 上月数据下载 + IVT 计算

> 每月初运行一次，从 Azure 下载上个月全部 IFS + AIFS 的 3161 关键时次数据，逐个文件计算 1000-300 hPa 垂直积分水汽通量 (IVT)。跳过已存在文件，支持断点续传。

---

## 一、下载逻辑

### 1. 确定目标月份

自动取上个月的 YYYYMM（例如 7 月运行 → 下载 6 月数据 `202606`）。也支持手动指定：

```bash
python dl_lastmonth.py             # 自动: 上个月
python dl_lastmonth.py 202605      # 手动: 指定月份
```

### 2. 遍历下载

对每个 **模型 × 日期 × 起报时次 × step**，执行：

```
① 检查 NC 文件是否已存在 → 跳过 (断点续传)
② 下载 grib2 → 校验 → 保存到 step{N}/ 目录
③ 计算 IVT → 保存 _ivt.nc 到同目录
④ 继续下一个文件
```

- **数据源**：Azure（ECMWF 历史归档，长期保存）
- **起报时次**：全部 4 个（00z / 06z / 12z / 18z）
- **步长**：IFS `[0,3,6,24,72]`，AIFS `[0,6,24,72]`
- **策略**：跳过已存在 → 下载失败跳过 → IVT 失败跳过，单个文件失败不中断整体

### 3. IVT 计算

同 `dl_realtime`，梯形法则垂直积分 1000-300 hPa，公式详见 [dl_realtime/README.md](../dl_realtime/README.md)。

---

## 二、文件结构

```
dl_lastmonth_cal_ivt/
├── config.yaml                      # 配置文件
├── utils.py                         # 共享模块
├── dl_lastmonth.py                  # 主脚本入口
├── compute_ivt.py                   # IVT 计算模块
├── requirements.txt                 # Python 依赖
├── log/                             # 日志目录
│
└── (数据输出在 save_dir 指定路径)
    /shared_data/zongshen/ec_monthly_ivt/{YYYYMM}/
    ├── ifs/
    │   ├── step0/
    │   │   ├── {date}_ifs_t{time}_step0.grib2
    │   │   └── {date}_ifs_t{time}_step0_ivt.nc
    │   ├── step3/
    │   ├── step6/
    │   ├── step24/
    │   └── step72/
    └── aifs/
        ├── step0/
        ├── step6/
        ├── step24/
        └── step72/
```

### 文件命名

```
{起报日期}_{模型}_t{起报时次}_step{预报步长}.grib2
{起报日期}_{模型}_t{起报时次}_step{预报步长}_ivt.nc
```

### GRIB2 与 NetCDF 内容

| 文件 | 内容 |
|------|------|
| `.grib2` | 37 条 message：`tp`(地面) + `q/u/v/t` × 9层 |
| `_ivt.nc` | 3 个变量：`IVT`、`IVT_u`、`IVT_v`，单位 kg/(m·s) |

### 预计数据量

| 项目 | 数量 | 单文件 | 合计 |
|------|------|--------|------|
| IFS grib | 5步 × 4时次 × 30天 | ~24MB | ~14.4GB |
| AIFS grib | 4步 × 4时次 × 30天 | ~21MB | ~10.1GB |
| IFS ivt nc | 同上 | ~25MB | ~15.0GB |
| AIFS ivt nc | 同上 | ~25MB | ~12.0GB |
| **每月总计** | **1080 文件** | | **~51.5GB** |

---

## 三、运行与调度

### 手动运行

```bash
conda activate ifs_aifs
cd /home/zongshen/ifs_aifs_download/dl_lastmonth_cal_ivt
python dl_lastmonth.py              # 自动处理上月
python dl_lastmonth.py 202606       # 指定月份
```

### 定时调度（每月 2 号 12:00 CST = 04:00 UTC）

每月首日凌晨数据可能未就绪，2 号中午给 Azure 约 40 小时缓冲。

```bash
crontab -e
```

```
0 12 2 * * . ~/miniforge3/etc/profile.d/conda.sh && conda activate ifs_aifs && cd /home/zongshen/ifs_aifs_download/dl_lastmonth_cal_ivt && python dl_lastmonth.py >> log/cron.log 2>&1
```

| crontab 字段 | 含义 |
|-------------|------|
| `0` | 分钟 = 整点 |
| `12` | 小时 = 中午 (CST) |
| `2` | 日 = 每月 2 号 |
| `* *` | 每月 + 每周都匹配 |

### 断点续传

每个文件处理前先检查 `_ivt.nc` 是否存在，存在则跳过。中断后直接重跑即可接上。

---

## 四、配置说明

```yaml
# 关键时次
steps:
  ifs: [0, 3, 6, 24, 72]
  aifs-single: [0, 6, 24, 72]

# 模型 → 输出目录名
models:
  ifs: ifs
  aifs-single: aifs

# 数据源
source: "azure"       # 历史数据从 Azure
times: [0, 6, 12, 18] # 全部 4 个起报时次

# 气象要素
single_params: ["tp"]
level_params: ["q", "u", "v", "t"]
levels: [1000, 925, 850, 700, 500, 300, 250, 200, 50]

# 输出
save_dir: "/shared_data/zongshen/ec_monthly_ivt"
```

---

## 五、依赖

```
ecmwf-opendata>=0.3.29,<0.4
pyyaml>=6
xarray
netcdf4
# eccodes 由 conda-forge 安装
```

详见 [requirements.txt](requirements.txt)。
