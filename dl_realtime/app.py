"""IVT + AR 预报展示界面 — Streamlit.

功能:
1. 选择时次 (step 0-144h)
2. 选择区域 (global / east_asia / north_china)
3. 播放 25 帧动画

运行: streamlit run app.py --server.port 8501
"""
import os
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
    """加载单张图."""
    path = FIG_ROOT / region_key / f"{step_tag}.png"
    if path.exists():
        return path.read_bytes()
    return None


def main():
    st.set_page_config(page_title="IVT + AR 大气河临近预报", layout="wide")
    st.title("IFS vs AIFS — IVT + AR 大气河临近预报")
    st.caption("数据来源: ECMWF Open Data | 预报时次: 最新起报, step 0-144h")

    col_region, col_step, col_play = st.columns([1, 2, 1])

    with col_region:
        region_label = st.selectbox("选择区域", list(REGIONS.keys()), index=0)
        region_key = REGIONS[region_label]

    steps = list_steps(region_key)
    if not steps:
        st.error(f"没有找到图片: {FIG_ROOT / region_key} — 先运行 dl_realtime.py")
        st.stop()

    with col_step:
        step_sel = st.selectbox("选择时次", steps, index=len(steps) - 1)

    with col_play:
        st.write("")
        st.write("")
        play = st.button("▶ 播放 25 帧", type="primary")

    # 显示区
    if play:
        placeholder = st.empty()
        for s in steps:
            data = load_image(region_key, s)
            if data:
                placeholder.image(data, caption=f"step {s}", use_container_width=True)
                st.session_state["last"] = s
            st.session_state["speed"] = 0.5
    else:
        data = load_image(region_key, step_sel)
        if data:
            st.image(data, caption=f"step {step_sel}", use_container_width=True)


if __name__ == "__main__":
    main()