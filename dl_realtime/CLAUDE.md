# dl_realtime — 实时预报 + IVT + AR + 可视化

> 项目完整说明见 [README.md](README.md) 和 [docs/代码逻辑.md](docs/代码逻辑.md)

## 核心文件

| 文件 | 职责 | 常改动 |
|------|------|--------|
| `dl_realtime.py` | 主管线（缓存/下载/IVT/AR/图） | ✅ |
| `visualize_ivt.py` | 画图（Basemap + bluemarble + AR + 降水） | ✅ |
| `viewer.html` | HTML 展示页（零依赖, 2026-08-06 取代 app.py/Streamlit） | ✅ |
| `north_china_timeseries.py` | 北京地区 AR 时序图 | 偶 |
| `config_realtime.yaml` | 配置（step/模型/路径） | 偶 |
| `utils.py` | 共享模块 | 少 |
| `compute_ivt.py` | IVT 计算 | 少 |
| `make_font.py` | 中文字体自动生成 | 少 |
| `bavi_step0.py` | 巴威个例 step0 华北图 | 临时 |
| `bavi_forecast.py` | 巴威个例预报场东亚图 | 临时 |
| `make_green_win.py` | Windows 离线绿包交叉打包 | 少 |
| `China_provinces.shp` / `Continent.shp` | 中国立场边界（省界/海岸线，老师提供） | 少 |

## 关键机制

### AR 时间恢复 (visualize_ivt._revive_series)

- 消失帧前推 4 帧、生成帧后推 4 帧高斯加权合成先验 (0.4/0.3/0.2/0.1)，≥0.5 直接恢复，**无轴长/IVT 门槛** (2026-08-06 晚, 门槛挡住 48h 恢复已删)
- mask 优先熵权法重识别，空 → 先验 mask 兜底；恢复结果参与后续时次加权
- 重算河轴走老师 First_new.py 原版流程：偏移后膨胀3次+填洞+再骨架化重连 (2026-08-06)，重连后**距离过滤**（轴点离 plume 边界 >5°/res+1 格剔除）
- 河轴**纯红散点**（2026-08-06 去白描边）
- plume 未变 (平滑/恢复未修改) 的帧保留 detect_ar 原轴，不重算

### 中国立场边界 (visualize_ivt._read_shp_rings/_draw_shapefile)

- `China_provinces.shp`(省界, 含南海诸岛) 画东亚/华北; `Continent.shp`(全球海岸线) 画所有区域
- 只有 `.shp` 本体 (无 .shx/.dbf) → 纯 struct 解析 ring 画线, 不依赖 pyshp/ogr
- 窗口相交裁剪 + 抽稀 + 全局缓存 (75 图 × 15 进程只解析一次); 文件缺失静默跳过
- 绿包打包时随代码复制 (make_green_win.py)

### 缓存（.last_run）

- 单行 `YYYY-MM-DD HHZ`（IFS 和 AIFS 对齐时次取 min）
- 对齐 ≠ 缓存 → 全流程（下载/IVT/AR/图）
- 对齐 = 缓存 → figures ≥ 75 张直接退出；figures < 75 → 只重画图（数据不变，跳过下载/IVT/AR）
- 强制重跑：`rm ec_realtime/.last_run`

### run_time.json

- 脚本开头立即写入 `run_time.json`（SAVE_DIR 根, 不在 figures/ 下——visualize_all 会 rmtree(figures)；`{"run_time": "2026-08-04 14:00"}`，北京时间）
- 网页用：标题栏显示起报时间，右侧按钮由 valid_label() 转换为预报时间（`08/04 20:00`）

### HTML 展示 (viewer.html, 2026-08-06 取代 Streamlit)

