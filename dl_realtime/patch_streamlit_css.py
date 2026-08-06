"""ARFS UI 补丁 — 已废弃, 仅保留 --undo 卸载功能 (清理完即可删除本文件).

背景 (2026-08-06): 曾尝试给 streamlit 包 index.html 注入 CSS 放大按键字号
+ JS 无刷新切换 (V1~V4). 结论:
  1) CSS 注入不生效 — Streamlit 1.60 样式全在 JS bundle, <style> 竞争不过;
  2) JS pushState + popstate 前端不响应 — 点击后 URL 变但内容不变.
最终方案: 按键全部用内联样式 HTML 链接 + st.query_params, 整页导航切换
(点击 → 当前页刷新加载新内容), 无需任何补丁.

用法 (服务器清理残留补丁, 跑完删除本文件):
    python patch_streamlit_css.py --undo
"""
import glob
import os
import sys

import streamlit

MARK_V1 = "ARFS-UI-PATCH-V1"
MARK_V2 = "ARFS-UI-PATCH-V2"
MARK_V3 = "ARFS-UI-PATCH-V3"
MARK_V4 = "ARFS-UI-PATCH-V4"


def _strip_block(text, mark):
    """移除标记所在块 (到 </style> 或 </script> 结束, 含闭合标签)."""
    while True:
        start = text.find(f"/* {mark} */")
        if start == -1:
            return text
        end = text.find("</style>", start)
        if end == -1:
            end = text.find("</script>", start)
            tail = "</script>"
        else:
            tail = "</style>"
        if end == -1:  # 无闭合标签的残留: 删到行尾
            end = text.find("\n", start)
            if end == -1:
                return text[:start]
            text = text[:start] + text[end:]
            continue
        text = text[:start] + text[end + len(tail):]


def _undo_html(html):
    with open(html, encoding="utf-8", errors="replace") as f:
        text = f.read()
    orig = text
    for m in (MARK_V1, MARK_V2, MARK_V3, MARK_V4):
        text = _strip_block(text, m)
    if text != orig:
        with open(html, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"[undo] 已移除 ARFS-UI-PATCH 补丁 → {html}")
    else:
        print(f"[undo] index.html 无补丁, 无需清理: {html}")


def _undo_css(css):
    """main.css 的补丁规则是 append 到文件尾的, 从首个标记行起全删."""
    with open(css, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    marks = tuple(f"/* {m} */" for m in (MARK_V1, MARK_V2, MARK_V3, MARK_V4))
    keep, hit = [], False
    for ln in lines:
        if any(m in ln for m in marks):
            hit = True
            continue
        if not hit:
            keep.append(ln)
    with open(css, "w", encoding="utf-8") as f:
        f.writelines(keep)
    print(f"[undo] 已清理 CSS 补丁规则 → {css}")


def main():
    base = os.path.dirname(streamlit.__file__)
    print(f"[patch] streamlit {streamlit.__version__} @ {base}")
    if "--undo" not in sys.argv:
        print("[patch] 本补丁已废弃: CSS 注入不生效、JS popstate 前端不响应,")
        print("        已改用 HTML 链接整页导航, 无需补丁。")
        print("        清理残留请运行: python patch_streamlit_css.py --undo")
        return 0
    html = os.path.join(base, "static", "index.html")
    if os.path.exists(html):
        _undo_html(html)
    css_dir = os.path.join(base, "static", "static", "css")
    for css in sorted(glob.glob(os.path.join(css_dir, "main.*.css"))):
        _undo_css(css)
    print("[undo] 完成. 本文件已无用, 可删除 (git rm).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
