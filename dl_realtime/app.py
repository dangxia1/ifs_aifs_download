"""大气河短期预报支撑平台 ARFS — Streamlit 界面.

运行: streamlit run app.py --server.port 8501
"""
import base64
import os
import time
from pathlib import Path

import streamlit as st
import yaml

# 数据目录解析顺序: 环境变量 > config_realtime.yaml > 包内相对路径 (绿色包)
def _resolve_save_dir():
    env = os.environ.get("EC_SAVE_DIR")
    if env:
        return env
    cfg_path = Path(__file__).resolve().parent / "config_realtime.yaml"
    if cfg_path.exists():
        try:
            cfg = yaml.safe_load(open(cfg_path, encoding="utf-8")) or {}
            if cfg.get("save_dir"):
                return cfg["save_dir"]
        except Exception:
            pass
    return str(Path(__file__).resolve().parent / "data")


SAVE_DIR = _resolve_save_dir()
FIG_ROOT = Path(SAVE_DIR) / "figures"
DOCS_DIR = Path(__file__).resolve().parent / "docs"

REGIONS = {
    "全球": "global",
    "东亚": "east_asia",
    "华北": "north_china",
}

PLAY_SPEED = 0.4  # 播放间隔 (秒)


def _bg_css():
    """背景图 (调暗) + 亮色按钮 的 CSS."""
    img_path = DOCS_DIR / "背景.jpg"
    if img_path.exists():
        b64 = base64.b64encode(img_path.read_bytes()).decode()
        bg = f"url(data:image/jpeg;base64,{b64})"
    else:
        bg = "linear-gradient(#0a0e14, #0a0e14)"
    return f"""
    <style>
    .stApp {{
        background: linear-gradient(rgba(8, 12, 18, 0.86), rgba(8, 12, 18, 0.86)), {bg};
        background-size: cover; background-position: center;
        background-attachment: fixed;
        color: #e0e4e8;
    }}
    .stApp header {{ background: transparent; }}

    /* 标题 (渐变, 保持原样) */
    h1 {{ font-weight: 700; letter-spacing: -0.02em;
         background: linear-gradient(135deg, #4da6ff, #a78bfa, #f472b6);
         -webkit-background-clip: text; -webkit-text-fill-color: transparent;
         font-size: 3.15rem !important; }}  /* 标题 ×1.5 */

    /* 亮色按钮 */
    .stButton button {{
        background: linear-gradient(135deg, #2f8cff, #5aa7ff);
        color: #ffffff !important; font-weight: 600;
        border: none; border-radius: 8px; transition: all 0.15s;
    }}
    .stButton button:hover {{ transform: translateY(-1px);
        box-shadow: 0 4px 14px rgba(47,140,255,.4); }}
    .stButton button[kind="secondary"] {{
        background: rgba(255,255,255,.12); color: #ffffff !important;
        font-size: 1.6rem !important; }}  /* ×1.5 */
    .stButton button[kind="secondary"]:hover {{
        background: rgba(255,255,255,.22); }}

    /* 所有按钮: 纯白 + 大字号 (×1.5, 含 step 日期按钮) */
    .stButton button {{
        color: #ffffff !important;
        font-size: 1.6rem !important;
    }}

    /* tab 标签 (预报图 / 北京地区大气河强度时间序列) */
    [data-testid="stTabs"] button,
    [data-baseweb="tab"] {{
        font-size: 1.6rem !important;
    }}

    /* 区域切换 segmented control / radio: 字号 ×1.5 */
    [data-testid="stSegmentedControl"] button,
    [data-testid="stSegmentedControl"] label,
    [data-testid="stRadio"] label,
    [role="radio"] {{
        font-size: 1.6rem !important;
    }}

    /* 全局兜底: Streamlit 版本 DOM 结构变化时 .stButton 可能失效,
       直接打全局 button 必命中 (2026-08-06 换思路) */
    button {{
        font-size: 1.6rem !important;
    }}

    /* 加固 (2026-08-06 二轮): rem 依赖 html 根字号, 主题异常时 1.6rem 会偏小
       → 根字号钉死 16px; 容器级/role 级选择器防 DOM 结构变化; px 兜底 */
    html {{
        font-size: 16px !important;
    }}
    .stApp {{
        font-size: 1.6rem !important;
    }}
    [data-testid="stTabs"],
    [data-testid="stSegmentedControl"],
    [data-testid="stRadio"],
    [role="tablist"],
    [role="radiogroup"] {{
        font-size: 1.6rem !important;
    }}
    button, [role="tab"], [role="radio"] {{
        font-size: 25px !important;
    }}
    /* step 按钮 (固定高度容器内): 间隔不变 */
    [data-testid="stVerticalBlock"] .stButton button {{
        width: 100%; text-align: left;
        margin-bottom: 3px; padding: 5px 8px;
    }}

    /* 兜底: .stApp 作用域内所有文本纯白 (渐变标题由 -webkit-text-fill-color 保护) */
    .stApp p, .stApp span, .stApp strong, .stApp label, .stApp li {{
        color: #ffffff !important;
    }}
    /* caption 字号 */
    [data-testid="stCaptionContainer"],
    [data-testid="stCaptionContainer"] p {{
        font-size: 1.05rem !important;
    }}

    /* 隐藏右上角主题切换工具栏 */
    [data-testid="stAppToolbar"] {{ visibility: hidden; }}

    /* 圆形播放按钮 */
    .play-round button {{
        width: 56px !important; height: 56px !important;
        border-radius: 50% !important; font-size: 1.3rem !important;
        padding: 0 !important; min-width: 56px !important;
        display: flex; align-items: center; justify-content: center;
    }}

    /* 进度条 */
    [data-testid="stProgress"] > div > div {{
        background: linear-gradient(90deg, #2f8cff, #a78bfa); }}

    /* caption */
    [data-testid="stCaptionContainer"] {{ color: #9aa5b1 !important; }}
    </style>
    """


