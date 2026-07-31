# CLAUDE.md

> 作为Claude Code(简称"CC")控制本项目的工程接口规范。  
> 控制回路: **目标**(需要什么) → **感知**(现状如何) → **决策**(怎么做) → **执行**(动手改) → **反馈**(改对了吗)，五环闭环。

## 一、目标(CC需要将系统推向的目标状态)

### 1.1 核心任务

下载 ECMWF IFS/AIFS 气象预报数据，覆盖两个汛期(基本完成) → 分析IFS/AIFS和ERA5数据的差异，分析两个模型的优劣(暂未开始)

- **2025 汛期**(历史数据): 2025-03-15 ~ 2025-10-31
  - 依据: 
    - [2025水利部汛期开始](http://shzhfy.mwr.gov.cn/ywdt/202503/t20250315_1877355.html)
    - [2025水利部汛期结束](http://www.mwr.gov.cn/xw/sjzs/202511/t20251102_2084627.html)
- **2026 汛期**(当前数据): 2026-04-01 ~ 2026-10-31(预计)
  - 依据: 
    - [水利部 2026 汛期开始](http://shzhfy.mwr.gov.cn/ywdt/202604/t20260401_2106531.html)

### 1.2 下载策略

| 时间段 | 性质 | 脚本 | 数据源 |
|--------|------|------|--------|
| 2025 汛期 | 历史 | `dl_anytime.py` | Azure |
| 2026 汛期 | 当前+未来 | `dl_2026.py`(每日运行，最近 3-4 天) | ECMWF(实时)，Azure(补过期) |

- `dl_2026.py`: 一键下载 IFS + AIFS 最近 3-4 天，已存在则跳过，404 自动跳过不重试，下载后自动校验
- `dl_anytime.py`: 任意日期下载(Azure 源)，跳过已存在文件
- `check_miss.py`: 扫描 `data/raw/` 找出缺失文件
- `dl_realtime/`: 3161 实时预报独立项目，详见 [README](dl_realtime/README.md)
- `dl_lastmonth_cal_ivt/`: 上月数据下载+IVT计算，每月初运行
- ECMWF 源仅保留 ~4 天数据，过期文件用 `dl_anytime.py` 从 Azure 补
- 空间估算: 原始数据 ~520GB（IFS ~26MB/文件 + AIFS ~23MB/文件，实测），建议 1TB 硬盘；若含 ERA5 + 处理中间产物，预留 1.2TB

### 1.3 质量目标

- 代码可工作、可测试、可维护；文档与代码同步；仓库整洁，无临时/废弃文件

---

## 二、系统模型(Agent 对项目的内部表示)

Agent 理解项目构成的蓝图——知道"系统长什么样"才能正确操作它。

### 2.1 项目结构

```
scripts/
├── config.yaml                 # 配置文件(参数/重试/路径)
├── dl_utils.py                 # 共享模块(加载config/日志/下载/重试/校验)
├── dl_2026.py                  # 日常下载(ecmwf源, ifs+aifs, 最近3-4天)
├── dl_anytime.py               # 任意日期下载(azure源, 跳过已存在)
├── check_miss.py               # 检查缺失文件(扫描data/raw/找缺口)
└── setup.py                    # 预建目录结构(可选)
docs/
├── ecmwf-opendata.md           # 官方文档参考
├── 数据源、校验和下载.md         # 数据源选择与GRIB校验
├── ifs-stream-type组合.md       # IFS/AIFS 模型 stream/type 有效组合
├── 项目进展.md                  # 项目进展与脚本指南
├── 研究方向.md                  # 论文研究方向与执行计划
└── git指南.md                  # Git 使用指南
test/
├── test_utils.py               # 共享工具(参数/校验/测速)
├── test_ecmwf.py               # ecmwf源 测速(直接运行: python test/test_ecmwf.py)
├── test_aifs.py                 # AIFS模型 测速
└── test_azure.py                # Azure源 测速 + 跨源对比
data/raw/{year}/{model}/{step}/  # {date}_{model}_t{time}_step{step}.grib2
dl_realtime/                     # [独立项目] 3161实时预报，详见 dl_realtime/README.md
dl_lastmonth_cal_ivt/            # [独立项目] 上月数据+IVT，详见 dl_lastmonth_cal_ivt/
log/{year_month}/                # {date}_download.log
```

### 2.2 运行参数

见[/scripts/config.yaml](/scripts/config.yaml)

### 2.3 环境初始化

```bash
conda create -n ifs_aifs python=3.10
conda activate ifs_aifs
pip install -r requirements.txt
```
- 环境依赖见[/requirements.txt](/requirements.txt)

---

## 三、信息感知与运行规则

Agent 自己跟进并获取项目状态信息的渠道。
- 行动前充分感知，降低决策不确定性。
- 行动时严格遵守规则，规范运行

### 3.1 知识库(/docs)

| 文档 | 用途 |
|------|------|
| [ecmwf-opendata.md](docs/ecmwf-opendata.md) | ecmwf-opendata 官方 API 文档 |
| [ifs-stream-type组合.md](docs/ifs-stream-type组合.md) | IFS/AIFS 模型 stream/type 有效组合 |
| [数据源、校验和下载.md](docs/数据源、校验和下载.md) | 数据源选择、GRIB校验、下载相关信息 |
| [项目进展.md](docs/项目进展.md) | 项目进展与脚本指南 |
| [git指南.md](docs/git指南.md) | Git 使用指南 |
| [研究方向.md](docs/研究方向.md) | 论文研究方向：天气分型 + 分歧归因主干分析 |
| [dl_realtime/README.md](dl_realtime/README.md) | 3161 实时预报下载 |
| [dl_lastmonth_cal_ivt/](dl_lastmonth_cal_ivt/) | 上月数据下载+IVT计算 |


### 3.2 运行规则

- 开始执行任务时，阅读本次项目相关的知识库文档，若仍有不明确问题，不断追问用户确定细节
- 任务完成后，阅读与本次任务相关的目录和文件，按项目实际状况更新文档内容(包括文档命名)，发现无用文件及时清理
- 每次修改 `dl_realtime/` 或 `dl_lastmonth_cal_ivt/` 下的代码，**同步检查对应的 README.md**（如新增模块需更新文件结构树、参数表、输出结构、依赖列表等）

**每次 `git commit` 前，逐条过以下检查清单（必须全部通过才可提交）：**

1. /docs 目录有新增/修改/删除 → CLAUDE.md 3.1 知识库索引已同步
2. /docs 或项目结构有变化 → CLAUDE.md 2.1 项目结构已同步
3. CLAUDE.md 有修改 → README.md 已同步检查
4. 无临时文件、废弃文件残留
5. commit message 用简洁中文

### 3.3 反馈规则

- 先输出项目最新的预期变化(如新代码会有怎样的输出结果，新的文档文件的内容简洁)，同时以与实际运行时相似的手段检验本次任务成果
- git commit 时不输出 Co-Authored-By 等相关字样
- 涉及 git commit/push 时，给出示例命令让用户自己执行，不主动代为提交
- 修改代码前必须先用文字回应，说明方案(如整体逻辑 + 改变的逻辑)后再动手，不要只思考不动笔