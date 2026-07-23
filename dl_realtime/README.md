# 实时预报数据下载

> 基于 ECMWF Open Data，每小时自动下载 IFS + AIFS 最新预报的 3161 关键时次数据，覆盖旧文件，永远只保留最新一套。

---

## 一、下载逻辑

整个脚本一次运行经历 **5 个阶段**：

### 1. 加载配置

读取 `config_realtime.yaml`，合并默认值（定义在 `utils.py` 的 `_DEFAULTS` 字典中）。若配置文件不存在则使用默认值。

涉及的关键配置项：

| 配置项 | 含义 | 当前值 |
|--------|------|--------|
| `steps` | 每个模型的预报步长 | IFS: `[0,3,6,24,72]`, AIFS: `[0,6,24,72]` |
| `single_params` | 地面单层要素 | `["tp"]` (总降水) |
| `level_params` | 气压层要素 | `["q","u","v","t"]` (比湿/风/温度) |
| `levels` | 气压层级 (hPa) | 1000/925/850/700/500/300/250/200/50 |
| `retry_max` | 下载失败重试次数 | 3 |

### 2. 获取最新可用起报时次 (`find_latest_run`)

调用 ECMWF Open Data API 的 **`Client.latest()`** 方法，直接返回服务端最新可用的预报时次（datetime 对象），无需手动探测或计算延迟时间。

ECMWF 每天运行 4 个时次：**00z / 06z / 12z / 18z**。每个模型独立调用 `latest()`，因为 **IFS 和 AIFS 发布时间可能不同步**（IFS 先完成，AIFS 晚几十分钟）。

### 3. 下载数据 (`download_with_retry`)

对每个模型 × 每个 step，执行以下流程：

```
① download_one()
   ├── 请求1: client.retrieve(single_params) → 地面场 GRIB2 → 临时文件 tmp1
   ├── 请求2: client.retrieve(level_params, levelist) → 高空场 GRIB2 → 临时文件 tmp2
   └── 合并: tmp1 + tmp2 二进制拼接 → target.tmp

② verify_grib()
   └── 用 eccodes 逐条读取 GRIB message，检查 single_params 是否齐全

③ 校验通过 → os.replace(target.tmp → target)
   校验失败 → 删除临时文件，重试 (最多 retry_max 次)
```

> **为什么分两次请求？** ECMWF Open Data 的 surface 参数和 pressure-level 参数属于不同的 GRIB 文件分片。分开请求后本地合并，避免下载整个 GRIB 文件再裁剪。

### 4. 覆盖旧数据 (`clear_model_dir`)

每个模型开始下载前，**先清空对应输出目录**（`shutil.rmtree` + `mkdir`），确保目录中只有最新一次运行的文件。

### 5. 输出结果

文件直接落在模型目录下，下载完成后自动计算 IVT：

```
/shared_data/zongshen/ec_realtime/
├── ifs/        ← 5 个 .grib2 文件
├── aifs/       ← 4 个 .grib2 文件
├── ivt/
│   ├── ifs/    ← 5 个 .nc 文件 (IVT)
│   └── aifs/   ← 4 个 .nc 文件 (IVT)
└── log/
```

### 6. 计算 IVT (`compute_ivt`)

下载完成后自动调用，对每个 grib2 文件计算 1000-300 hPa 垂直积分水汽通量。

**公式**：

$$IVT = \frac{1}{g} \int_{300}^{1000} q \cdot \mathbf{V} \, dp$$

其中 $g = 9.80665\,\text{m/s}^2$，$q$ 为比湿，$\mathbf{V} = (u,v)$ 为水平风矢量，$p$ 为气压。

**数值积分**（梯形法则）：

气压层从低到高：1000 → 925 → 850 → 700 → 500 → 300 hPa。相邻层间取 $q \cdot \mathbf{V}$ 的平均值 × 层厚，累加后除以 $g$。

$$IVT_u = \frac{1}{g} \sum_{k=1}^{N-1} \frac{q_k u_k + q_{k+1} u_{k+1}}{2} \cdot |p_{k+1} - p_k|$$

**输出**：每个 grib2 对应一个 NetCDF（`_ivt.nc`），包含 `IVT`、`IVT_u`、`IVT_v`，单位 kg/(m·s)。

---

## 二、文件结构

