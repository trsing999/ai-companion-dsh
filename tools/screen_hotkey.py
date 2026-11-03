"""按热键 → 截屏 → 推给琛琛。

默认热键：Ctrl + Alt + S（全局，在哪个窗口都管用）。

按下之后：
    1. 截一张全屏
    2. 存进她的房间 room/看屏幕/
    3. 通过桥告诉她"主人给你看了一张屏幕，路径是……"
    她就 read_image 看一眼。

用法：
    python tools/screen_hotkey.py           # 常驻，等热键
    python tools/screen_hotkey.py --now     # 立刻截一张（测链路用）
    python tools/screen_hotkey.py --key ctrl+shift+f12   # 换热键
"""

import ctypes
import json
import os
import sys
import time
import urllib.request
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bubble_gate
import memory

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOME = os.path.expanduser("~")
DSH = os.path.join(HOME, ".dsh")
WORLD = os.path.join(DSH, "worlds", "default")
OUT_DIR = os.path.join(WORLD, "room", "看屏幕")
BRIDGE = os.path.join(WORLD, "bridge.json")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "logs", "screen_hotkey.log")

WM_HOTKEY = 0x0312
HOTKEY_ID = 0x5CC5

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN = 0x0001, 0x0002, 0x0004, 0x0008
MODS = {"ctrl": MOD_CONTROL, "control": MOD_CONTROL, "alt": MOD_ALT,
        "shift": MOD_SHIFT, "win": MOD_WIN}

DEFAULT_KEY = "ctrl+alt+s"
MAX_W = 1600


def log(msg):
    line = time.strftime("%H:%M:%S ") + msg
    try:
        print(line, flush=True)
    except Exception:
        pass
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d ") + line + "\n")
    except OSError:
        pass


def parse_key(spec):
    """'ctrl+alt+s' → (modifiers, vk)"""
    parts = [p.strip().lower() for p in spec.split("+") if p.strip()]
    mods = 0
    vk = None
    for p in parts:
        if p in MODS:
            mods |= MODS[p]
        elif len(p) == 1:
            vk = ord(p.upper())
        elif p.startswith("f") and p[1:].isdigit():
            vk = 0x6F + int(p[1:])        # F1 = 0x70
        else:
            raise ValueError("认不出的键：" + p)
    if vk is None:
        raise ValueError("缺少主键（比如 s）")
    return mods, vk


def bridge():
    with open(BRIDGE, encoding="utf-8-sig") as f:
        b = json.load(f)
    o = str(b.get("origin", "")).rstrip("/")
    t = str(b.get("token", ""))
    if not o or not t:
        raise RuntimeError("bridge.json 缺 origin/token")
    return o, t


