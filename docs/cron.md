# Cron 定时运行指南

`dl_2026.py` 需要每日运行以拉取最新预报数据（最近 5 天）。以下是各平台定时运行方案。

## 前提

```bash
conda activate ifs_aifs
cd /path/to/ifs-aifs-ai
```

建议先手动跑一次确认可行：
```bash
python scripts/dl_2026.py
```

## Linux / macOS — crontab

```bash
# 编辑 crontab
crontab -e

# 每天 08:00 UTC 运行（ecmwf 数据通常在 07:00~08:00 UTC 更新完毕）
0 8 * * * cd /path/to/ifs-aifs-ai && /path/to/conda/envs/ifs_aifs/bin/python scripts/dl_2026.py >> log/cron.log 2>&1
```

- `>> log/cron.log 2>&1`: 输出追加到日志，排查问题用
- 若使用不同时区，自行换算出对应 UTC:08:00 的本地时间
- 可用 [crontab.guru](https://crontab.guru) 验证 cron 表达式

## Linux — systemd timer（备选）

更可靠的方案，适合生产环境：

1. 创建 service 文件 `/etc/systemd/system/dl-2026.service`：

```ini
[Unit]
Description=ECMWF IFS/AIFS daily download

[Service]
Type=oneshot
User=your-user
WorkingDirectory=/path/to/ifs-aifs-ai
ExecStart=/path/to/conda/envs/ifs_aifs/bin/python scripts/dl_2026.py
```

2. 创建 timer 文件 `/etc/systemd/system/dl-2026.timer`：

```ini
[Unit]
Description=Daily ECMWF download trigger
Requires=dl-2026.service

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
```

3. 启用：
```bash
sudo systemctl enable dl-2026.timer
sudo systemctl start dl-2026.timer
systemctl list-timers dl-2026.timer
```

## Windows — 任务计划程序

1. 打开 **任务计划程序** (Task Scheduler)
2. **创建基本任务** → 名称：`IFS-AIFS Daily Download`
3. **触发器**：每天，选择 UTC 08:00 对应的本地时间
4. **操作** → 新建：
   - 程序：`cmd.exe`
   - 参数：`/c conda activate ifs_aifs && cd /d D:\Projects\ifs-aifs-ai && python scripts\dl_2026.py >> log\cron.log 2>&1`
5. 勾选 **不管用户是否登录都要运行**（若需后台运行）

或使用 PowerShell 创建：
```powershell
$action = New-ScheduledTaskAction -Execute "cmd.exe" `
  -Argument '/c conda activate ifs_aifs && cd /d D:\Projects\ifs-aifs-ai && python scripts\dl_2026.py >> log\cron.log 2>&1'
$trigger = New-ScheduledTaskTrigger -Daily -At "16:00"
Register-ScheduledTask -TaskName "IFS-AIFS Daily Download" -Action $action -Trigger $trigger
```

## 补缺口 — 按需运行

ecmwf 源仅保留 ~4 天，过期文件需用 `dl_anytime.py` 从 Azure 补：

```bash
# 补单日
python scripts/dl_anytime.py 2026-05-01 2026-05-01

# 补整月
python scripts/dl_anytime.py 2026-05-01 2026-05-31
```

建议每周手动补一次，或在 cron 中加一条周级任务。

## 常见问题

| 问题 | 解决 |
|---|---|
| conda 命令找不到 | cron 环境下 PATH 极简，用 conda env 的 python 绝对路径 |
| 输出为空 | 检查 python 路径、工作目录是否正确 |
| `FileNotFoundError: config.yaml` | 确保 `WorkingDirectory` 设置在项目根目录 |