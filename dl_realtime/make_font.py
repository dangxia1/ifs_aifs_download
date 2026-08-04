"""自动生成子集化中文字体 (Noto Sans CJK SC).

字体不进 git: 运行时从系统 Noto ttc 提取 + 子集化 (GB2312 一级常用字 + ASCII 符号),
约 2MB。目标目录优先级: FONT_DIR 环境变量 > 服务器 /shared_data/zongshen/fonts >
项目内 fonts/ (绿色包/本地 fallback)。

用法: python make_font.py   (幂等, 已存在则跳过)
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FONTS = ROOT / "fonts"

# 目标目录候选 (按优先级)
TARGET_DIRS = [
    os.environ.get("FONT_DIR", ""),
    "/shared_data/zongshen/fonts",   # 服务器数据目录
    str(FONTS),                       # 项目内 (绿色包/本地)
]

# 系统 Noto ttc 候选 (服务器等 Linux 环境)
TTC_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]

# GB2312 一级字库 (3755 常用字) + ASCII + 常用符号
_ASCII_SYMBOLS = (
    "0123456789"
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "%+-=·:()[]{}·/|,.;!?_~^°²³⁻¹<> "
)


def _gb2312_level1():
    """生成 GB2312 一级汉字 (3755 个常用字)."""
    chars = []
    for hi in range(0xB0, 0xD8):
        for lo in range(0xA1, 0xFF):
            try:
                chars.append(bytes([hi, lo]).decode("gb2312"))
            except Exception:
                pass
    return "".join(chars)


def ensure_font():
    """确保子集字体存在 (目标目录优先级: FONT_DIR > 服务器 > 项目内). 返回路径或 None."""
    # 1. 已有则直接返回
    for d in TARGET_DIRS:
        if not d:
            continue
        p = Path(d) / "NotoSansCJKsc-Regular.otf"
        if p.exists():
            return str(p)

    # 2. 找一个可写目标目录
    target_dir = None
    for d in TARGET_DIRS:
        if not d:
            continue
        try:
            Path(d).mkdir(parents=True, exist_ok=True)
            Path(d).write_text("")  # 测试可写
            Path(d, "test").unlink(missing_ok=True)
            target_dir = d
            break
        except Exception:
            continue
    if target_dir is None:
        print("[font] 无可用目录, 回退系统字体")
        return None

    target = Path(target_dir) / "NotoSansCJKsc-Regular.otf"

    for ttc in TTC_CANDIDATES:
        if not os.path.exists(ttc):
            continue
        try:
            from fontTools.ttLib import TTCollection, TTFont
            from fontTools import subset

            # 1. 提取 SC 子字体
            tmp = Path(target_dir) / "_sc_full.otf"
            found = False
            for font in TTCollection(ttc).fonts:
                if font["name"].getDebugName(4) == "Noto Sans CJK SC":
                    font.save(str(tmp))
                    found = True
                    break
            if not found:
                continue

            # 2. 子集化
            text = _gb2312_level1() + _ASCII_SYMBOLS
            opts = subset.Options()
            opts.flavor = None
            s = subset.Subsetter(options=opts)
            s.populate(text=text)
            f = TTFont(str(tmp))
            s.subset(f)
            f.save(str(target))
            tmp.unlink(missing_ok=True)
            print(f"[font] 生成: {target} ({target.stat().st_size / 1024 / 1024:.1f}MB)")
            return str(target)
        except Exception as e:
            print(f"[font] 生成失败: {e}")
            continue
    print("[font] 未找到系统 Noto ttc, 将回退到系统字体")
    return None


if __name__ == "__main__":
    ensure_font()