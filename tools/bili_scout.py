"""给 world 的琛琛加"刷 B 站"能力（只读，不登录、不评论）。

做法：定时抓 B 站公开热门/分区排行，整理成一段可读的清单，
写进她自己的房间 worlds/default/room/b站刷到的.md。
她在自己的会话里可以 read 这个文件，看到什么、想聊什么由她决定。
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WORLD = os.path.join(os.environ["USERPROFILE"], ".dsh", "worlds", "default")
ROOM = os.path.join(WORLD, "room")
OUT = os.path.join(ROOM, "b站刷到的.md")
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs", "bili_scout.log")
INTERVAL = 3600  # 每小时刷一次

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
}


def log(msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def api(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def popular(ps=12):
    data = api("https://api.bilibili.com/x/web-interface/popular?ps=%d&pn=1" % ps)
    items = (data.get("data") or {}).get("list") or []
    out = []
    for it in items:
        dur = it.get("duration") or 0
        out.append(
            {
                "title": (it.get("title") or "").strip(),
                "up": ((it.get("owner") or {}).get("name") or "").strip(),
                "views": it.get("stat", {}).get("view", 0),
                "danmaku": it.get("stat", {}).get("danmaku", 0),
                "duration": "%d:%02d" % (dur // 60, dur % 60),
                "desc": (it.get("desc") or "").strip().replace("\n", " ")[:120],
                "bvid": it.get("bvid", ""),
                "url": "https://www.bilibili.com/video/" + (it.get("bvid") or ""),
            }
        )
    return out


def render(items):
    now = time.strftime("%Y-%m-%d %H:%M")
    lines = ["# 我刷到的 B 站（%s）" % now, ""]
    lines.append("这是主人给我开的窗口，我可以从这里看看外面。下面的数字是播放量和弹幕数。")
    lines.append("")
    for i, v in enumerate(items, 1):
        lines.append("## %d. %s" % (i, v["title"]))
        lines.append("- UP 主：%s" % v["up"])
        lines.append("- 时长 %s ｜ 播放 %s ｜ 弹幕 %s" % (v["duration"], v["views"], v["danmaku"]))
        if v["desc"]:
            lines.append("- 简介：%s" % v["desc"])
        lines.append("- 链接：%s" % v["url"])
        lines.append("")
    lines.append("---")
    lines.append("（这些是我能看见的清单。真要看画面，得主人帮我装 ffmpeg 和视觉模型。）")
    return "\n".join(lines)


def once():
    try:
        items = popular()
        if not items:
            log("empty list")
            return False
        os.makedirs(ROOM, exist_ok=True)
        text = render(items)
        tmp = OUT + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, OUT)
        log("wrote %d videos -> %s" % (len(items), OUT))
        return True
    except Exception as e:
        log("failed: %s %s" % (type(e).__name__, str(e)[:80]))
        return False


def main():
    if "--once" in sys.argv:
        ok = once()
        print("ok" if ok else "failed")
        return
    while True:
        once()
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
