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

    /* 标题 */
    h1 {{ font-weight: 700; letter-spacing: -0.02em;
         background: linear-gradient(135deg, #4da6ff, #a78bfa, #f472b6);
         -webkit-background-clip: text; -webkit-text-fill-color: transparent;
         font-size: 2.1rem !important; }}

    /* 亮色按钮 */
    .stButton button {{
        background: linear-gradient(135deg, #2f8cff, #5aa7ff);
        color: #ffffff !important; font-weight: 600;
        border: none; border-radius: 8px; transition: all 0.15s;
    }}
    .stButton button:hover {{ transform: translateY(-1px);
        box-shadow: 0 4px 14px rgba(47,140,255,.4); }}
    .stButton button[kind="secondary"] {{
        background: rgba(255,255,255,.12); color: #e8ecf0 !important; }}
    .stButton button[kind="secondary"]:hover {{
        background: rgba(255,255,255,.22); }}

    /* step 按钮 (固定高度容器内) */
    [data-testid="stVerticalBlock"] .stButton button {{
        width: 100%; text-align: left; font-size: 0.72rem;
        margin-bottom: 3px; padding: 4px 8px;
    }}

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
    p = FIG_ROOT / "run_time.json"
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
    st.caption(f"ECMWF Open Data · IFS vs AIFS · 起报 {run_time} (北京时间) · step 0-144h"
               if run_time else
               "ECMWF Open Data · IFS vs AIFS · step 0-144h · 时间为北京时间(UTC+8)")

    tab_map, tab_ts = st.tabs(["预报图", "华北 AR 强度时间序列"])

    with tab_ts:
        ts_path = FIG_ROOT / "north_china_timeseries.png"
        if ts_path.exists():
            st.image(ts_path.read_bytes(),
                     caption="North China AR Intensity (0-144h)",
                     use_container_width=True)
            st.caption("灰柱=无AR | 透明斜线=IVT达标未识别 | 彩色=AR等级(蓝/黄/橙/橙红/红)")
        else:
            st.warning("时序图尚未生成 — 运行 dl_realtime.py 后自动产出")

    with tab_map:
        # ── 区域切换 ──
        try:
            region_label = st.segmented_control(
                "选择区域", list(REGIONS.keys()), default="全球",
                label_visibility="collapsed",
            )
        except (TypeError, AttributeError):
            region_label = st.radio(
                "选择区域", list(REGIONS.keys()), index=0,
                label_visibility="collapsed", horizontal=True,
            )
        region_key = REGIONS[region_label]

        steps = list_steps(region_key)
        if not steps:
            st.error(f"没有找到图片: {FIG_ROOT / region_key} — 先运行 dl_realtime.py")
            st.stop()

        if "step_sel" not in st.session_state or st.session_state.get("region") != region_key:
            st.session_state["step_sel"] = steps[-1]
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

            st.markdown("**预报时次选择**")
            # step 滚动面板 (原生固定高度容器, 避免 HTML div 空黑框)
            try:
                step_container = st.container(height=380)
            except TypeError:
                step_container = st.container()
            with step_container:
                for tag in steps:
                    label = valid_label(tag, run_time)
                    if st.button(label, key=f"btn_{tag}",
                                 type="primary" if tag == st.session_state["step_sel"] else "secondary"):
                        st.session_state["step_sel"] = tag
                        st.rerun()

        with col_img:
            step_sel = st.session_state["step_sel"]

            if play:
                # 左侧大图放映 + 进度条同步
                img_ph = st.empty()
                for i, s in enumerate(steps):
                    data = load_image(region_key, s)
                    if data:
                        img_ph.image(data, caption=f"{region_label} — {valid_label(s, run_time)}",
                                     use_container_width=True)
                    prog_bar.progress((i + 1) / len(steps),
                                      text=f"第 {i + 1}/{len(steps)} 帧")
                    time.sleep(PLAY_SPEED)
                prog_ph.empty()  # 播放完成, 清空进度条框
            else:
                data = load_image(region_key, step_sel)
                if data:
                    st.image(data, caption=f"{region_label} — {valid_label(step_sel, run_time)}",
                             use_container_width=True)
                    # 原图下载 (浏览器可打开)
                    st.download_button(
                        "查看原图",
                        data=data,
                        file_name=f"{region_key}_{step_sel}.png",
                        mime="image/png",
                        key="btn_download",
                    )


if __name__ == "__main__":
    main()