```
dl_realtime/                         # 项目根目录
├── config_realtime.yaml             # 配置文件
├── utils.py                         # 共享模块 (配置加载/探测/下载/校验/重试/路径)
├── dl_realtime.py                   # 主脚本入口
├── compute_ivt.py                   # IVT 计算模块 (下载后自动调用)
├── requirements.txt                 # Python 依赖
│
└── (数据输出在 save_dir 指定路径)
    /shared_data/zongshen/ec_realtime/
    ├── ifs/
    │   ├── {date}_ifs_t{time}_step0.grib2
    │   ├── {date}_ifs_t{time}_step3.grib2
    │   ├── {date}_ifs_t{time}_step6.grib2
    │   ├── {date}_ifs_t{time}_step24.grib2
    │   └── {date}_ifs_t{time}_step72.grib2
    ├── aifs/
    │   ├── {date}_aifs-single_t{time}_step0.grib2
    │   ├── {date}_aifs-single_t{time}_step6.grib2
    │   ├── {date}_aifs-single_t{time}_step24.grib2
    │   └── {date}_aifs-single_t{time}_step72.grib2
    └── log/                             # 日志目录 (自动创建)
        └── 20260722_142625.log          # 每次运行一个日志文件
```

### 文件命名规则

```
{起报日期}_{模型}_t{起报时次}_step{预报步长}.grib2

示例: 2026-07-21_ifs_t18_step6.grib2
      ↑          ↑   ↑  ↑
      7月21日    IFS 18z 6小时预报
```

### GRIB2 文件内容

每个 `.grib2` 文件包含 **37 条 GRIB message**：

| 类型 | 条数 | 内容 |
|------|------|------|
| 地面场 | 1 | `tp` (总降水) |
| 高空场 | 36 | `q/u/v/t` × 9层 (1000~50hPa) |

---

## 三、日志系统

### 日志文件

每次运行在 `log/` 目录下生成一个独立的日志文件，文件名格式：

```
log/YYYYMMDD_HHMMSS.log

示例: log/20260722_142625.log
      → 2026年7月22日 14:26:25 开始运行
```

### 日志格式

```
HH:MM:SS LEVEL     MESSAGE

示例:
14:26:25 INFO      === 3161 realtime download ===
14:26:27 INFO      Latest run: 2026-07-21 18z [OK]
14:26:28 INFO      --- ifs (steps: [0, 3, 6, 24, 72]) ---
14:26:40 INFO        OK 2026-07-21_ifs_t18_step0.grib2  (37 msgs, 23.3MB)
14:28:52 INFO      === Done: 9 files ===
```

### 日志级别

| 级别 | 触发条件 | 示例 |
|------|----------|------|
| `INFO` | 正常运行信息 | 开始/结束、文件下载成功、起报时次确认 |
| `WARNING` | 可恢复错误 | 下载失败进入重试（`Retry 1/3 ...`） |
| `ERROR` | 致命错误 | 无可用时次、重试耗尽、文件校验失败 |

### 双输出

```python
handlers=[
    FileHandler(log/xxx.log)   → 写入文件 (UTF-8)
    StreamHandler(sys.stdout)  → 打印到终端 (用于 cron 邮件/重定向)
]
```

两者同步输出相同内容，cron 调度时可通过 `>> /var/log/dl_realtime.log 2>&1` 捕获终端输出。

---

## 四、3161 关键时次

| 编号 | 预报提前量 | IFS step | AIFS step | 用途 |
|------|-----------|----------|-----------|------|
| 3 | 提前3天 | 72h | 72h | 早期预警 |
| 1 | 提前1天 | 24h | 24h | 临近预警 |
| 6 | 提前6小时 | 6h | 6h | 短临预警 |
| 1 | 提前3小时 | 3h | — | 紧急预警（AIFS无此步长） |
| 0 | 0小时 | 0h | 0h | 实况分析（analysis） |

> **为何 AIFS 缺少 step=3？** AIFS 在 ECMWF Open Data 中的时间分辨率为 **6 小时间隔**（0→6→12→24→48→72…），不提供 3 小时步长的数据。IFS 则为 3 小时间隔（0→3→6→9→…）。

---

## 五、配置说明 (`config_realtime.yaml`)

```yaml
# 预报步长 (按模型区分)
steps:
  ifs: [0, 3, 6, 24, 72]
  aifs-single: [0, 6, 24, 72]

# 模型 → 输出目录名
models:
  ifs: ifs
  aifs-single: aifs

# 气象要素
single_params: ["tp"]                # 地面层: 总降水
level_params: ["q", "u", "v", "t"]   # 气压层: 比湿/U风/V风/温度
levels: [1000, 925, 850, 700, 500, 300, 250, 200, 50]  # 9层

# 下载行为
source: "ecmwf"                      # 数据源 (实时)
retry_max: 3                         # 重试次数
retry_interval: 10                   # 重试间隔 (秒)

# 输出
save_dir: "/shared_data/zongshen/ec_realtime"
```

