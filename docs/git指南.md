# Git 使用指南

## 初始化

```bash
cd D:\Projects\ifs-aifs-ai
git init
```

## .gitignore

```gitignore
# Data and log directories (created by setup.py)
/data/
/log/

# Python
__pycache__/
*.pyc
*.pyo
*.egg-info/
dist/
build/

# Conda / venv
.conda/
venv/
.env

# IDE
.vscode/
.idea/

# OS
Thumbs.db
.DS_Store
```

## 初始提交

```bash
git add . # 暂存所有源文件
git commit -m "Initial commit: IFS/AIFS download project" # 提交
```

## 日常提交

```bash
# 查看状态
git status

# 暂存修改
git add scripts/dl_2026.py    # 具体文件
git add -A                     # 所有文件（谨慎）

# 提交
git commit -m "描述做了什么"

# 查看历史
git log --oneline -10
```

## .gitignore 说明

| 条目 | 原因 |
|---|---|
| `/data/`, `/log/` | 运行时生成，单文件 ~25MB，不纳入版本控制 |
| `__pycache__/`, `*.pyc` | Python 编译缓存 |
| `.conda/`, `venv/` | 环境目录，每个环境数百 MB |
| `.env` | 可能含密钥 |
| `Thumbs.db`, `.DS_Store` | 系统垃圾文件 |