# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此仓库中工作时提供指引。

## 指南

/docs下是项目知识库，工作前按需查阅：

- 官方API文档: [docs/ecmwf-opendata.md](docs/ecmwf-opendata.md)
- 数据源选择与GRIB校验: [docs/数据源、校验和下载.md](docs/数据源、校验和下载.md)
- 项目进展和 /scripts 脚本介绍与指南: [docs/项目进展.md](docs/项目进展.md)
- Git使用指南: [docs/git指南.md](docs/git指南.md)
- pytest测试思路: [docs/pytest自动化测试思路.md](docs/pytest自动化测试思路.md)
- Cron定时运行: [docs/cron.md](docs/cron.md)

规则：
- 新增或修改 /docs 下的文件后，将链接加入本指南的索引
- 修改 CLAUDE.md 时同步检查 README.md 是否需要更新
- 遇到不明确的问题，先查阅 /docs 下的官方文档，仍不确定则询问用户
- 开始改动代码前，快速浏览项目根目录和待修改目录的文件列表，发现无用文件及时清理
- 每完成一轮改动后，git add 相关文件并提交（commit message 用中文）

## 项目概述与需求

- 下载 ECMWF IFS / AIFS 气象预报数据
  - 2025-05-01至2025-08-31的数据(历史数据): dl_anytime.py (azure源)
  - 2026-05-01至2026-08-31的数据(现在和未来数据)
    - 使用脚本dl_2026.py每日运行, 一键下载ifs+aifs最近5天
    - ecmwf源仅保留~4天数据, 过期文件用dl_anytime.py从azure补
    - 若数据存在则跳过, 404自动跳过不重试, 下载后自动校验
    - 空间估算: 全年约123GB, 300GB硬盘足够


### 参数需求

- 通用配置：IFS / AIFS 共用
steps: [0, 6, 12, 24, 48, 72]
save_dir: "data/raw/"  (dl_utils.py 中基于 _PROJECT_ROOT 计算为绝对路径)

d- 单层变量 (surface)  
  - params: ["2t", "msl", "tp", "ssrd"]

- 气压层变量 (pressure levels)  
  - params: ["q", "u", "v", "t"]
  - levelist: [1000, 925, 850, 700, 500, 300, 250, 200, 50]


### 环境配置

```bash
conda create -n ifs_aifs python=3.10
conda activate ifs_aifs
pip install -r requirements.txt
```

### 项目结构

```
scripts/
└── config.yaml            # 配置文件（参数/重试/路径）
└── dl_utils.py           # 共享模块（加载config/日志/下载/重试/校验）
└── dl_2026.py            # 日常下载（ecmwf源, ifs+aifs, 最近5天）
└── dl_anytime.py          # 任意日期下载（azure源, 跳过已存在）
└── check_miss.py          # 检查缺失文件（扫描data/raw/找缺口）
└── setup.py              # 预建目录结构（可选）
docs/
└── ecmwf-opendata.md      # 官方文档参考
└── 数据源、校验和下载.md          # 数据源选择与GRIB校验
└── 项目进展.md             # 项目进展与 /scripts 脚本介绍与指南
└── git指南.md              # Git 初始化与使用指南
test/
└── conftest.py             # shared fixtures (recent_date, verify_grib, etc.)
├── test_ecmwf.py           # ecmwf源 tests (single, pressure, combined)
├── test_aifs.py            # AIFS model test (combined)
└── test_azure.py           # Azure源 + 跨源对比 tests
```
