# 实时预报数据下载

> 基于 ECMWF Open Data，每小时自动下载 IFS + AIFS 最新预报数据（step 0-144h / 6h 间隔，25 个时次），计算 IVT + 识别大气河，输出双模型对比图，Streamlit 展示。

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

文件直接落在模型目录下，下载完成后自动计算 IVT → AR → 可视化：

```
/shared_data/zongshen/ec_realtime/
├── ifs/        ← 5 个 .grib2
├── aifs/       ← 4 个 .grib2
├── ivt/{ifs,aifs}/   ← 9 个 _ivt.nc
├── ar/{ifs,aifs}/    ← 9 个 _ar.nc
├── figures/{global,east_asia,north_china}/{ifs,aifs}/
│                     ← 27 个 .pdf
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

### 7. AR 大气河检测 (`detect_ar`)

IVT 计算完成后自动调用，对每文件执行 AR 识别：

- 加载 85% 分位气候态阈值（ERA5 1981-2023，老师提供）
- 骨架化 → FilFinder2D 精炼 → 几何过滤
- 输出 `_ar.nc`：`AR_plume`（羽流）、`AR_axis`（河轴）、`AR_center`（质心）、`AR_IVT`（羽流内 IVT）

### 8. 可视化 (`visualize_ivt`)

AR 检测完成后自动调用，生成 **3 区域 × 每文件** PDF：

| 图层 | 数据 | 样式 |
|------|------|------|
| 底图 | Basemap bluemarble | 卫星地球影像 |
| IVT 填色（非 AR） | `_ivt.nc` `IVT` | contourf, alpha=0.2 |
| IVT 填色（AR 内） | `_ar.nc` 掩膜后 | contourf, alpha=1 |
| AR 河轴 | `_ar.nc` `AR_axis` | **纯红散点**（老师要求 2026-08-06，去白描边；华北更大；全球/东亚 8pt）。平滑/恢复改过 plume 时重算轴：骨架→偏移到 IVT 极大值→**膨胀3次+填洞+再骨架化重连**（老师 First_new.py 原版流程，2026-08-06 补回）→**距离过滤**（轴点离 plume 边界 >5°/res+1 格剔除，老师 First_new.py:134，2026-08-06 补）；plume 未变时保留 detect_ar 原轴 |
| AR 质心 | `_ar.nc` `AR_center` | 纯白加号（2026-08-06 改：原黑边十字 → 白 `+`，全球 s=60 / 东亚·华北 s=120） |
| 降水标注 | grib2 `tp` 差分 | 4 级绿色圆点，圆点尺寸按区域缩放：全球 ×1 / 东亚 ×2 / 华北 ×3（2026-08-06，老同志看得见） |
| 边界叠加 | shapefile | **中国立场边界**（老师提供 2026-08-06）：`Continent.shp` 全球海岸线（所有区域）+ `China_provinces.shp` 中国省级边界含南海诸岛（东亚/华北）。只有 `.shp` 本体 → 纯 `struct` 解析画线（不依赖 pyshp/ogr），窗口相交裁剪 + 抽稀 + 进程内缓存；文件缺失静默跳过 |
| 华北区域 | 硬编码 | 北京红星 `(116.4°E, 39.9°N)` |

**双面板**：左 IFS 右 AIFS 并排对比，每 step 一张 PNG。

输出至 `ec_realtime/figures/{global,east_asia,north_china}/step{N}.png`（每区域 25 张，共 75 张）。

### Streamlit 展示 (`app.py`)

```bash
streamlit run app.py --server.port 8501
```

功能：选区域（点击切换）、选时次（右侧滚动面板，显示有效时间）、播放动画+进度条、查看原图、北京地区时序图 tab（2026-08-06 由华北缩小，北京 116.4°E/39.9°N 中心 ±1.5°，柱高 = AR 区域 IVT 积分/面积，柱色等级按该平均值定）。数据目录自动解析：环境变量 > config_realtime.yaml > 包内 `data/`（绿色包）。

**按键机制**（2026-08-06）：Tab/区域/时次按键全部是内联样式的 HTML 链接（`font-size:19px`），由 `st.query_params` 驱动，点击 → **整页导航**（当前页刷新加载新内容，URL 同步更新）。不依赖 `<style>` 注入（该环境注入无效）；曾试 `patch_streamlit_css.py` 改 streamlit 包静态文件注入 JS 无刷新切换，但 Streamlit 1.60 前端不响应手动 popstate（URL 变内容不变），方案已废弃、脚本已删除。播放键 ▶ 保留 `st.button`。默认打开第一张图（`steps[0]`）。

验证：页面上起报时间旁有灰色小字 `[UI v3]` = 代码是新版；大标题应为渐变彩色、按键字号 19px。

---

## 二、文件结构

```
dl_realtime/                         # 项目根目录
├── config_realtime.yaml             # 配置文件
├── utils.py                         # 共享模块 (配置加载/探测/下载/校验/重试/路径)
├── dl_realtime.py                   # 主脚本入口
├── compute_ivt.py                   # IVT 计算模块
├── detect_ar.py                     # AR 大气河识别 (复用 dl_lastmonth_cal_ivt)
├── visualize_ivt.py                 # 可视化模块 (75 张双面板 PNG)
├── north_china_timeseries.py        # 北京地区 AR 强度时序图 (双子图)
├── app.py                           # Streamlit 展示界面 (ARFS)
├── make_green_win.py                # Windows 离线绿包打包 (交叉打包, 详见 打包分发.md)
├── start.bat / start.sh             # 绿色包一键启动
├── docs/                            # 背景图 + 代码逻辑文档
├── China_provinces.shp              # 中国省级边界 (含南海诸岛, 中国立场, 2026-08-06 老师提供)
├── Continent.shp                    # 全球海岸线 (中国立场版图)
├── fonts/                           # 内置中文字体 (Noto CJK, OFL 可分发)
├── requirements.txt                 # Python 依赖
│
└── (数据输出在 save_dir 指定路径)
    /shared_data/zongshen/ec_realtime/
    ├── ifs/          ← 25 个 .grib2 (0-144h 步长6h)
    ├── aifs/         ← 25 个 .grib2
    ├── ivt/{ifs,aifs}/    ← 50 个 _ivt.nc
    ├── ar/{ifs,aifs}/     ← 50 个 _ar.nc
    ├── figures/
    │   ├── {global,east_asia,north_china}/step{N}.png  ← 75 张
    │   └── north_china_timeseries.png                  ← 北京地区时序图
    ├── log/
    └── .last_run        ← 缓存 (对齐时次)
```

### 文件命名规则

```
{起报日期}_{模型}_t{起报时次}_step{预报步长}.grib2

示例: 2026-08-02_ifs_t06_step24.grib2
      ↑          ↑   ↑  ↑
      8月2日    IFS 06z 24小时预报
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

# 3. 安装 C 库依赖 (eccodes + netcdf4 + cartopy, 由 conda-forge 提供 C 库)
conda install eccodes netcdf4 hdf5 cartopy -y

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