"""看一眼琛琛现在怎么样：亲密度、日记、房间、花费、信箱。

双击「看琛琛的状态.cmd」即可。
"""

import json
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOME = os.path.expanduser("~")
DSH = os.path.join(HOME, ".dsh")
WORLD = os.path.join(DSH, "worlds", "default")
ROOM = os.path.join(WORLD, "room")
DIARY = os.path.join(WORLD, "diary")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "logs", "inbox_watcher.log")


def load(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return None


def fmt(ts):
    if not ts:
        return "从没有"
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts / 1000 if ts > 1e11 else ts))
    except Exception:
        return "?"


def ago(ts):
    if not ts:
        return ""
    sec = time.time() - (ts / 1000 if ts > 1e11 else ts)
    if sec < 60:
        return "刚刚"
    if sec < 3600:
        return f"{int(sec // 60)} 分钟前"
    if sec < 86400:
        return f"{sec / 3600:.1f} 小时前"
    return f"{sec / 86400:.1f} 天前"


def line(title):
    print()
    print("─" * 46)
    print(f"  {title}")
    print("─" * 46)


print()
print("  🐋  琛琛现在怎么样")
print("  " + time.strftime("%Y-%m-%d %H:%M:%S"))

# ── 亲密度 ──
line("💗 亲密度（桌宠）")
pet = load(os.path.join(DSH, "pet.json"))
if pet:
    a = pet.get("affinity", {})
    d = pet.get("display", {})
    print(f"  亲密度      : {a.get('points', 0)} 点")
    print(f"  被摸过      : {a.get('pets', 0)} 次    （上次 {fmt(a.get('lastPetAt'))}，{ago(a.get('lastPetAt'))}）")
    print(f"  被喂过      : {a.get('feeds', 0)} 次    （上次 {fmt(a.get('lastFeedAt'))}）")
    print(f"  被躲开      : {a.get('petRejects', 0)} 次")
    print(f"  小人          : {pet.get('petId', '?')}，{'显示中' if d.get('visible') else '藏起来了'}，大小 {d.get('size', '?')}px")
else:
    print("  读不到 pet.json")

# ── 生活 ──
line("🌙 她的日子")
life = load(os.path.join(WORLD, "life.json"))
if life:
    sp = life.get("spend", {})
    print(f"  今天花了    : {sp.get('yuan', 0):.3f} 元")
    al = life.get("alarm", {})
    if al.get("at"):
        print(f"  下个闹钟    : {al['at']}（{al.get('source', '')}）")
    rv = life.get("review", {})
    if rv.get("at"):
        print(f"  上次回顾    : {rv['at']}")

# ── 日记 ──
line("📖 日记与自述")
try:
    ds = sorted(f for f in os.listdir(DIARY) if f.endswith(".md") and f[0].isdigit())
    print(f"  日记篇数    : {len(ds)}")
    if ds:
        last = ds[-1]
        print(f"  最新一篇    : {last}")
        print(f"  最后更新    : {time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(os.path.join(DIARY, last))))}")
except Exception as e:
    print(f"  日记目录读不了: {e}")

me = os.path.join(ROOM, "我是谁.md")
if os.path.exists(me):
    txt = open(me, encoding="utf-8-sig").read()
    print(f"  我是谁      : {len(txt)} 字，最后改于 {time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(me)))}")

# ── 房间 ──
line("🏠 她的房间")
for sub in ("", "inbox", "outbox"):
    p = os.path.join(ROOM, sub) if sub else ROOM
    try:
        files = [f for f in os.listdir(p) if os.path.isfile(os.path.join(p, f))]
        n = len(files)
        name = "房间根目录" if not sub else ("收信抽屉 inbox" if sub == "inbox" else "回信抽屉 outbox")
        print(f"  {name:<14}: {n} 个文件")
    except Exception:
        pass
print(f"  完整路径    : {ROOM}")

# ── 送信的路 ──
line("📮 送信的路")
b = load(os.path.join(WORLD, "bridge.json"))
if b:
    print(f"  桥          : {b.get('origin')}（token {str(b.get('token'))[:8]}…）")
else:
    print("  桥          : 读不到 bridge.json")

alive = False
if os.path.exists(LOG):
    m = os.path.getmtime(LOG)
    age = time.time() - m
    print(f"  哨兵日志    : 最后一行 {ago(m)}")
    alive = age < 180
    print(f"  哨兵状态    : {'✅ 在跑' if alive else '❌ 没在跑（双击桌面「启动信箱哨兵」）'}")
    try:
        st = os.path.join(ROOT, "logs", "inbox_watcher.state.json")
        d = load(st) or {}
        letters = [k for k in d if not k.startswith("__")]
        print(f"  送过的信    : {len(letters)} 封")
    except Exception:
        pass
else:
    print("  哨兵日志    : 还没有（没启动过）")

print()
print("─" * 46)
print()
