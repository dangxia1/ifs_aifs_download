"""ARFS UI 补丁: 直接修改 Streamlit 包静态文件, 强制放大按键字号 + 无刷新切换.

背景 (2026-08-06): st.markdown 注入的 <style> 在部分 Streamlit 版本/环境
被过滤或竞争不过 JS 运行时注入的样式 (新版 Streamlit 样式全编进 JS
bundle, 无 main.css 文件) → 网页按键字号一直不变.
方案: app.py 按键改内联样式 HTML 链接 (必然生效); 本脚本给 streamlit
包的 index.html 注入:
  1) CSS 规则 (字号兜底)
  2) JS: 拦截按键链接点击, pushState 更新 URL + 派发 popstate →
     Streamlit 前端感知 URL 变化自动重渲染 → 无刷新切换 (V3, 2026-08-06)
幂等; 旧补丁 (V1/V2) 自动移除; streamlit 升级后重跑一次即可.

用法: python patch_streamlit_css.py
"""
import glob
import os

import streamlit

MARK_V1 = "ARFS-UI-PATCH-V1"
MARK_V2 = "ARFS-UI-PATCH-V2"
MARK = "ARFS-UI-PATCH-V3"
RULES = f"""/* {MARK} */
html {{ font-size: 16px !important; }}
button, [role="button"], [role="tab"], [role="radio"], [role="option"] {{
    font-size: 25px !important;
}}
.stButton button, .stButton > button,
[data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-primary"],
[data-testid="stBaseButton-secondaryFormSubmit"], [data-testid="stBaseButton-primaryFormSubmit"],
[data-testid="stTabs"] button, [data-testid="stTabs"] [role="tab"],
[data-baseweb="tab"], [data-baseweb="button"],
[data-testid="stSegmentedControl"] button, [data-testid="stSegmentedControl"] label,
[data-testid="stRadio"] label, [data-testid="stRadio"] [role="radio"] {{
    font-size: 25px !important;
}}
"""
JS = f"""<script>
/* {MARK}: 按键链接无刷新切换 (pushState + popstate → Streamlit 重渲染)
   注意: pushState/popstate 都携带 state 对象 (Streamlit 校验 history.state,
   state=null 时认为 URL 无变化) */
document.addEventListener('click', function (e) {{
  var a = e.target && e.target.closest ? e.target.closest('a[href^="?"]') : null;
  if (!a) return;
  e.preventDefault();
  var href = a.getAttribute('href');
  if (history.pushState) {{
    history.pushState({{arfsNav: href}}, '', href);
    try {{
      window.dispatchEvent(new PopStateEvent('popstate', {{state: {{arfsNav: href}}}}));
    }} catch (err) {{
      window.dispatchEvent(new PopStateEvent('popstate'));
    }}
  }} else {{
    window.location.href = href;
  }}
}});
</script>
"""


def _strip_old(text):
    """移除旧 V1/V2 补丁 (规则/style 块)."""
    for m in (MARK_V1, MARK_V2):
        start = text.find(f"/* {m} */")
        if start == -1:
            continue
        end = text.find("</style>", start)
        if end != -1:
            text = text[:start] + text[end + len("</style>"):]
        else:  # 无 </style> 的残留注释, 删注释行
            end = text.find("\n", start)
            text = text[:start] + text[end:]
    return text


def _patch_css(css):
    with open(css, encoding="utf-8", errors="replace") as f:
        text = f.read()
    text = _strip_old(text)
    if MARK in text:
        print(f"[patch] 已打过 V3 补丁, 跳过: {css}")
        return True
    with open(css, "a", encoding="utf-8") as f:
        f.write("\n" + RULES)
    print(f"[patch] 已追加 V3 字号规则 → {css}")
    return True


def _patch_index(html):
    with open(html, encoding="utf-8", errors="replace") as f:
        text = f.read()
    text = _strip_old(text)
    if MARK in text:
        print(f"[patch] 已打过 V3 补丁, 跳过: {html}")
        return True
    if "</head>" not in text:
        print(f"[patch] index.html 无 </head>, 放弃: {html}")
        return False
    inject = f"<style>\n{RULES}\n</style>\n{JS}</head>"
    text = text.replace("</head>", inject, 1)
    with open(html, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"[patch] 已在 </head> 前插入 V3 (CSS+JS) → {html}")
    return True


def main():
    base = os.path.dirname(streamlit.__file__)
    print(f"[patch] streamlit {streamlit.__version__} @ {base}")
    css_dir = os.path.join(base, "static", "static", "css")
    files = sorted(glob.glob(os.path.join(css_dir, "main.*.css")))
    if files:
        _patch_css(files[0])
    html = os.path.join(base, "static", "index.html")
    if os.path.exists(html) and _patch_index(html):
        return 0
    print(f"[patch] 静态目录结构: "
          f"{os.listdir(os.path.join(base, 'static'))}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
