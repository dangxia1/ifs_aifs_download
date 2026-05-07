# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此仓库中工作时提供指引。

## 指南

/docs下是项目知识库，工作前按需查阅：

- 官方API文档: [docs/ecmwf-opendata.md](docs/ecmwf-opendata.md)
- 数据源选择与GRIB校验: [docs/数据源、校验和下载.md](docs/数据源、校验和下载.md)
- dl_2025.py实现计划: [docs/plan_dl_2025.md](docs/plan_dl_2025.md)
- dl_2026.py实现计划: [docs/plan_dl_2026.md](docs/plan_dl_2026.md)
- Git使用指南: [docs/git指南.md](docs/git指南.md)
- pytest测试思路: [docs/pytest自动化测试思路.md](docs/pytest自动化测试思路.md)
- Cron定时运行: [docs/cron.md](docs/cron.md)

规则：
- /docs下有文件更新时将索引加入本指南
- 更新CLAUDE.md时同步更新README.md
- 遇到不确定的事查阅官方文档并询问用户
- 每次更新项目时阅读整个目录
  - 检查并删去项目不需要的文件
  - 检查已有文件的冗余部分并删除
  - 更新完成后git跟进一下

## 项目概述与需求

- 下载 ECMWF IFS / AIFS 气象预报数据
  - 2025-05-01至2025-08-31的数据(历史数据)
    - 使用脚本dl_2025.py进行下载 (azure源, 一键ifs+aifs)
  - 2026-05-01至2026-08-31的数据(现在和未来数据)
    - 使用脚本dl_2026.py每日运行, 一键下载ifs+aifs最近5天
    - ecmwf源仅保留~4天数据, 过期文件用dl_miss.py从azure补
    - 若数据存在则跳过, 404自动跳过不重试, 下载后自动校验
    - 空间估算: 全年约123GB, 300GB硬盘足够


### 参数需求

- 通用配置：IFS / AIFS 共用
steps: [6, 12, 24, 48, 72]
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

### 待办

- [x] 数据源测试 (ecmwf/azure/aws/google)
- [x] 单层变量下载测试
- [x] 气压层变量下载测试
- [x] 合并下载方案验证
- [x] 跨源一致性验证 (ecmwf == azure)
- [x] GRIB校验方案确定
- [x] AIFS下载测试 (tcw/tcwv已移除, 单层统一为4参数)
- [x] 编写 dl_2025.py（历史数据 2025-05-01 ~ 2025-08-31, azure源, 一键ifs+aifs）
- [x] 编写 dl_2026.py（ecmwf源, 一键ifs+aifs, 每次最近5天）
- [ ] 项目审查修复 (2026-05-06)
  - [x] git init 初始化仓库
  - [x] requirements.txt 版本锁定
  - [x] .gitignore 补充 Python 通用条目
  - [x] dl_miss.py 改用 argparse（与 setup.py 风格统一）
  - [x] README.md 补充入门指引（首次使用顺序）
  - [x] dl_2025.py 编写
  - [x] test/ 改为自动化测试（pytest）
  - [x] print() 改为 logging 模块
  - [x] 配置从硬编码改为配置文件
  - [x] 添加 cron 定时运行指南
  - [x] 添加数据清理机制（清理过期文件）—— 不需要
  - [x] 添加 --dry-run 干跑模式 —— 不需要

### 项目结构

```
scripts/
└── config.yaml            # 配置文件（参数/重试/路径）
└── dl_utils.py           # 共享模块（加载config/日志/下载/重试/校验）
└── dl_2026.py            # 日常下载（ecmwf源, ifs+aifs, 最近5天）
└── dl_2025.py            # 历史下载（azure源, ifs+aifs, 2025-05~08）
└── dl_miss.py            # 补缺口（azure源, 扫描缺失并下载）
└── setup.py              # 预建目录结构（可选）
docs/
└── ecmwf-opendata.md      # 官方文档参考
└── 数据源、校验和下载.md          # 数据源选择与GRIB校验
└── plan_dl_2025.md        # dl_2025.py实现计划
└── plan_dl_2026.md        # dl_2026.py实现计划
└── git指南.md              # Git 初始化与使用指南
test/
└── conftest.py             # shared fixtures (recent_date, verify_grib, etc.)
├── test_ecmwf.py           # ecmwf源 tests (single, pressure, combined)
├── test_aifs.py            # AIFS model test (combined)
└── test_azure.py           # Azure源 + 跨源对比 tests
```
