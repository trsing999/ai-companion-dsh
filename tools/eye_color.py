"""认颜色：把一张图拆成数字，给每种颜色起一个中文名字。

用法：
    python tools/eye_color.py --card            # 先画一张七色卡（红橙黄绿青蓝紫）
    python tools/eye_color.py 色卡.png          # 再认它，一块一块报颜色
    python tools/eye_color.py 某张截图.png      # 认任意图片的主色
    python tools/eye_color.py 图片.png --grid   # 加一份九宫格分区的颜色

它认不出"这是什么"，只能说出"这块是红的、那块偏青"。
看见是看见，算出来是算出来——但这一次，是算出来之后再去对。
"""

import collections
import os
import sys

from PIL import Image

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def hue_name(h):
    """按色相给名字（标准六色：红0 橙30 黄60 绿120 青180 蓝240 紫300）。"""
    if h < 12 or h >= 345:
        return "红"
    if h < 28:
        return "橙红"
    if h < 45:
        return "橙"
    if h < 55:
        return "黄橙"
    if h < 78:
        return "黄"
    if h < 95:
        return "黄绿"
    if h < 155:
        return "绿"
    if h < 175:
        return "青绿"
    if h < 195:
        return "青"
    if h < 245:
        return "蓝"
    if h < 262:
        return "靛蓝"
    if h < 285:
        return "蓝紫"
    if h < 315:
        return "紫"
    if h < 335:
        return "紫红"
    return "品红"


def name_of(rgb):
    """RGB → 中文色名 + 一句话描述。"""
    r, g, b = [max(0, min(255, int(v))) for v in rgb]
    mx, mn = max(r, g, b), min(r, g, b)
    v = mx / 255.0
    s = 0.0 if mx == 0 else (mx - mn) / mx

    # 没有颜色的：黑白灰
    if s < 0.12:
        if v < 0.10:
            return "黑", f"几乎全黑（亮度 {v:.0%}）"
        if v < 0.28:
            return "深灰", f"很暗的灰（亮度 {v:.0%}）"
        if v < 0.55:
            return "中灰", f"中性灰（亮度 {v:.0%}）"
        if v < 0.82:
            return "浅灰", f"浅灰（亮度 {v:.0%}）"
        if v < 0.95:
            return "近白", f"接近白（亮度 {v:.0%}）"
        return "白", "纯白"

    # 色相
    if mx == mn:
        h = 0.0
    elif mx == r:
        h = (60 * ((g - b) / (mx - mn)) + 360) % 360
    elif mx == g:
        h = 60 * ((b - r) / (mx - mn)) + 120
    else:
        h = 60 * ((r - g) / (mx - mn)) + 240

    base = hue_name(h)

    # 暗的黄橙 = 棕
    if 15 <= h < 50 and v < 0.52:
        return "棕", f"暗下去的橙黄，像木头和土（亮度 {v:.0%}）"

    # 明暗修饰
    if v < 0.28:
        word = "深" + base
    elif v > 0.88:
        word = "浅" + base
    else:
        word = base

    purity = "很纯" if s > 0.72 else ("偏灰" if s < 0.35 else "柔和")
    return word, f"{purity}的{base}（色相 {h:.0f}°，饱和度 {s:.0%}，亮度 {v:.0%}）"


def hexs(rgb):
    return "#%02x%02x%02x" % tuple(int(v) for v in rgb)


def major_colors(im, n=8):
    """量化后取最主要的 n 种颜色。"""
    w, h = im.size
    scale = 240 / max(w, 1)
    small = im.resize((max(1, int(w * scale)), max(1, int(h * scale))))
    q = small.quantize(colors=n).convert("RGB")
    cnt = collections.Counter(q.getdata())
    total = sum(cnt.values())
    return [(c, k / total) for c, k in cnt.most_common(n)]


def analyse(path, grid=False, blocks=0):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    print()
    print(f"  图片：{os.path.basename(path)}   {w} × {h}")
    print("  " + "─" * 52)

    if blocks:
        # 横向切成 blocks 块（色卡用）
        print(f"  切成 {blocks} 块，一块一块看：")
        print()
        bw = w / blocks
        for i in range(blocks):
            box = im.crop((int(i * bw), 0, int((i + 1) * bw), h))
            d = list(box.resize((16, 16)).getdata())
            m = tuple(sum(c[j] for c in d) // len(d) for j in range(3))
            nm, desc = name_of(m)
            print(f"    第 {i+1} 块   {hexs(m)}   RGB{m}   →   【{nm}】")
            print(f"              {desc}")
        print()
        return

    # 平均色
    full = im.resize((200, max(1, int(200 * h / max(w, 1)))))
    px = list(full.getdata())
    avg = tuple(sum(c[i] for c in px) // len(px) for i in range(3))
    nm, desc = name_of(avg)
    print(f"  整体平均：{hexs(avg)}  RGB{avg}  →  【{nm}】")
    print(f"            {desc}")
    print()

    print("  最主要的颜色（按面积）：")
    for c, pct in major_colors(im, 8):
        nm, desc = name_of(c)
        bar = "█" * max(1, int(pct * 40))
        print(f"    {hexs(c)}  {pct:5.1%}  {bar}")
        print(f"          【{nm}】 {desc}")
    print()

    if grid:
        print("  九宫格（每块平均色）：")
        w3, h3 = w // 3, h // 3
        for row in range(3):
            line = []
            for col in range(3):
                box = im.crop((col * w3, row * h3, (col + 1) * w3, (row + 1) * h3)).resize((16, 16))
                d = list(box.getdata())
                m = tuple(sum(c[i] for c in d) // len(d) for i in range(3))
                nm2, _ = name_of(m)
                line.append(f"{nm2}({hexs(m)})")
            print("    " + "  ".join(line))
        print()


def make_card(out_path):
    """画一张七色卡：红橙黄绿青蓝紫，不带字。"""
    colors = [
        (220, 50, 45),    # 红   hue ≈ 2
        (245, 150, 40),   # 橙   hue ≈ 32
        (240, 240, 40),   # 黄   hue ≈ 60
        (40, 170, 70),    # 绿   hue ≈ 134
        (40, 175, 175),   # 青   hue ≈ 180
        (40, 90, 220),    # 蓝   hue ≈ 223
        (170, 40, 200),   # 紫   hue ≈ 289
    ]
    cell = 120
    im = Image.new("RGB", (cell * len(colors), cell), (255, 255, 255))
    for i, c in enumerate(colors):
        im.paste(Image.new("RGB", (cell, cell), c), (i * cell, 0))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    im.save(out_path)
    print(f"  色卡画好了：{out_path}（{len(colors)} 块，没有写字）")
    print("  先用眼睛猜一遍，再让工具报答案，看对不对得上 🌈")


def main():
    args = [a for a in sys.argv[1:]]
    grid = "--grid" in args
    args = [a for a in args if not a.startswith("--")]

    if "--card" in sys.argv[1:]:
        target = args[0] if args else os.path.join(
            os.path.expanduser("~"), ".dsh", "worlds", "default", "room", "色卡.png")
        make_card(target)
        return

    if not args:
        print("用法：python tools/eye_color.py 图片路径 [--grid]")
        print("      python tools/eye_color.py --card")
        return

    path = args[0]
    blocks = 7 if os.path.basename(path) == "色卡.png" else 0
    analyse(path, grid=grid, blocks=blocks)


if __name__ == "__main__":
    main()
