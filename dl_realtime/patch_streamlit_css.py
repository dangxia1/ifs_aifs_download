"""ARFS UI 补丁: 直接修改 Streamlit 包静态 CSS, 强制放大按键字号.

背景 (2026-08-06): st.markdown 注入的 <style> 在部分 Streamlit 版本/
环境被过滤, 字号 CSS 选择器从未生效 → 网页按键字号一直不变.
本脚本直接往 streamlit 包的 main.css 末尾追加规则 (浏览器加载的就是
这个文件, 必然生效). 幂等: 已打过补丁则跳过. streamlit 升级后重跑一次即可.

用法: python patch_streamlit_css.py
"""
import glob
import os

import streamlit

MARK = "/* ARFS UI patch: 按键字号强制放大 (2026-08-06) */"
RULES = f"""
{MARK}
html {{ font-size: 16px !important; }}
button, [role="tab"], [role="radio"], [data-testid="stTabs"] button,
[data-baseweb="tab"], [data-testid="stSegmentedControl"] button {{
    font-size: 25px !important;
}}
"""


def main():
    css_dir = os.path.join(os.path.dirname(streamlit.__file__),
                           "static", "static", "css")
    files = sorted(glob.glob(os.path.join(css_dir, "main.*.css")))
    if not files:
        print(f"[patch] 未找到 Streamlit CSS: {css_dir}")
        return 1
    css = files[0]
    with open(css, encoding="utf-8", errors="replace") as f:
        text = f.read()
    if MARK in text:
        print(f"[patch] 已打过补丁, 跳过: {css}")
        return 0
    with open(css, "a", encoding="utf-8") as f:
        f.write(RULES)
    print(f"[patch] 已追加字号规则 → {css}")
    print("[patch] 请重启 streamlit + 浏览器 Ctrl+F5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