---

## 六、环境部署

### 首次部署

```bash
# 0. 安装 miniforge (社区版 conda，无 Anaconda TOS，安装在家目录无需 root)
wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
bash Miniforge3-Linux-x86_64.sh -b -p /shared_data/zongshen/miniforge3
/shared_data/zongshen/miniforge3/bin/conda init
# 重新登录让 conda 生效，或 source ~/.bashrc

# 1. 拉取代码
cd /home/zongshen
git clone git@github.com:dangxia1/ifs_aifs_download.git
# dl_realtime/ 在 ifs_aifs_download/dl_realtime/

# 2. 创建 conda 环境
conda create -n ifs_aifs python=3.10 -y
conda activate ifs_aifs

# 3. 安装 C 库依赖 (eccodes + netcdf4, 由 conda-forge 提供 C 库)
conda install eccodes netcdf4 hdf5 -y

# 4. 安装 Python 依赖
cd /home/zongshen/ifs_aifs_download/dl_realtime
pip install -r requirements.txt

# 5. 测试运行
python dl_realtime.py
```

> **为什么用 miniforge？** 1) `eccodes` 依赖 C 库，conda 自带，无需 `sudo`；2) miniforge 是 conda-forge 社区维护的开源 fork，无 Anaconda 公司 TOS 限制，学术界广泛使用。

### eccodes 的作用

`eccodes` 是 ECMWF 官方的 GRIB 文件处理库，在项目中用于 **数据完整性校验**：

```python
# verify_grib() 做的事:
1. 逐条读取下载完成的 GRIB2 文件的 message
2. 提取每条 message 的 shortName (参数名，如 "tp")
3. 与 single_params 对比，检查要素是否齐全
4. 若要素缺失 → 文件损坏/下载不完整 → 触发重试
```

### 依赖列表

```
ecmwf-opendata>=0.3.29,<0.4   # ECMWF Open Data API 客户端
eccodes>=2.47.0,<2.48          # GRIB2 解码 / 数据完整性校验
pyyaml>=6                      # YAML 配置文件解析
```

详见 [requirements.txt](requirements.txt)。

---

## 七、运行与调度

### 手动运行

```bash
conda activate ifs_aifs
cd /home/zongshen/ifs_aifs_download/dl_realtime
python dl_realtime.py
```

### 定时调度：Crontab（每小时）

```bash
# 编辑
crontab -e

# 每小时整点运行 (. conda.sh 使 cron 能加载 conda 环境)
0 * * * * . /shared_data/zongshen/miniforge3/etc/profile.d/conda.sh && conda activate ifs_aifs && cd /home/zongshen/ifs_aifs_download/dl_realtime && TQDM_DISABLE=1 python dl_realtime.py >> /shared_data/zongshen/ec_realtime/log/cron.log 2>&1
```

| crontab 字段 | 含义 |
|-------------|------|
| `0` | 分钟 = 整点 |
| `*` | 每小时 |
| `*` | 每天 |
| `*` | 每月 |
| `*` | 每周 |

验证：`crontab -l`

### 定时调度：Windows 任务计划程序

```powershell
schtasks /create /tn "3161_download" /tr "C:\Users\dangx\.conda\envs\ifs_aifs\python.exe D:\Projects\CV\ifs-aifs-ai\dl_realtime\dl_realtime.py" /sc HOURLY
```

---

### 数据过期说明

- ECMWF `source=ecmwf` 仅保留 **~4 天** 的实时数据
- 若脚本因故障超过 4 天未运行，旧时次数据将 404
- 脚本通过 `Client.latest()` 自动获取最新可用时次

---

## 八、数据源说明

| 项目 | 说明 |
|------|------|
| 数据门户 | [ECMWF Open Data](https://www.ecmwf.int/en/forecasts/datasets/open-data) |
| 许可证 | CC BY 4.0（使用时需注明 ECMWF） |
| IFS 模型 | 物理驱动的确定性全球预报 (HRES)，~9km |
| AIFS 模型 | 数据驱动的确定性全球预报 (AIFS-Single)，~28km |
| 分辨率 | 0.25° (HRES) |
| IFS 步长间隔 | 00z/12z: 0-144h 每3h, 144-240h 每6h; 06z/18z: 0-90h 每3h |
| AIFS 步长间隔 | 所有时次 6h 间隔 |