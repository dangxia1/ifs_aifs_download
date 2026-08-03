"""大气河短期预报支撑平台 ARFS — Streamlit 界面.

运行: streamlit run app.py --server.port 8501
"""
import os
import time
from pathlib import Path

import streamlit as st

# 数据目录
SAVE_DIR = os.environ.get("EC_SAVE_DIR", "/shared_data/zongshen/ec_realtime")
FIG_ROOT = Path(SAVE_DIR) / "figures"

REGIONS = {
    "全球": "global",
    "东亚": "east_asia",
    "华北": "north_china",
}

PLAY_SPEED = 0.4  # 播放间隔 (秒)
STEP_COLS = 5     # step 网格列数


@st.cache_data(ttl=600)
def list_steps(region_key):
    """列出该区域已有的 step PNG 文件."""
    d = FIG_ROOT / region_key
    if not d.exists():
        return []
    files = sorted(d.glob("step*.png"),
                   key=lambda f: int(f.stem.replace("step", "")))
    return [f.stem for f in files]


@st.cache_data(ttl=600)
def load_image(region_key, step_tag):
    """加载单张图 (原图 bytes)."""
    path = FIG_ROOT / region_key / f"{step_tag}.png"
    if path.exists():
        return path.read_bytes()
    return None


def step_label(tag):
    """step72 → 72h"""
    return f"{int(tag.replace('step', ''))}h"


@st.dialog("查看原图")
def show_full_image(region_key, step_tag):
    """弹窗显示原图 (完整分辨率)."""
    data = load_image(region_key, step_tag)
    if data:
        st.image(data, caption=f"{REGIONS[region_key]} — {step_label(step_tag)}",
                 use_container_width=True)


def theme_css(dark):
    """白天/夜间视觉模式."""
    if dark:
        return """
        <style>
        .stApp { background-color: #0e1117; color: #fafafa; }
        .stApp header { background-color: #0e1117; }
        [data-testid="stCaptionContainer"] { color: #bbb !important; }
        .stButton button { color: #ddd; }
        </style>
        """
    return """
    <style>
    .stApp { background-color: #ffffff; color: #111111; }
    .stApp header { background-color: #ffffff; }
    </style>
    """


def main():
    st.set_page_config(page_title="大气河短期预报支撑平台 ARFS", layout="wide")

    # ── 左上: 视觉模式切换 ──
    col_theme, col_info = st.columns([1, 5])
    with col_theme:
        dark = st.toggle("夜间模式", value=True)
    with col_info:
        st.caption("数据来源: ECMWF Open Data | 预报时次: 最新起报, step 0-144h | IFS vs AIFS")
    st.markdown(theme_css(dark), unsafe_allow_html=True)
    st.title("大气河短期预报支撑平台 Atmospheric River Forecast Support (ARFS)")
    st.caption("ECMWF Open Data · IFS vs AIFS · step 0-144h")

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
        # ── 区域切换: 图片上方, 点击直接切换 ──
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

        # 当前选中 step (session 记忆)
        if "step_sel" not in st.session_state or st.session_state.get("region") != region_key:
            st.session_state["step_sel"] = steps[-1]
            st.session_state["region"] = region_key

        # ── 主布局: 左图 (大) 右控制面板 ──
        col_img, col_side = st.columns([4, 1])

        with col_side:
            play = st.button("播放动画", type="primary", use_container_width=True)
            st.markdown("**时次**")
            for r in range(0, len(steps), STEP_COLS):
                cols = st.columns(STEP_COLS)
                for c, tag in enumerate(steps[r:r + STEP_COLS]):
                    with cols[c]:
                        if st.button(step_label(tag), key=f"btn_{tag}",
                                     use_container_width=True,
                                     type="primary" if tag == st.session_state["step_sel"] else "secondary"):
                            st.session_state["step_sel"] = tag
                            st.rerun()

        with col_img:
            step_sel = st.session_state["step_sel"]

            if play:
                img_ph = st.empty()
                prog_ph = st.empty()
                for i, s in enumerate(steps):
                    data = load_image(region_key, s)
                    if data:
                        img_ph.image(data, caption=f"{region_label} — {step_label(s)}",
                                     use_container_width=True)
                    prog_ph.progress((i + 1) / len(steps),
                                     text=f"第 {i + 1}/{len(steps)} 帧 · {step_label(s)}")
                    time.sleep(PLAY_SPEED)
                prog_ph.empty()
            else:
                data = load_image(region_key, step_sel)
                if data:
                    st.image(data, caption=f"{region_label} — {step_label(step_sel)}",
                             use_container_width=True)
                    if st.button("查看原图", key="btn_full"):
                        show_full_image(region_key, step_sel)


if __name__ == "__main__":
    main()