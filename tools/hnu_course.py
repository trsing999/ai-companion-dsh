"""给她安排课：湖南大学的优先，加上具身智能，再放宽到优质公开课。

用主人 B 站的登录态（SESSDATA，只读）搜，筛掉标题党和考研视频，
写进她房间 room/我的课.md。

用法：
    python tools/hnu_course.py            # 搜一轮，更新文件
    python tools/hnu_course.py --show     # 只在终端看
"""

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOME = os.path.expanduser("~")
SESSION = os.path.join(HOME, ".dsh", "bili", "session.json")
WORLD = os.path.join(HOME, ".dsh", "worlds", "default")
OUT = os.path.join(WORLD, "room", "我的课.md")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")

# 三组：湖大的课 / 具身智能 / 专业基础
GROUPS = [
    ("🏫 湖南大学的课", [
        "湖南大学 人工智能 公开课",
        "湖南大学 信号与系统",
        "湖南大学 电路基础",
        "湖南大学 模拟电子技术",
    ]),
    ("🤖 具身智能", [
        "具身智能 公开课",
        "具身智能 机器人 课程",
        "强化学习 机器人 课程",
    ]),
    ("📡 电子信息 / AI 基础", [
        "电子信息 专业课 公开课",
        "机器学习 公开课 完整",
    ]),
]

MIN_SECONDS = 900          # 15 分钟以下的基本不是正经课
MAX_PER_SEARCH = 3

OFFICIAL_UP = ("湖南大学",)

NOISE_WORDS = (
    "张雪峰", "考研", "择校", "速成", "期末", "突击", "不挂科",
    "报录", "真题", "试卷", "就业", "找不到工作",
    "学不会", "退出IT圈", "拿走不谢", "扛霸子", "天花板",
    "996", "吹爆", "卷",
)


def sessdata():
    try:
        with open(SESSION, encoding="utf-8-sig") as f:
            return (json.load(f).get("sessdata") or "").strip() or None
    except Exception:
        return None


def api(url):
    ck = sessdata()
    headers = {"User-Agent": UA, "Referer": "https://www.bilibili.com/"}
    if ck:
        headers["Cookie"] = "SESSDATA=" + ck
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def clean_title(t):
    t = re.sub(r"<[^>]+>", "", t or "")
    t = t.replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
    return " ".join(t.split())


def secs(d):
    parts = [int(p) for p in re.findall(r"\d+", str(d))]
    if not parts:
        return 0
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return parts[0]


def score(it):
    s = 0
    t, up = it["title"], it["up"]
    if up in OFFICIAL_UP:
        s += 12
    if "湖南大学" in t:
        s += 8
    if any(k in t for k in ("具身智能", "机器人", "强化学习", "embodied")):
        s += 8
    if "公开课" in t:
        s += 5
    if "完整" in t or "合集" in t or "全" in t:
        s += 2
    if it["mins"] >= 300:
        s += 2
    if it["play"] >= 10000:
        s += 1
    return s


def search(kw):
    url = ("https://api.bilibili.com/x/web-interface/wbi/search/type"
           f"?search_type=video&keyword={urllib.parse.quote(kw)}")
    try:
        j = api(url)
    except Exception:
        return []
    if j.get("code") != 0:
        return []
    out = []
    for it in ((j.get("data") or {}).get("result") or []):
        s = secs(it.get("duration"))
        if s < MIN_SECONDS:
            continue
        rec = {
            "title": clean_title(it.get("title")),
            "up": it.get("author") or "",
            "bvid": it.get("bvid") or "",
            "mins": s // 60,
            "play": it.get("play") or 0,
        }
        if any(w in rec["title"] for w in NOISE_WORDS):
            continue
        out.append(rec)
    out.sort(key=score, reverse=True)
    return [r for r in out if score(r) >= 5][:MAX_PER_SEARCH]


def build():
    now = time.strftime("%Y-%m-%d %H:%M")
    lines = ["# 我的课", "",
             f"（{now} 搜的。用主人的登录态只读，不点赞不评论。）", ""]
    total = 0
    seen = set()

    for group, kws in GROUPS:
        got = []
        for kw in kws:
            for it in search(kw):
                if it["bvid"] in seen:
                    continue
                seen.add(it["bvid"])
                got.append(it)
            time.sleep(1.2)
        if not got:
            continue
        got.sort(key=score, reverse=True)
        lines.append(f"## {group}")
        lines.append("")
        for it in got[:5]:
            total += 1
            star = "⭐ " if it["up"] in OFFICIAL_UP else ""
            lines.append(f"- {star}**{it['title']}**")
            lines.append(f"  - {it['mins']} 分钟 · {it['play']:,} 次播放 · {it['up']}")
            lines.append(f"  - https://www.bilibili.com/video/{it['bvid']}")
        lines.append("")

    if total == 0:
        lines += ["（这次一条都没搜到。可能登录态过期，或者接口变了。）", ""]

    lines += ["---", "",
              "想上哪一门，让主人播出来，我跟着看（抽帧 + 读简介）。", ""]

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8-sig") as f:
        f.write("\n".join(lines))
    return OUT, total


def main():
    path, n = build()
    print(f"  找到 {n} 门 → {path}")
    if "--show" in sys.argv:
        try:
            print(open(path, encoding="utf-8-sig").read()[:2000])
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
