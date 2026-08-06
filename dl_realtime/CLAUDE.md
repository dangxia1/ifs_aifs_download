# dl_realtime — 实时预报 + IVT + AR + 可视化

> 项目完整说明见 [README.md](README.md) 和 [docs/代码逻辑.md](docs/代码逻辑.md)

## 核心文件

| 文件 | 职责 | 常改动 |
|------|------|--------|
| `dl_realtime.py` | 主管线（缓存/下载/IVT/AR/图） | ✅ |
| `visualize_ivt.py` | 画图（Basemap + bluemarble + AR + 降水） | ✅ |
| `app.py` | Streamlit 界面（ARFS） | ✅ |
| `north_china_timeseries.py` | 华北 AR 时序图 | 偶 |
| `config_realtime.yaml` | 配置（step/模型/路径） | 偶 |
| `utils.py` | 共享模块 | 少 |
| `compute_ivt.py` | IVT 计算 | 少 |
| `make_font.py` | 中文字体自动生成 | 少 |
| `bavi_step0.py` | 巴威个例 step0 华北图 | 临时 |
| `bavi_forecast.py` | 巴威个例预报场东亚图 | 临时 |
| `make_green_win.py` | Windows 离线绿包交叉打包 | 少 |

## 关键机制

### 缓存（.last_run）

- 单行 `YYYY-MM-DD HHZ`（IFS 和 AIFS 对齐时次取 min）
- 对齐 ≠ 缓存 → 全流程（下载/IVT/AR/图）
- 对齐 = 缓存 → figures ≥ 75 张直接退出；figures < 75 → 只重画图（数据不变，跳过下载/IVT/AR）
- 强制重跑：`rm ec_realtime/.last_run`

### run_time.json

- 脚本开头立即写入 `figures/run_time.json`（`{"run_time": "2026-08-04 14:00"}`，北京时间）
- 网页用：标题栏显示起报时间，右侧按钮由 valid_label() 转换为预报时间（`08/04 20:00`）

### 并行

- 下载：18 进程（mp.Process，非 daemon）
- AR 检测：4 进程（同）
- 可视化：15 进程（mp.Pool，复用 bluemarble warp）
- 所有多进程方案已处理：Pool daemon → 改用 mp.Process；FilFinder2D 再开子进程 → 用 Process 非 daemon

### 降水标注

- tp 为累积量，差分：未来 12h = tp(N+12)-tp(N)，未来 24h = tp(N+24)-tp(N)
- 4 级绿色圆点（大雨/暴雨/大暴雨/特大暴雨），逐格点取最高等级只标一次
- 实时下载需 156/168（config 的 steps_extra）；巴威东亚需下载到 96h

### 中文字体

- `make_font.py` 自动从系统 Noto ttc 提取 SC 子字体 + 子集化 → ~2MB
- 目标目录：`/shared_data/zongshen/fonts/`（服务器）> 项目 `fonts/`
- 幂等，不进 git（`.gitignore` 已屏蔽）
- matplotlib 注册后需 `fm._load_fontmanager(try_read_cache=False)` 重建缓存

## 服务器路径

| 用途 | 路径 |
|------|------|
| 代码 | `/home/zongshen/ifs_aifs_download/dl_realtime/` |
| 数据 | `/shared_data/zongshen/ec_realtime/` |
| 月度数据 | `/shared_data/zongshen/ec_monthly_ivt/{YYYYMM}/` |
| 巴威图 | `/shared_data/zongshen/bavi_case/` |
| 阈值 | `/shared_data_5/ntfs2/liangju/ARIA_Asia_v15/ERA5/` |
| 字体 | `/shared_data/zongshen/fonts/` |
| conda | `/shared_data/zongshen/miniforge3/` |
| Streamlit | `http://10.2.7.31:8501` |

## 常见操作

```bash
# 只重画图
rm -rf /shared_data/zongshen/ec_realtime/figures
python dl_realtime.py    # 缓存命中 → re-plot 分支, 几分钟

# 强制全流程
rm -f /shared_data/zongshen/ec_realtime/.last_run
python dl_realtime.py

# 重启 Streamlit
pkill -f "streamlit run"
nohup streamlit run app.py --server.port 8501 --server.headless true > /shared_data/zongshen/ec_realtime/log/streamlit.log 2>&1 &

# Windows 离线绿包打包 (服务器, 交叉打包, 无需对方装 Python)
conda activate ifs_aifs && python make_green_win.py
# → /shared_data/zongshen/ARFS_green_win.zip, 详见 打包分发.md
```

## 工作流：临时诊断代码

- 需要服务器跑的测试/诊断代码：**写入 `ivt处理/项目计划.md`**（用户可复制粘贴），不用写脚本文件
- 测试完成后：**删除该节**（不留文档残留）
- 用户偏好 Edit 工具修改（VSCode 可见），少用 Bash 追加

## 注意

- 绘图用 Basemap（非 cartopy），bluemarble 全分辨率 warp 慢但画质最佳
- Streamlit 1.60 CSS 用 `config.toml` 设主题 + 内联样式兜底，secondary 按钮颜色是特异性覆盖的常见陷阱
- `.last_run` 格式为单行字符串，不是 JSON
- 绿图标色用 `color="#ff0000"` 而非十六进制字符串，matplotlib 接受两种
- 不要手动改 `visualize_ivt.py` 的 `_read_ivt` 经度排序逻辑（ECMWF 0~360 → -180~180 转换已安全）
- Git 协作：本地主导推送，服务器只 pull，不 push