"""把她在世界里说的话、写的日记，全部镜像到手机。

来源：
  worlds/default/conversations/<今天>.jsonl   她的每一条 assistant 消息
  worlds/default/diary/<日期>.md              当天日记（写完推一次）
  worlds/default/room/我是谁.md               自述被改写时推一次

去重：按 recordId / 文件大小偏移记录，重启后不重复推历史。
"""

import glob
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from notify_mobile import push  # noqa: E402

WORLD = os.path.join(os.path.expanduser("~"), ".dsh", "worlds", "default")
STATE = os.path.join(HERE, "..", "logs", "world_mirror_state.json")
LOG = os.path.join(HERE, "..", "logs", "world_mirror.log")
POLL = 5


def log(msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def load_state():
    try:
        return json.loads(open(STATE, encoding="utf-8").read())
    except (OSError, ValueError):
        return {"seen": [], "offsets": {}, "diary": {}}


def save_state(st):
    try:
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        tmp = STATE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False)
        os.replace(tmp, STATE)
    except OSError:
        pass


def send(title, text):
    if not text.strip():
        return
    try:
        ok, detail = push(title, text)
        log("push %s %s | %s" % ("ok" if ok else "FAIL", str(detail)[:60], text[:40]))
    except Exception as e:
        log("push error: %s" % e)


def watch_conversations(st):
    today = time.strftime("%Y-%m-%d")
    path = os.path.join(WORLD, "conversations", today + ".jsonl")
    try:
        size = os.path.getsize(path)
    except OSError:
        return
    key = "conv"
    off = st["offsets"].get(key, size)  # 首次运行从末尾开始，不回放历史
    if size < off:
        off = 0
    if size == off:
        st["offsets"][key] = off
        return
    with open(path, "rb") as f:
        f.seek(off)
        chunk = f.read()
        st["offsets"][key] = f.tell()
    for raw in chunk.splitlines():
        if not raw.strip():
            continue
        try:
            rec = json.loads(raw.decode("utf-8", "replace"))
        except ValueError:
            continue
        if rec.get("role") != "assistant":
            continue
        if rec.get("status") not in (None, "complete"):
            continue
        rid = rec.get("recordId")
        if rid in st["seen"]:
            continue
        st["seen"].append(rid)
        st["seen"] = st["seen"][-500:]
        text = (rec.get("content") or "").strip()
        if text:
            send("琛琛", text)


def watch_diary(st):
    for path in sorted(glob.glob(os.path.join(WORLD, "diary", "*.md")))[-2:]:
        try:
            size = os.path.getsize(path)
            mtime = int(os.path.getmtime(path))
        except OSError:
            continue
        key = os.path.basename(path)
        prev = st["diary"].get(key) or {}
        if prev.get("size") == size:
            continue
        # 首次见到只登记，不推历史
        st["diary"][key] = {"size": size, "mtime": mtime}
        if not prev:
            continue
        try:
            body = open(path, encoding="utf-8").read()
        except OSError:
            continue
        text = body.strip()
        if len(text) > 1500:
            text = text[:1500] + "…"
        send("琛琛的日记 · " + key.replace(".md", ""), text)


def watch_persona(st):
    path = os.path.join(WORLD, "room", "我是谁.md")
    try:
        size = os.path.getsize(path)
    except OSError:
        return
    key = "self"
    prev = st["diary"].get(key) or {}
    if prev.get("size") == size:
        return
    st["diary"][key] = {"size": size}
    if not prev:
        return
    try:
        body = open(path, encoding="utf-8").read().strip()
    except OSError:
        return
    if len(body) > 1200:
        body = body[:1200] + "…"
    send("琛琛改写了「我是谁」", body)


def main():
    st = load_state()
    log("start; 已推送 %d 条历史" % len(st["seen"]))
    while True:
        try:
            watch_conversations(st)
            watch_diary(st)
            watch_persona(st)
            save_state(st)
        except Exception as e:
            log("loop error: %s %s" % (type(e).__name__, str(e)[:80]))
        time.sleep(POLL)


if __name__ == "__main__":
    main()