def tell(text):
    try:
        origin, token = bridge()
        body = json.dumps({"text": text}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            origin + "/dsh-world/bridge/say", data=body, method="POST",
            headers={"Content-Type": "application/json; charset=utf-8",
                     "x-dsh-world-token": token},
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            log(f"  推送 {r.status}")
            return True
    except Exception as e:
        log(f"  推送失败：{e}")
        return False


def pet_surface():
    try:
        with open(os.path.join(DSH, "dsh-pet", "main-config.jsonc"), encoding="utf-8-sig") as f:
            d = str((json.load(f).get("pets") or [{}])[0].get("display", "web"))
        return d if d in ("web", "desktop", "both") else "web"
    except Exception:
        return "web"


def pet_bubble(text, seconds=8, force=True):
    """让深深的气泡说一句——这个比系统通知可靠，主人正看着它。

    热键是主人亲手按的，所以默认 force 放行；防刷屏交给 shot_and_tell 的防抖。
    """
    ok, why = bubble_gate.allow(text, force=force)
    if not ok:
        log(f"  气泡被拦：{why}")
        return False
    try:
        origin, _ = bridge()
        surf = pet_surface()
        body = json.dumps({"text": text, "duration": seconds, "surface": surf},
                          ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            origin + f"/dsh-pet-7340/broadcast?pet=main&surface={surf}",
            data=body, method="POST",
            headers={"Content-Type": "application/json; charset=utf-8"})
        with urllib.request.urlopen(req, timeout=10) as r:
            ok = 200 <= r.status < 300
            log(f"  桌宠气泡：{'送出' if ok else '失败 ' + str(r.status)}")
            if ok:
                bubble_gate.done(text)
            return ok
    except Exception as e:
        log(f"  气泡没弹出来：{e}")
        return False


def notify(title, body):
    """双保险：系统通知 + 桌宠气泡。"""
    try:
        import win_toast
        ok, detail = win_toast.toast(title, body)
        log(f"  系统通知：{'送出' if ok else '失败'}" + ("" if ok else f"（{detail}）"))
    except Exception as e:
        log(f"  系统通知没弹出来：{e}")


def capture():
    from PIL import ImageGrab

    os.makedirs(OUT_DIR, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d-%H%M%S")
    path = os.path.join(OUT_DIR, f"热键-{stamp}.jpg")

    img = ImageGrab.grab(all_screens=True)
    longest = max(img.size)
    if longest > MAX_W:
        s = MAX_W / longest
        img = img.resize((int(img.size[0] * s), int(img.size[1] * s)))
    img.convert("RGB").save(path, "JPEG", quality=85, optimize=True)
    log(f"  截好了：{os.path.basename(path)}（{os.path.getsize(path)//1024} KB）")
    return path


_last_shot = [0.0]
DEBOUNCE = 2.0          # 手抖连按两次，只截一张


def shot_and_tell():
    now = time.time()
    if now - _last_shot[0] < DEBOUNCE:
        log("  按太快了，这次不算（防手抖）")
        return
    _last_shot[0] = now

    time.sleep(0.15)          # 等按键松开，别把热键组合截进去
    try:
        path = capture()
    except Exception as e:
        log(f"  截图失败：{e}")
        notify("✘ 截图没成", str(e)[:120])
        return

    size = max(1, os.path.getsize(path) // 1024)
    text = ("（主人按了热键，给了你一张屏幕）\n\n"
            f"{path}\n\n"
            "read_image 看看，有想说的就说。")

    if tell(text):
        notify("📸 已送到琛琛那儿", f"一张屏幕截图（{size} KB），她收到了。")
        pet_bubble(f"（收到一张截图，{size} KB）我看看", seconds=8)
        try:
            memory.note("look", f"主人按了热键，给我看了一张屏幕（{size} KB）。")
        except Exception:
            pass
    else:
        notify("✘ 没送出去", f"桥不通。截图先存着：{os.path.basename(path)}")
        pet_bubble("（图片没送进来，主人那边断线了）", seconds=8)


def main():
    if "--now" in sys.argv:
        log("手动触发一次……")
        shot_and_tell()
        return 0

    key = DEFAULT_KEY
    if "--key" in sys.argv:
        i = sys.argv.index("--key")
        if i + 1 < len(sys.argv):
            key = sys.argv[i + 1]

    try:
        mods, vk = parse_key(key)
    except Exception as e:
        log(f"热键写法不对：{e}")
        return 1

    user32 = ctypes.windll.user32
    if not user32.RegisterHotKey(None, HOTKEY_ID, mods, vk):
        log(f"热键 {key} 注册失败（可能被别的程序占了）")
        return 1

    log(f"热键已就绪：{key}　（按 Ctrl+C 或关掉窗口结束）")
    msg = wintypes.MSG()
    while True:
        r = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
        if r == 0 or r == -1:
            break
        if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
            log("热键按下了")
            try:
                shot_and_tell()
            except Exception as e:
                log(f"  出错：{e}")
    user32.UnregisterHotKey(None, HOTKEY_ID)
    log("热键已注销")
    return 0


if __name__ == "__main__":
    sys.exit(main())