@st.cache_data(ttl=600)
def list_steps(region_key):
    d = FIG_ROOT / region_key
    if not d.exists():
        return []
    files = sorted(d.glob("step*.png"),
                   key=lambda f: int(f.stem.replace("step", "")))
    return [f.stem for f in files]


@st.cache_data(ttl=600)
def load_image(region_key, step_tag):
    path = FIG_ROOT / region_key / f"{step_tag}.png"
    if path.exists():
        return path.read_bytes()
    return None


@st.cache_data(ttl=600)
def load_run_time():
    """读取起报时间 (北京时间). 例: '2026-08-04 14:00'"""
    p = Path(SAVE_DIR) / "run_time.json"  # SAVE_DIR 根, 不被 figures rmtree 删
    if p.exists():
        try:
            import json
            return json.load(open(p)).get("run_time", "")
        except Exception:
            return ""
    return ""


def valid_label(tag, run_time):
    """step6 + 起报 2026-08-04 14:00 → '08/04 20:00' (预报时间)."""
    if not run_time:
        return tag
    from datetime import datetime, timedelta
    step_h = int(tag.replace("step", ""))
    rt = datetime.strptime(run_time, "%Y-%m-%d %H:%M")
    vt = rt + timedelta(hours=step_h)
    return f"{vt.strftime('%m/%d')} {vt.hour:02d}:00"


