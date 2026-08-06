"""ARFS UI 补丁: 直接修改 Streamlit 包静态文件, 强制放大按键字号.

背景 (2026-08-06): st.markdown 注入的 <style> 在部分 Streamlit 版本/环境
被过滤或竞争不过 JS 运行时注入的样式 (新版 Streamlit 样式全编进 JS
bundle, 无 main.css 文件) → 网页按键字号一直不变.
本脚本直接改 streamlit 包的静态文件 (浏览器必然加载), 幂等:
  1) 旧版: static/static/css/main.*.css  → 末尾追加规则
  2) 新版: static/index.html            → </head> 前插入 <style>
streamlit 升级后重跑一次即可.

用法: python patch_streamlit_css.py
"""
import glob
import os

import streamlit

MARK = "ARFS-UI-PATCH-V1"
RULES = f"""/* {MARK} */
html {{ font-size: 16px !important; }}
button, [role="tab"], [role="radio"], [data-testid="stTabs"] button,
[data-baseweb="tab"], [data-testid="stSegmentedControl"] button {{
    font-size: 25px !important;
}}
"""


def _patch_css(css):
    with open(css, encoding="utf-8", errors="replace") as f:
        text = f.read()
    if MARK in text:
        print(f"[patch] 已打过补丁, 跳过: {css}")
        return True
    with open(css, "a", encoding="utf-8") as f:
        f.write("\n" + RULES)
    print(f"[patch] 已追加字号规则 → {css}")
    return True


def _patch_index(html):
    with open(html, encoding="utf-8", errors="replace") as f:
        text = f.read()
    if MARK in text:
        print(f"[patch] 已打过补丁, 跳过: {html}")
        return True
    if "</head>" not in text:
        print(f"[patch] index.html 无 </head>, 放弃: {html}")
        return False
    style = f"<style>\n{RULES}\n</style>\n</head>"
    text = text.replace("</head>", style, 1)
    with open(html, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"[patch] 已在 </head> 前插入字号规则 → {html}")
    return True


def main():
    base = os.path.dirname(streamlit.__file__)
    print(f"[patch] streamlit {streamlit.__version__} @ {base}")
    css_dir = os.path.join(base, "static", "static", "css")
    files = sorted(glob.glob(os.path.join(css_dir, "main.*.css")))
    if files and _patch_css(files[0]):
        return 0
    html = os.path.join(base, "static", "index.html")
    if os.path.exists(html) and _patch_index(html):
        return 0
    # 诊断: 打印 static 目录结构, 便于人工定位
    print(f"[patch] 静态目录结构: "
          f"{os.listdir(os.path.join(base, 'static'))}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())