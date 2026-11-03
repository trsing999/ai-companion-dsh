"""让她动起来：给桌宠点播动作、往气泡里说话。

用法：
    python tools/pet_control.py list                 # 看有哪些动作
    python tools/pet_control.py play 写代码          # 让她做一个动作
    python tools/pet_control.py say "我困了"          # 让她气泡里冒一句话
    python tools/pet_control.py both 原地小憩沉眠 "好困"

动作名就是素材文件名，九十多个，都是中文。
"""

import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bubble_gate

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOME = os.path.expanduser("~")
DSH = os.path.join(HOME, ".dsh")
BRIDGE = os.path.join(DSH, "worlds", "default", "bridge.json")
WEBM = os.path.join(DSH, "profiles", "desktop", "node_modules",
                    "dsh-pet", "assets", "webm")

PET_ID = "main"          # 插件版那只叫 main（深深）
CONFIG = os.path.join(DSH, "dsh-pet", "main-config.jsonc")


def surface_from_config():
    """跟着配置走：display 是 web / desktop / both，就对准哪个 surface。

    这样不管主人怎么调，她都不会撞上"不满足 surface"的报错。
    """
    try:
        with open(CONFIG, encoding="utf-8-sig") as f:
            j = json.load(f)
        d = str((j.get("pets") or [{}])[0].get("display", "web"))
        return d if d in ("web", "desktop", "both") else "web"
    except Exception:
        return "web"


SURFACE = "web"          # 真跑的时候用 surface_from_config()


def origin():
    try:
        with open(BRIDGE, encoding="utf-8-sig") as f:
            o = str(json.load(f).get("origin", "")).rstrip("/")
        if o:
            return o
    except Exception:
        pass
    return os.environ.get("DSH_WEB_URL", "http://127.0.0.1:14077").rstrip("/")


def post(path, payload):
    url = origin() + path
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read().decode("utf-8", "replace") or "{}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"raw": body}
    except Exception as e:
        return 0, {"error": str(e)}


def animations():
    if not os.path.isdir(WEBM):
        return []
    return sorted(
        os.path.splitext(f)[0] for f in os.listdir(WEBM) if f.endswith(".webm")
    )


def play(name, pet=PET_ID, surface=None):
    surface = surface or surface_from_config()
    status, res = post(
        f"/dsh-pet-7340/anim?pet={pet}&surface={surface}",
        {"name": name, "surface": surface},
    )
    ok = res.get("ok")
    if ok:
        print(f"✔ 她做了「{name}」")
    else:
        print(f"✘ {res.get('message') or res}")
        near = [a for a in animations() if name in a or a in name]
        if near:
            print("  是不是想找：" + "、".join(near[:6]))
    return bool(ok)


def say(text, pet=PET_ID, seconds=10, surface=None, force=False):
    """说话前先过限流：一分钟最多两句，同一句不重复刷。"""
    ok, why = bubble_gate.allow(text, force=force)
    if not ok:
        print(f"✘ 气泡被拦：{why}")
        return False

    surface = surface or surface_from_config()
    status, res = post(
        f"/dsh-pet-7340/broadcast?pet={pet}&surface={surface}",
        {"text": text, "duration": seconds, "surface": surface},
    )
    if res.get("ok"):
        bubble_gate.done(text)
        print(f"✔ 气泡里说了：「{text}」")
        return True
    print(f"✘ {res.get('message') or res}")
    return False


def main():
    args = sys.argv[1:]
    if not args or args[0] == "list":
        anims = animations()
        print(f"共 {len(anims)} 个动作：\n")
        line = []
        for a in anims:
            line.append(a)
            if len(line) == 5:
                print("  " + "　".join(line))
                line = []
        if line:
            print("  " + "　".join(line))
        return 0

    cmd = args[0]
    if cmd == "play" and len(args) >= 2:
        return 0 if play(args[1]) else 1
    if cmd == "say" and len(args) >= 2:
        return 0 if say(args[1]) else 1
    if cmd == "both" and len(args) >= 3:
        ok1 = play(args[1])
        ok2 = say(args[2])
        return 0 if (ok1 and ok2) else 1

    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())