def main():
    st.set_page_config(page_title="大气河短期预报支撑平台 ARFS", layout="wide")
    st.markdown(_bg_css(), unsafe_allow_html=True)

    st.title("大气河短期预报支撑平台 Atmospheric River Forecast Support (ARFS)")

    run_time = load_run_time()
    rt_line = f"起报时间: {run_time} (北京时间)" if run_time else "起报时间: 未知 (北京时间)"
    model_line = "数值天气预报模型(IFS) 对比 人工智能预报模型(AIFS)"
    st.markdown(
        f'<p style="color:#ffffff;font-size:1.6rem;margin:0">{rt_line}'
        f' <span style="font-size:1.15rem;color:#9aa5b1">[UI v3]</span></p>'
        f'<p style="color:#ffffff;font-size:1.6rem;margin:0">{model_line}</p>',
        unsafe_allow_html=True)

    # ── Tab/区域/时次按键全部用 HTML 链接 + query_params ──
    # (2026-08-06: 组件字号需 CSS 覆盖, 而 <style> 注入在该 Streamlit 环境
    # 不生效; st.markdown 内联样式一直生效 → 按键改内联样式, 与图例同机制)
    from streamlit import query_params

    def _qp(name, default=None):
        v = query_params.get(name)
        return v[0] if isinstance(v, list) else (v or default)

    def _q(**kw):
        base = {k: (v[0] if isinstance(v, list) else v)
                for k, v in query_params.items()}
        base.update(kw)
        return "?" + "&".join(f"{k}={v}" for k, v in base.items())

    def _btn(href, text, active=False, block=False):
        bg = ("linear-gradient(135deg,#2f8cff,#5aa7ff)" if active
              else "rgba(255,255,255,.12)")
        width = ("width:100%;text-align:left;box-sizing:border-box;"
                 if block else "")
        return (f'<a href="{href}" style="display:inline-block;{width}'
                f'font-size:19px;color:#fff;font-weight:600;padding:8px 20px;'
                f'margin-bottom:4px;border-radius:8px;text-decoration:none;'
                f'background:{bg};">{text}</a>')

    tab = _qp("tab", "map")
    region = _qp("region", "global")
    step_q = _qp("step")

    # ── Tab 切换 (内联字号 25px) ──
    st.markdown(
        f'<div style="display:flex;gap:12px;margin:0 0 8px 0;">'
        f'{_btn(_q(tab="map"), "预报图", active=(tab == "map"))}'
        f'{_btn(_q(tab="ts"), "北京地区大气河强度时间序列", active=(tab == "ts"))}'
        f'</div>', unsafe_allow_html=True)

    if tab == "ts":
        # ── 时序图 ──
        ts_path = FIG_ROOT / "north_china_timeseries.png"
        if ts_path.exists():
            st.image(ts_path.read_bytes(),
                     use_container_width=True)
            # 图例: 格式与预报图下方图例一致 (background 圆点, 不受 CSS 白色覆盖)
            st.markdown(
                """
                <div style="display:flex;gap:24px;align-items:center;padding:10px 16px;
                            background:rgba(255,255,255,.07);border-radius:8px;
                            font-size:16px;color:#fff;flex-wrap:wrap;">
                  <span><span style="display:inline-block;width:14px;height:14px;background:#444444;border-radius:2px;margin-right:6px;"></span>无大气河 (IVT&lt;250)</span>
                  <span><span style="display:inline-block;width:14px;height:14px;border:2px dashed #aaa;border-radius:2px;margin-right:6px;"></span>无柱 = 未识别出大气河 (IVT≥250 未检出)</span>
                  <span><span style="display:inline-block;width:56px;height:14px;background:linear-gradient(90deg,#3498db,#f1c40f,#e67e22,#d35400,#e74c3c);border-radius:2px;margin-right:6px;"></span>大气河等级 (蓝1级~红5级)</span>
                </div>
                """,
                unsafe_allow_html=True)
        else:
            st.warning("时序图尚未生成 — 运行 dl_realtime.py 后自动产出")
        return

    # ── 地图 tab ──
    # 区域切换 (HTML 链接, 内联字号; URL 用英文参数, 显示中文标签)
    st.markdown(
        '<div style="display:flex;gap:12px;margin:0 0 8px 0;">'
        + "".join(_btn(_q(region=v), k, active=(region == v))
                  for k, v in REGIONS.items())
        + '</div>', unsafe_allow_html=True)

    region_key = region
    steps = list_steps(region_key)
    if not steps:
        st.error(f"没有找到图片: {FIG_ROOT / region_key} — 先运行 dl_realtime.py")
        st.stop()

    # 当前时次: URL 指定且存在 → 用之; 否则默认第一张 (2026-08-06)
    step_sel = step_q if step_q in steps else steps[0]
    st.session_state["step_sel"] = step_sel
    st.session_state["region"] = region_key

    # ── 主布局: 左图 (大) 右侧固定面板 ──
    col_img, col_side = st.columns([5, 1])

    with col_side:
        # ── 面板顶部: 圆形播放按钮 + 同行进度条 ──
        c_play, c_prog = st.columns([1, 3])
        with c_play:
            st.markdown('<div class="play-round">', unsafe_allow_html=True)
            play = st.button("▶", key="btn_play", help="播放动画",
                             type="primary")
            st.markdown('</div>', unsafe_allow_html=True)
        with c_prog:
            prog_ph = st.empty()
            prog_bar = prog_ph.progress(0.0, text="就绪")

        st.markdown('<p style="font-size:19px;color:#fff;font-weight:700;margin:0 0 4px 0">预报时次选择</p>',
                    unsafe_allow_html=True)
        # step 滚动面板 (原生固定高度容器, 避免 HTML div 空黑框)
        try:
            step_container = st.container(height=380)
        except TypeError:
            step_container = st.container()
        with step_container:
            for tag in steps:
                st.markdown(_btn(_q(step=tag), valid_label(tag, run_time),
                                 active=(tag == step_sel), block=True),
                            unsafe_allow_html=True)

    with col_img:
        if play:
            # 左侧大图放映 + 进度条同步
            img_ph = st.empty()
            for i, s in enumerate(steps):
                data = load_image(region_key, s)
                if data:
                    img_ph.image(data, use_container_width=True)
                prog_bar.progress((i + 1) / len(steps),
                                  text=f"第 {i + 1}/{len(steps)} 帧")
                time.sleep(PLAY_SPEED)
            prog_ph.empty()  # 播放完成, 清空进度条框
        else:
            data = load_image(region_key, step_sel)
            if data:
                st.image(data, use_container_width=True)
                # 原图下载 (浏览器可打开)
                st.download_button(
                    "查看原图",
                    data=data,
                    file_name=f"{region_key}_{step_sel}.png",
                    mime="image/png",
                    key="btn_download",
                )

            # 图例说明: 恒显示在图片下方 (播放/缺图时也可见, 2026-08-06)
            # background 圆点/白✚黑描边: CSS 强制白色 span 不影响
            st.markdown(
                """
                <div style="padding:10px 16px;background:rgba(255,255,255,.07);
                            border-radius:8px;font-size:1.05rem;color:#fff;">
                  <div style="display:flex;gap:28px;align-items:center;flex-wrap:wrap;">
                    <span><span style="display:inline-block;width:16px;height:16px;border-radius:50%;background:#ff0000;margin-right:6px;"></span>大气河河轴</span>
                    <span><span style="color:#fff;text-shadow:-1px 0 #000,1px 0 #000,0 -1px #000,0 1px #000;font-size:1.1rem;margin-right:4px;">✚</span>大气河质心</span>
                  </div>
                  <div style="display:flex;gap:28px;align-items:center;flex-wrap:wrap;margin-top:8px;">
                    <span><span style="display:inline-block;width:16px;height:16px;border-radius:50%;background:#C5E1A5;margin-right:6px;"></span>大雨</span>
                    <span><span style="display:inline-block;width:16px;height:16px;border-radius:50%;background:#66BB6A;margin-right:6px;"></span>暴雨</span>
                    <span><span style="display:inline-block;width:16px;height:16px;border-radius:50%;background:#1B5E20;margin-right:6px;"></span>大暴雨</span>
                    <span><span style="display:inline-block;width:16px;height:16px;border-radius:50%;background:#00838F;margin-right:6px;"></span>特大暴雨</span>
                  </div>
                  <div style="margin-top:8px;color:#fff;">水汽通量(IVT): 半透明区域未识别出大气河, 不透明区域为大气河</div>
                </div>
                """,
                unsafe_allow_html=True)


if __name__ == "__main__":
    main()
