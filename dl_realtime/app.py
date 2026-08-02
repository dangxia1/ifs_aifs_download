"""IVT + AR 预报展示界面 — Streamlit (Operate 模式).

功能:
1. 区域切换 (图片上方, 点击直接切换)
2. 时次 step 选择 (右侧一列, 点击直接切换)
3. 播放动画 + 进度条
4. 白天/夜间视觉模式 (左上)
5. 图片清晰展示, 可点击放大 (新标签页打开原图)

运行: streamlit run app.py --server.port 8501
"""
import base64
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


def img_clickable_html(data):
    """可点击放大: 新标签页打开 base64 原图."""
    b64 = base64.b64encode(data).decode()
    return (f'<a href="data:image/png;base64,{b64}" target="_blank" '
            f'style="font-size:13px;">查看原图（新标签页）</a>')


def theme_css(dark):
    """白天/夜间视觉模式."""
    if dark:
        return """
        <style>
        .stApp { background-color: #0e1117; color: #fafafa; }
        .stApp header { background-color: #0e1117; }
        [data-testid="stCaptionContainer"] { color: #bbb !important; }
        .stRadio label, .stSegmentedControl label { color: #ddd !important; }
        </style>
        """
    return """
    <style>
    .stApp { background-color: #ffffff; color: #111111; }
    .stApp header { background-color: #ffffff; }
    </style>
    """


def main():
    st.set_page_config(page_title="IVT + AR 大气河临近预报", layout="wide")

    # ── 左上: 视觉模式切换 ──
    col_theme, col_info = st.columns([1, 5])
    with col_theme:
        dark = st.toggle("夜间模式", value=True)
    with col_info:
        st.caption("数据来源: ECMWF Open Data | 预报时次: 最新起报, step 0-144h | IFS vs AIFS")
    st.markdown(theme_css(dark), unsafe_allow_html=True)

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

    # ── 布局: 左图 右 step ──
    col_img, col_side = st.columns([3, 1])

    with col_side:
        st.markdown("**时次 (step)**")
        step_sel = st.radio(
            "选择时次", steps, index=len(steps) - 1,
            label_visibility="collapsed",
        )
        play = st.button("播放动画", type="primary", use_container_width=True)

    with col_img:
        if play:
            # 播放全部帧 + 进度条
            img_ph = st.empty()
            prog_ph = st.empty()
            for i, s in enumerate(steps):
                data = load_image(region_key, s)
                if data:
                    img_ph.image(data, caption=f"{region_label} — {s}",
                                 use_container_width=True)
                prog_ph.progress((i + 1) / len(steps),
                                 text=f"播放中: {s} / {len(steps)}")
                time.sleep(PLAY_SPEED)
            prog_ph.empty()
        else:
            data = load_image(region_key, step_sel)
            if data:
                st.image(data, caption=f"{region_label} — {step_sel}",
                         use_container_width=True)
                st.markdown(img_clickable_html(data), unsafe_allow_html=True)


if __name__ == "__main__":
    main()