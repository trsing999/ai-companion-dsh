"""夜里她困了。

23:00 到 7:00 之间，隔一阵让桌宠做个困倦的动作（原地小憩沉眠 / 打哈欠那种）。
不打断她思考，只是让身体跟着时间走。

用法：
    python tools/pet_night.py        # 现在困一下
    python tools/pet_night.py --show # 看现在是白天还是夜里
"""

import json
import os
import sys
import time
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOME = os.path.expanduser("~")
DSH = os.path.join(HOME, ".dsh")
BRIDGE = os.path.join(DSH, "worlds", "default", "bridge.json")
CONFIG = os.path.join(DSH, "dsh-pet", "main-config.jsonc")

# 夜里用的动作（都在 106 个里）
NIGHT_ANIMS = ["原地小憩沉眠", "原地蹲下玩玩具汽车", "东张西望"]


def origin():
    try:
        with open(BRIDGE, encoding="utf-8-sig") as f:
            return str(json.load(f).get("origin", "")).rstrip("/")
    except Exception:
        return os.environ.get("DSH_WEB_URL", "http://127.0.0.1:14077").rstrip("/")


def surface():
    try:
        with open(CONFIG, encoding="utf-8-sig") as f:
            d = str((json.load(f).get("pets") or [{}])[0].get("display", "web"))
        return d if d in ("web", "desktop", "both") else "web"
    except Exception:
        return "web"


def is_night():
    h = time.localtime().tm_hour
    return h >= 23 or h < 7


def nap():
    """让她困一下：做个动作 + 气泡说一句。"""
    surf = surface()
    anim = NIGHT_ANIMS[int(time.strftime("%H")) % len(NIGHT_ANIMS)]
    try:
        body = json.dumps({"name": anim, "surface": surf},
                          ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            origin() + f"/dsh-pet-7340/anim?pet=main&surface={surf}",
            data=body, method="POST",
            headers={"Content-Type": "application/json; charset=utf-8"})
        with urllib.request.urlopen(req, timeout=10) as r:
            ok = 200 <= r.status < 300
        print(f"  {'✔' if ok else '✘'} 困一下：{anim}")
        return ok
    except Exception as e:
        print(f"  ✘ {e}")
        return False


def main():
    if "--show" in sys.argv:
        print("  夜里" if is_night() else "  白天")
        return 0
    if not is_night():
        print("  现在不是夜里，不困")
        return 0
    return 0 if nap() else 1


if __name__ == "__main__":
    sys.exit(main())
