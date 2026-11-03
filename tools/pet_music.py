"""她能听歌，也能切歌——但切之前得问你一声。

B（自己读歌）：
    python tools/pet_music.py now                    # 现在在放什么
    python tools/pet_music.py search "囹圄 姜没"      # 搜歌 + 拿歌词（不登录，公开接口）

C（切歌，要先批准）：
    python tools/pet_music.py next                   # 想切下一首
    python tools/pet_music.py pause                  # 想暂停
    python tools/pet_music.py approve                # 【主人用】同意一次，10 分钟内有效

规矩：
    没批准的时候调 next/pause，只会弹一句"我想切首歌，可以吗？"，
    不会真的动。主人点了「同意切歌」之后，10 分钟内她都切得动。
"""

import ctypes
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bubble_gate

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOME = os.path.expanduser("~")
DSH = os.path.join(HOME, ".dsh")
BRIDGE = os.path.join(DSH, "worlds", "default", "bridge.json")
CONFIG = os.path.join(DSH, "dsh-pet", "main-config.jsonc")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPROVAL = os.path.join(ROOT, "logs", "music_approval.json")
LOG = os.path.join(ROOT, "logs", "pet_music.log")

APPROVE_MINUTES = 10
PET_ID = "main"

# Windows 媒体键
VK = {
    "play": 0xB3,
    "next": 0xB0,
    "prev": 0xB1,
    "mute": 0xAD,
}

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


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


def key(vk):
    """发一个媒体键（按下 + 松开）。"""
    user32 = ctypes.windll.user32
    user32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.06)
    user32.keybd_event(vk, 0, 2, 0)      # KEYEVENTF_KEYUP


def load_approval():
    try:
        with open(APPROVAL, encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return {}


def approved():
    a = load_approval()
    until = a.get("until", 0)
    return time.time() < until


def approve():
    os.makedirs(os.path.dirname(APPROVAL), exist_ok=True)
    until = time.time() + APPROVE_MINUTES * 60
    with open(APPROVAL, "w", encoding="utf-8") as f:
        json.dump({"until": until,
                   "at": time.strftime("%Y-%m-%d %H:%M:%S")}, f, ensure_ascii=False)
    end = time.strftime("%H:%M", time.localtime(until))
    print(f"  好了，{APPROVE_MINUTES} 分钟内（到 {end}）她可以切歌")
    bubble(f"（主人点头了，{APPROVE_MINUTES} 分钟内我能切歌）")
    return 0


def bubble(text, seconds=8, force=True):
    """主人点头/她请求切歌这类，都是稀发事件，force 放行；
    但如果真被限流了也如实说。"""
    ok, why = bubble_gate.allow(text, force=force)
    if not ok:
        log(f"  气泡被拦：{why}")
        return False
    try:
        with open(BRIDGE, encoding="utf-8-sig") as f:
            origin = str(json.load(f).get("origin", "")).rstrip("/")
        surf = "web"
        try:
            with open(CONFIG, encoding="utf-8-sig") as f:
                d = str((json.load(f).get("pets") or [{}])[0].get("display", "web"))
            surf = d if d in ("web", "desktop", "both") else "web"
        except Exception:
            pass
        body = json.dumps({"text": text, "duration": seconds, "surface": surf},
                          ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            origin + f"/dsh-pet-7340/broadcast?pet={PET_ID}&surface={surf}",
            data=body, method="POST",
            headers={"Content-Type": "application/json; charset=utf-8"})
        urllib.request.urlopen(req, timeout=10).read()
        bubble_gate.done(text)
        return True
    except Exception:
        return False


def ask_permission(what):
    """没批准时：弹一句问主人，不乱动。"""
    msg = {"next": "我想切下一首，可以吗？", "pause": "我想暂停一下，可以吗？",
           "prev": "我想回上一首，可以吗？", "play": "我想播放，可以吗？"}.get(what, "我想动一下音乐")
    bubble(f"（{msg}）", seconds=12)
    log(f"  请求「{what}」——等主人同意（这次没动）")
    print(f"  没批准。已经在气泡里问主人了：「{msg}」")
    print("  （主人双击桌面「同意切歌」之后，10 分钟内有效）")
    return 1


def do(what):
    if what not in VK:
        print("  只会 play / pause / next / prev")
        return 1
    if not approved():
        return ask_permission(what)
    key(VK[what])
    log(f"  执行「{what}」")
    print(f"  ✔ 已发出媒体键：{what}")
    return 0


def now():
    import now_playing
    entry = now_playing.current()
    if not entry:
        print("  现在没在放歌")
        return 0
    app, singer, song = entry
    print(f"  在放：{song} - {singer}（{app}）")
    return 0


def search(q):
    import now_playing
    parts = q.split()
    song = parts[0] if parts else q
    singer = " ".join(parts[1:])
    sid = now_playing.find_song(song, singer)
    if not sid:
        print("  没搜到这首歌")
        return 1
    lines = now_playing.lyric_of(sid)
    print(f"  找到：{song} {singer}".strip())
    for ln in lines:
        print("   ", ln)
    return 0


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    cmd = args[0].lower()
    if cmd == "approve":
        return approve()
    if cmd == "now":
        return now()
    if cmd == "search":
        return search(" ".join(args[1:]))
    if cmd in VK:
        return do(cmd)
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
