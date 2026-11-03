"""陪她看一集动漫：定时截屏，攒成一列图，她自己一张张 read_image。

不用抓视频文件、不用 ffmpeg——画面就在屏幕上，截下来就是了。

用法：
    python tools/watch_anime.py                    # 默认 10 分钟，每 20 秒一张
    python tools/watch_anime.py --minutes 24       # 一集 24 分钟
    python tools/watch_anime.py --every 10         # 每 10 秒一张（更连贯，图更多）
    python tools/watch_anime.py --stop-at "动漫共和国"   # 只在那个窗口在前台时才截

产物：
    room/看动漫/2026-11-03-1230/
        12-30-00.png
        12-30-20.png
        ...
        清单.md          ← 按顺序列好，直接读这个再一张张看图

她怎么看：
    读 清单.md 知道有哪几张，然后 read_image 一张一张看。
"""

import ctypes
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WORLD = os.path.join(os.path.expanduser("~"), ".dsh", "worlds", "default")
BASE = os.path.join(WORLD, "room", "看动漫")


def log(msg):
    print(time.strftime("%H:%M:%S ") + msg, flush=True)


def active_title():
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        n = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        return buf.value.strip()
    except Exception:
        return ""


def arg(name, default):
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def main():
    minutes = float(arg("--minutes", 10))
    every = float(arg("--every", 20))
    stop_at = arg("--stop-at", "")

    # 按"这一集内容多少分钟"来算，自动换算倍速
    episode = float(arg("--episode", 0))
    speed = float(arg("--speed", 1)) or 1.0
    if episode:
        minutes = episode / speed
        every = every / speed

    from PIL import ImageGrab

    session = time.strftime("%Y-%m-%d-%H%M")
    out = os.path.join(BASE, session)
    os.makedirs(out, exist_ok=True)

    total = max(1, int(minutes * 60 / every))
    if episode:
        log(f"一集 {episode:g} 分钟，{speed:g}x 倍速 → 实际录 {minutes:g} 分钟，每 {every:g} 秒一张，预计 {total} 张")
    else:
        log(f"开始陪看：{minutes:g} 分钟，每 {every:g} 秒一张，预计 {total} 张")
    log(f"存到：{out}")

    saved = []
    start = time.time()
    for i in range(total):
        if stop_at:
            title = active_title()
            if stop_at not in title:
                log(f"  跳过（前台是「{title}」）")
                time.sleep(every)
                continue
        try:
            img = ImageGrab.grab(all_screens=True)
        except Exception as e:
            log(f"  截图失败：{e}")
            time.sleep(every)
            continue
        name = time.strftime("%H-%M-%S") + ".jpg"
        path = os.path.join(out, name)
        try:
            # 缩到长边 1600 再存 JPEG，一张两百来 KB，她看也清楚
            longest = max(img.size)
            if longest > 1600:
                s = 1600 / longest
                img = img.resize((int(img.size[0] * s), int(img.size[1] * s)))
            img.convert("RGB").save(path, "JPEG", quality=82, optimize=True)
            saved.append((name, round(time.time() - start, 1), img.size))
            log(f"  [{i+1}/{total}] {name}")
        except OSError as e:
            log(f"  存不下：{e}")
        if i < total - 1:
            time.sleep(every)

    # 写一份清单
    lines = [f"# 这一集的画面（{session}）", "",
             f"- 共 {len(saved)} 张，每 {every:g} 秒一张",
             f"- 目录：`{out}`", "",
             "按顺序看，一张一张 read_image。", ""]
    for n, (name, sec, size) in enumerate(saved, 1):
        lines.append(f"{n}. `{name}`　（第 {sec:g} 秒，{size[0]}×{size[1]}）")
    lines.append("")

    with open(os.path.join(out, "清单.md"), "w", encoding="utf-8-sig") as f:
        f.write("\n".join(lines))

    log(f"完成：{len(saved)} 张")
    return 0


if __name__ == "__main__":
    sys.exit(main())
