"""只读读取主人的 B 站账号（关注、收藏、稍后再看、观看历史），写进琛琛的房间。

凭据：~/.dsh/bili/session.json  {"sessdata": "..."}
只用 SESSDATA，不做任何写操作（不点赞、不评论、不转发）。
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOME = os.path.expanduser("~")
SESSION = os.path.join(HOME, ".dsh", "bili", "session.json")
WORLD = os.path.join(HOME, ".dsh", "worlds", "default")
ROOM = os.path.join(WORLD, "room")
OUT = os.path.join(ROOM, "主人最近在看什么.md")
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs", "bili_account.log")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)


def log(msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def sessdata():
    try:
        raw = open(SESSION, encoding="utf-8-sig").read()
        data = json.loads(raw)
        v = (data.get("sessdata") or "").strip()
        return v or None
    except (OSError, ValueError):
        return None


def call(url, cookie, referer="https://www.bilibili.com/"):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Referer": referer,
            "Cookie": "SESSDATA=" + cookie,
        },
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def fmt_dur(sec):
    try:
        sec = int(sec)
    except (TypeError, ValueError):
        return ""
    if sec <= 0:
        return ""
    return "%d:%02d" % (sec // 60, sec % 60)


def get_profile(cookie):
    d = call("https://api.bilibili.com/x/web-interface/nav", cookie)
    if d.get("code") != 0:
        return None, d.get("message") or "nav failed"
    data = d.get("data") or {}
    if not data.get("isLogin"):
        return None, "SESSDATA 无效或已过期"
    return {"mid": data.get("mid"), "uname": data.get("uname"), "level": (data.get("level_info") or {}).get("current_level")}, None


def get_followings(cookie, mid, limit=12):
    url = "https://api.bilibili.com/x/relation/followings?vmid=%s&pn=1&ps=%d&order=desc" % (mid, limit)
    d = call(url, cookie)
    out = []
    for u in ((d.get("data") or {}).get("list") or []):
        out.append({"name": u.get("uname", ""), "sign": (u.get("sign") or "")[:40]})
    return out


def get_favs(cookie, mid, limit=8):
    d = call(
        "https://api.bilibili.com/x/v3/fav/folder/created/list-all?up_mid=%s" % mid, cookie
    )
    folders = ((d.get("data") or {}).get("list") or [])[:limit]
    out = []
    for f in folders:
        fid = f.get("id")
        cnt = f.get("media_count", 0)
        items = []
        try:
            r = call(
                "https://api.bilibili.com/x/v3/fav/resource/list?media_id=%s&pn=1&ps=5&platform=web" % fid,
                cookie,
            )
            for m in ((r.get("data") or {}).get("medias") or [])[:5]:
                items.append({"title": m.get("title", ""), "up": (m.get("upper") or {}).get("name", ""), "dur": m.get("duration")})
        except Exception:
            pass
        out.append({"title": f.get("title", ""), "count": cnt, "items": items})
    return out


def get_toview(cookie):
    d = call("https://api.bilibili.com/x/v2/history/toview", cookie)
    out = []
    for m in ((d.get("data") or {}).get("list") or [])[:10]:
        out.append(
            {
                "title": m.get("title", ""),
                "up": (m.get("owner") or {}).get("name", ""),
                "dur": fmt_dur(m.get("duration")),
                "progress": m.get("progress", -1),
            }
        )
    return out


def get_history(cookie, limit=15):
    d = call("https://api.bilibili.com/x/web-interface/history/cursor?ps=%d&type=archive" % limit, cookie)
    out = []
    for m in ((d.get("data") or {}).get("list") or [])[:limit]:
        out.append(
            {
                "title": m.get("title", ""),
                "author": m.get("author_name", ""),
                "viewed": m.get("view_at", 0),
                "progress": m.get("progress", -1),
                "dur": m.get("duration", 0),
                "tag": m.get("tag_name", ""),
            }
        )
    return out


def human_ts(ts):
    try:
        ts = int(ts)
        if ts <= 0:
            return ""
        return time.strftime("%m-%d %H:%M", time.localtime(ts))
    except Exception:
        return ""


def render(profile, follows, favs, toview, history, err=None):
    now = time.strftime("%Y-%m-%d %H:%M")
    lines = ["# 主人最近在看什么（%s）" % now, ""]
    if err:
        lines += ["> 这次没读到：%s" % err, ""]
        return "\n".join(lines)
    lines.append("这是主人允许我看的窗口，只读，我不会去点赞或者留言。")
    lines.append("")
    lines.append("## 主人（%s，Lv%s）" % (profile["uname"], profile["level"]))
    lines.append("")
    if history:
        lines.append("## 最近看过")
        for h in history:
            prog = ""
            if h["progress"] and h["dur"]:
                try:
                    pct = max(0, min(100, int(h["progress"] / h["dur"] * 100)))
                    prog = "（看到 %d%%）" % pct
                except Exception:
                    prog = ""
            lines.append(
                "- %s ｜ %s ｜ %s%s" % (h["title"], h["author"], human_ts(h["viewed"]), prog)
            )
        lines.append("")
    if toview:
        lines.append("## 稍后再看")
        for v in toview:
            lines.append("- %s ｜ %s ｜ %s" % (v["title"], v["up"], v["dur"]))
        lines.append("")
    if favs:
        lines.append("## 收藏夹")
        for f in favs:
            lines.append("### %s（%d 个）" % (f["title"], f["count"]))
            for m in f["items"]:
                lines.append("- %s ｜ %s" % (m["title"], m["up"]))
            lines.append("")
    if follows:
        lines.append("## 关注的 UP 主（最近关注的）")
        for u in follows:
            sign = ("—— " + u["sign"]) if u.get("sign") else ""
            lines.append("- %s %s" % (u["name"], sign))
        lines.append("")
    lines.append("---")
    lines.append("（只读窗口：我看得到，但不会做任何操作。）")
    return "\n".join(lines)


def run():
    cookie = sessdata()
    if not cookie:
        log("没有 SESSDATA：%s 不存在或为空" % SESSION)
        return False
    try:
        profile, err = get_profile(cookie)
        if err:
            log("profile failed: %s" % err)
            os.makedirs(ROOM, exist_ok=True)
            with open(OUT, "w", encoding="utf-8", newline="\n") as f:
                f.write(render({"uname": "?", "level": "?"}, [], [], [], [], err=err))
            return False
        mid = profile["mid"]
        follows = get_followings(cookie, mid)
        favs = get_favs(cookie, mid)
        toview = get_toview(cookie)
        history = get_history(cookie)
        text = render(profile, follows, favs, toview, history)
        os.makedirs(ROOM, exist_ok=True)
        tmp = OUT + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, OUT)
        log(
            "ok: %s | 历史 %d 条 / 稍后再看 %d / 收藏夹 %d / 关注 %d"
            % (profile["uname"], len(history), len(toview), len(favs), len(follows))
        )
        return True
    except Exception as e:
        log("failed: %s %s" % (type(e).__name__, str(e)[:100]))
        return False


if __name__ == "__main__":
    if "--loop" in sys.argv:
        while True:
            run()
            time.sleep(2 * 3600)
    sys.exit(0 if run() else 1)
