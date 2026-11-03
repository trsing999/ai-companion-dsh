"""自动陪看：主人在看动漫的时候，悄悄截一集下来给她。

不推送、不打扰。她什么时候想翻就翻。
一天最多一集（72 张），截够了就停——省钱。

被 inbox_watcher 周期调用 tick()，也可以单独跑：
    python tools/auto_watch.py --test    # 看看现在算不算"在看动漫"
"""

import ctypes
import json
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORLD = os.path.join(os.path.expanduser("~"), ".dsh", "worlds", "default")
BASE = os.path.join(WORLD, "room", "看动漫")
STATE = os.path.join(BASE, ".state.json")

MAX_PER_DAY = 72        # 一集的量，到了就收手
INTERVAL = 10           # 两张之间至少隔这么久（2 倍速一集 12 分钟正好 72 张）
KEYWORDS = ("动漫共和国", "Androws", "sdmnfowa")   # ANDROWS 的窗口标题特征


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


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def find_anime_window():
    """在所有窗口里找动漫那一扇。返回 (hwnd, 标题, 矩形) 或 None。

    不要求它在前台——主人可能一边看一边切来切去。
    只要求它开着、没最小化、尺寸像样。
    """
    user32 = ctypes.windll.user32
    hits = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(hwnd, _):
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
            if user32.IsIconic(hwnd):          # 最小化的不算
                return True
            n = user32.GetWindowTextLengthW(hwnd)
            if n == 0:
                return True
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            title = buf.value.strip()
            if not any(k in title for k in KEYWORDS):
                return True
            r = RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            w, h = r.right - r.left, r.bottom - r.top
            if w < 400 or h < 300:             # 太小的是启动器/托盘，不是主窗口
                return True
            hits.append((hwnd, title, (r.left, r.top, r.right, r.bottom)))
        except Exception:
            pass
        return True

    user32.EnumWindows(cb, 0)
    return hits[0] if hits else None


def load_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(st):
    try:
        os.makedirs(BASE, exist_ok=True)
        tmp = STATE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False)
        os.replace(tmp, STATE)
    except OSError:
        pass


def watching():
    """现在是不是真的在看动漫？返回 (标题, 矩形) 或 (None, None)。

    要求它**就在最前面**——被别的窗口挡着的时候截下来的是遮挡物，
    那不是她想看的东西。
    """
    hit = find_anime_window()
    if not hit:
        return None, None
    try:
        fg = ctypes.windll.user32.GetForegroundWindow()
    except Exception:
        fg = None
    if hit[0] != fg:
        return None, None
    return hit[1], hit[2]


def trim_dark(img, thresh=22):
    """把上下的黑边裁掉——特别是 MateBook 3:2 屏幕放 16:9 动漫留下的那种。

    从最上面和最下面一行一行往里找，碰到第一行「有内容」的就停。
    上下不对称也没关系（有时候底部有进度条/界面）。
    """
    try:
        g = img.convert("L")
        w, h = g.size
        px = g.load()
        step = max(1, w // 100)
        xs = list(range(0, w, step))

        def row_avg(y):
            return sum(px[x, y] for x in xs) / len(xs)

        top = 0
        while top < h - 1 and row_avg(top) <= thresh:
            top += 1
        bottom = 0
        while bottom < h - 1 and row_avg(h - 1 - bottom) <= thresh:
            bottom += 1

        if top + bottom >= h * 0.7:
            return img                    # 整张都黑，别裁
        if top < 4 and bottom < 4:
            return img                    # 本来就没黑边
        if h - top - bottom < 120:
            return img                    # 裁完太小，别裁

        return img.crop((0, top, w, h - bottom))
    except Exception:
        return img


def tick(verbose=False):
    """被周期性调用。截了一张就返回路径，否则 None。"""
    title, box = watching()
    if not title:
        if verbose:
            log(f"没在看动漫（前台是：{active_title() or '空'}）")
        return None

    today = time.strftime("%Y-%m-%d")
    st = load_state()
    if st.get("date") != today:
        st = {"date": today, "count": 0, "lastShot": 0}

    if st.get("count", 0) >= MAX_PER_DAY:
        if verbose:
            log(f"今天的 {MAX_PER_DAY} 张已经够了，不再截（省钱）")
        return None

    now = time.time()
    if now - st.get("lastShot", 0) < INTERVAL:
        return None

    from PIL import ImageGrab
    try:
        img = ImageGrab.grab(bbox=box, all_screens=True)   # 只截那扇窗
    except Exception:
        try:
            img = ImageGrab.grab(all_screens=True)
        except Exception as e:
            log(f"截图失败：{e}")
            return None

    day_dir = os.path.join(BASE, st["date"])
    os.makedirs(day_dir, exist_ok=True)
    name = time.strftime("%H-%M-%S") + ".jpg"
    path = os.path.join(day_dir, name)

    # 裁黑边暂不启用：动漫画面本身偏暗，亮度判断不可靠，有切到内容的风险。
    # 黑边只是多花约 15% 的 token（一集约 0.05 元），不值得冒险。
    # img = trim_dark(img)

    longest = max(img.size)
    if longest > 1600:
        s = 1600 / longest
        img = img.resize((int(img.size[0] * s), int(img.size[1] * s)))
    try:
        img.convert("RGB").save(path, "JPEG", quality=82, optimize=True)
    except OSError as e:
        log(f"存不下：{e}")
        return None

    st["count"] = st.get("count", 0) + 1
    st["lastShot"] = now
    save_state(st)

    log(f"截到第 {st['count']}/{MAX_PER_DAY} 张：{name}（{title}）")
    return path


def summary():
    """今天截了多少张，给她一份清单。"""
    today = time.strftime("%Y-%m-%d")
    day_dir = os.path.join(BASE, today)
    if not os.path.isdir(day_dir):
        return 0
    files = sorted(f for f in os.listdir(day_dir) if f.endswith(".jpg"))
    if not files:
        return 0
    lines = [f"# 今天这一集（{today}）", "",
             f"- 共 {len(files)} 张，每 {INTERVAL} 秒一张",
             f"- 目录：`{day_dir}`", "",
             "按顺序一张一张 read_image。看到不想看的就跳，没人管你。", ""]
    for i, f in enumerate(files, 1):
        lines.append(f"{i}. `{f}`")
    lines.append("")
    try:
        with open(os.path.join(day_dir, "清单.md"), "w", encoding="utf-8-sig") as fh:
            fh.write("\n".join(lines))
    except OSError:
        pass
    return len(files)


if __name__ == "__main__":
    if "--test" in sys.argv:
        title, box = watching()
        if title:
            log(f"算『在看动漫』：{title}")
            log(f"窗口区域：{box}")
        else:
            log("不算在看动漫")
            log(f"当前前台：{active_title() or '（空）'}")
        st = load_state()
        log(f"今天已截：{st.get('count', 0)} / {MAX_PER_DAY}")
        n = summary()
        log(f"今天目录里有 {n} 张")
        sys.exit(0)
    log("这次真截一张：")
    print(tick(verbose=True))
