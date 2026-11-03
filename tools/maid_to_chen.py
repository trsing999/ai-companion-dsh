"""摸女仆 → 琛琛有反应（轮询版，比低级钩子稳）。

轮询左键状态与光标位置：在女仆浮窗内按下左键 → 在琛琛身体中心合成一次点击。
"""

import ctypes, glob, json, os, sys, time
from ctypes import wintypes

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

user32 = ctypes.windll.user32
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs", "maid_to_chen.log")
APPDATA = os.environ["APPDATA"]
RUNTIME_GLOB = os.path.join(APPDATA, "dsh-pet-standalone-webm-chat", "pet-runtime-v2-*slot-0.json")
MAID_TITLE = "桌面模式"
COOLDOWN = 1.2


def log(msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def maid_rect():
    found = []

    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        if MAID_TITLE in buf.value:
            r = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            if r.right - r.left > 50 and r.bottom - r.top > 50:
                found.append((r.left, r.top, r.right, r.bottom))
        return True

    user32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(cb), 0)
    return found[0] if found else None


def chen_rect():
    files = glob.glob(RUNTIME_GLOB)
    if not files:
        return None
    try:
        d = json.load(open(max(files, key=os.path.getmtime), encoding="utf-8"))
        return (d["x"], d["y"], d["x"] + d["w"], d["y"] + d["h"])
    except (OSError, ValueError, KeyError):
        return None


def inside(pt, r, margin=4):
    return bool(r) and r[0] + margin <= pt[0] <= r[2] - margin and r[1] + margin <= pt[1] <= r[3] - margin


def cursor():
    p = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return (p.x, p.y)


def click(x, y):
    user32.SetCursorPos(x, y)
    time.sleep(0.02)
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.03)
    user32.mouse_event(0x0004, 0, 0, 0, 0)


def main():
    mr, cr = maid_rect(), chen_rect()
    log(f"start maid={mr} chen={cr}")
    if not mr:
        log("警告：没找到女仆窗口（标题含「桌面模式」）")
    prev_down = False
    last_refresh = 0.0
    last_fire = 0.0
    while True:
        now = time.time()
        if now - last_refresh > 2:
            last_refresh = now
            try:
                mr = maid_rect() or mr
                cr = chen_rect() or cr
            except Exception:
                pass
        down = bool(user32.GetAsyncKeyState(0x01) & 0x8000)
        if down and not prev_down:
            pt = cursor()
            if inside(pt, mr) and not inside(pt, cr) and now - last_fire > COOLDOWN and cr:
                last_fire = now
                cx, cy = (cr[0] + cr[2]) // 2, (cr[1] + cr[3]) // 2
                log(f"maid-touched {pt} -> click chen ({cx},{cy})")
                click(cx, cy)
                time.sleep(0.15)
                down = False
        prev_down = down
        time.sleep(0.03)


if __name__ == "__main__":
    main()