- 单文件纯 HTML+CSS+JS, 零第三方依赖; 页内路径全部走 **JS 多前缀探测** (2026-08-07): `figures/` → `data/figures/` → `../figures/` → `../data/figures/`, 首中缓存 — 项目根/数据根/绿包 data/ 三种放置均可用, 不再 404
- 背景图: 探测 `背景.jpg` → `docs/背景.jpg`, JS 叠加暗化渐变; 缺失回退深色底色 (2026-08-07 恢复 streamlit 效果)
- 启动: `python -m http.server 8501 --directory <数据目录根>` (服务器用 `--bind 0.0.0.0`)
- file:// 双击可用 (图能显示), 仅 run_time.json fetch 被拦 → 降级显示 stepN
- URL hash 同步 `#map/global/step6` / `#ts`; 时次按钮标签 = run_time + step 换算的预报时间
- 绿包: make_green_win.py 拷 viewer.html + 背景.jpg + run_time.json 到 data/ (run_time.json 在 SAVE_DIR 根, 2026-08-07 修复旧路径 bug) + start.bat 用 runtime python 起 http.server
- 视觉 v2.3 (2026-08-07, frontend-design skill 指导): 深色科学仪器风 + 单一琥珀强调色 + 大字号 (面向 50 岁预报员); 版本标记在 HTML 头部注释 `ARFS HTML 展示页 (v2.3, …)` — 页脚文字已删
- ⚠️ 播放动画必须预载 + 保留旧帧 (`showImage(src, smooth)`), 否则大 PNG 解码慢于 0.4s/帧时每两张黑一下 (v2.3 修复); step 须防御回退, 否则 URL 会拼出 stepundefined.png
- ⚠️ 路径探测结果必须**赋值**给 figBase (曾漏赋值导致绿包/服务器一直报"未找到图片数据目录"; 首候选命中时值为空串 "" 属正常, 判失败要用 `=== null`)

### 并行

- 下载：18 进程（mp.Process，非 daemon）
- AR 检测：4 进程（同）
- 可视化：15 进程（mp.Pool，复用 bluemarble warp）
- 所有多进程方案已处理：Pool daemon → 改用 mp.Process；FilFinder2D 再开子进程 → 用 Process 非 daemon

### 降水标注

- tp 为累积量，差分：未来 12h = tp(N+12)-tp(N)，未来 24h = tp(N+24)-tp(N)
- 4 级绿色圆点（大雨/暴雨/大暴雨/特大暴雨），逐格点取最高等级只标一次
- 圆点尺寸按区域缩放：全球 ×1 / 东亚 ×2 / 华北 ×3（2026-08-06 老师要求，老同志看得见）
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
| 网页 (http.server) | `http://10.2.7.31:8501/viewer.html` |

## 常见操作

```bash
# 只重画图
rm -rf /shared_data/zongshen/ec_realtime/figures
python dl_realtime.py    # 缓存命中 → re-plot 分支, 几分钟

# 强制全流程
rm -f /shared_data/zongshen/ec_realtime/.last_run
python dl_realtime.py

# 展示页部署 (HTML 版, 替代 streamlit; 背景图一并拷, 缺省自动回退)
cp viewer.html /shared_data/zongshen/ec_realtime/
cp docs/背景.jpg /shared_data/zongshen/ec_realtime/
pkill -f "http.server 8501"
nohup python -m http.server 8501 --directory /shared_data/zongshen/ec_realtime > /shared_data/zongshen/ec_realtime/log/httpd.log 2>&1 &
# 浏览器: http://10.2.7.31:8501/viewer.html

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
- 展示层是纯静态 HTML（viewer.html），改样式/字号直接改 HTML/CSS，无框架限制
- `.last_run` 格式为单行字符串，不是 JSON
- 绿图标色用 `color="#ff0000"` 而非十六进制字符串，matplotlib 接受两种
- 不要手动改 `visualize_ivt.py` 的 `_read_ivt` 经度排序逻辑（ECMWF 0~360 → -180~180 转换已安全）
- Git 协作：本地主导推送，服务器只 pull，不 push