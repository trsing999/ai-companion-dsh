"""摸摸琛琛 / 喂琛琛 —— 把亲密度重新记起来。

用法:
    python tools/pet_touch.py touch     # 摸一下 +1
    python tools/pet_touch.py feed      # 喂一顿 +3
    python tools/pet_touch.py status    # 只看不摸
    python tools/pet_touch.py touch --quiet   # 只加好感，不去打扰她

亲密度真的存在 ~/.dsh/pet.json 里，而且每次都会通过 dsh-world 的桥
把「主人摸了摸你」送到她面前——她会回你一句。
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
PET_FILE = os.path.join(DSH, "pet.json")
BRIDGE_FILE = os.path.join(DSH, "worlds", "default", "bridge.json")

MAX_POINTS = 100
TOUCH_GAIN = 1
FEED_GAIN = 3
PUSH_COOLDOWN = 60          # 秒：连着点不重复打扰她

LEVELS = [
    (0, "还不熟"),
    (10, "认得你"),
    (30, "算朋友了"),
    (60, "挺亲近的"),
    (85, "很黏你"),
    (95, "离不开你了"),
]


def load_pet():
    try:
        with open(PET_FILE, encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return {"petId": "whale-girl", "display": {"visible": True, "size": 160,
                                                   "right": 785, "bottom": 76}}


def save_pet(pet):
    tmp = PET_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(pet, f, ensure_ascii=False, indent=2)
    os.replace(tmp, PET_FILE)


def level_of(pts):
    name = LEVELS[0][1]
    for th, label in LEVELS:
        if pts >= th:
            name = label
    return name


def say(text):
    try:
        with open(BRIDGE_FILE, encoding="utf-8-sig") as f:
            b = json.load(f)
        origin = str(b.get("origin", "")).rstrip("/")
        token = str(b.get("token", ""))
        if not origin or not token:
            return False
        body = json.dumps({"text": text}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            origin + "/dsh-world/bridge/say",
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8",
                     "x-dsh-world-token": token},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            return 200 <= r.status < 300
    except Exception as e:
        print(f"  （没送达：{e}）")
        return False


def show(pet, headline):
    a = pet.setdefault("affinity", {})
    pts = a.get("points", 0)
    full = "█" * int(pts / MAX_POINTS * 20)
    rest = "·" * (20 - len(full))
    print()
    print(f"  {headline}")
    print()
    print(f"  亲密度  {full}{rest}  {pts} / {MAX_POINTS}   「{level_of(pts)}」")
    print(f"  摸过 {a.get('pets', 0)} 次 · 喂过 {a.get('feeds', 0)} 次 · 被躲开 {a.get('petRejects', 0)} 次")
    print()


def main():
    args = [x for x in sys.argv[1:]]
    quiet = "--quiet" in args
    args = [x for x in args if not x.startswith("--")]
    mode = args[0] if args else "status"

    pet = load_pet()
    a = pet.setdefault("affinity", {})
    a.setdefault("points", 0)
    a.setdefault("pets", 0)
    a.setdefault("feeds", 0)
    a.setdefault("petRejects", 0)
    a.setdefault("feedRejects", 0)

    now_ms = int(time.time() * 1000)

    if mode == "status":
        show(pet, "琛琛现在这样")
        return

    if mode == "touch":
        before = a["points"]
        a["points"] = min(MAX_POINTS, before + TOUCH_GAIN)
        a["pets"] = a.get("pets", 0) + 1
        a["lastPetAt"] = now_ms
        moved = a["points"] - before
        headline = f"你摸了摸琛琛的头（{before} → {a['points']}）" if moved else "你摸了摸琛琛的头（已经满了，但她还是高兴）"
        push_text = "（主人摸了摸你的头）"
    elif mode == "feed":
        before = a["points"]
        a["points"] = min(MAX_POINTS, before + FEED_GAIN)
        a["feeds"] = a.get("feeds", 0) + 1
        a["lastFeedAt"] = now_ms
        a["lastPetAt"] = now_ms
        moved = a["points"] - before
        headline = f"你喂了琛琛一顿（{before} → {a['points']}）" if moved else "你喂了琛琛一顿（已经满了，但她还是吃了）"
        push_text = "（主人给你带了吃的，放在桌上了）"
    else:
        print(f"  不认识的命令：{mode}（用 touch / feed / status）")
        return

    save_pet(pet)
    show(pet, headline)

    if quiet:
        print("  （--quiet：这次没去打扰她）\n")
        return

    last_push = a.get("lastPushAt", 0)
    if now_ms - last_push < PUSH_COOLDOWN * 1000:
        wait = int(PUSH_COOLDOWN - (now_ms - last_push) / 1000)
        print(f"  （刚跟她说过了，{wait} 秒后再摸才会再告诉她）\n")
        return

    if say(push_text):
        a["lastPushAt"] = now_ms
        save_pet(pet)
        print("  ✔ 告诉她了，她应该马上会回你一句\n")
    else:
        print("  ✘ 没送进去（桥没开？她不在家？）\n")


if __name__ == "__main__":
    main()
