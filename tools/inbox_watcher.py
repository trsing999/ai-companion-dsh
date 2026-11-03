"""信箱哨兵：room/inbox 一有新信，立刻通过 dsh-world 的桥送进她的家。

主人把信丢进 <DSH 世界>/room/inbox/，
这个进程在两秒内发现，读出来，POST 给 dsh-world 的 bridge/say，
于是这句话就作为「主人说的」进入她的家和记忆——她会真的看到。

特点：
- 每封信只送一次（按文件名去重），记在 room/state/delivered.json
- 文件要静止 1.5 秒才送，避免主人还在打字就送出去半封
- bridge.json 的 token 每次发送前重新读，DSH 重启后自动跟上
- 送信成功/失败都写 logs/inbox_watcher.log
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
WORLD = os.path.join(os.path.expanduser("~"),
                     ".dsh", "worlds", "default")
ROOM = os.path.join(WORLD, "room")
DIARY_DIR = os.path.join(WORLD, "diary")
INBOX = os.path.join(ROOM, "inbox")
STATE = os.path.join(ROOT, "logs")          # 已送记录放工作区，房间外写不动
DELIVERED = os.path.join(STATE, "inbox_watcher.state.json")
BRIDGE_FILE = os.path.join(WORLD, "bridge.json")
SCHEDULE_FILE = os.path.join(ROOM, "主人的日程.md")


def desktop_schedule():
    """桌面上的「日程.txt」——主人每天在这儿写今天的安排。"""
    home = os.path.expanduser("~")
    for p in (os.path.join(home, "OneDrive", "Desktop", "日程.txt"),
              os.path.join(home, "Desktop", "日程.txt")):
        if os.path.exists(p):
            return p
    return os.path.join(home, "OneDrive", "Desktop", "日程.txt")
PET_FILE = os.path.join(os.path.expanduser("~"), ".dsh", "pet.json")
LOG = os.path.join(ROOT, "logs", "inbox_watcher.log")

POLL_SECONDS = 2.0
STABLE_SECONDS = 1.5      # 文件最后改动后至少安静这么久才送
MAX_CHARS = 8000          # 太长的信只送前面，剩下的请主人看原文
RETRY = 3
BRIEF_AT = (8, 30)        # 每天几点把「今天」推给她
OUTSIDE_EVERY = 900       # 每隔多久去看一眼外面（天气/新闻），只刷新文件不推送
CLASSIC_EVERY = 1800      # 每隔多久确认一次「今天那一段古籍」有没有换
AUTO_WATCH_EVERY = 5      # 每隔多久看一眼主人是不是在看动漫（配合 auto_watch 里 10 秒的间隔）
MUSIC_EVERY = 300         # 每隔多久听一次主人在放什么歌
NIGHT_EVERY = 1800        # 夜里多久让她困一次
CLEAN_EVERY = 86400       # 多久清一次缓存（视频、抽帧、截图、日志）

SKIP_NAMES = {"README.md", "放这里.md", "desktop.ini"}
SKIP_PREFIX = ("_模板", "_", "~$")     # 摸板/临时文件不算信
LETTER_EXT = {".txt", ".md", ".markdown", ".text", ""}


def log(msg):
    line = time.strftime("%H:%M:%S ") + msg
    try:
        print(line, flush=True)
    except Exception:
        pass          # 没有控制台句柄时别崩，写文件就够了
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d ") + line + "\n")
    except Exception:
        pass


def load_delivered():
    try:
        with open(DELIVERED, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_delivered(data):
    try:
        os.makedirs(STATE, exist_ok=True)
        # 只留最近的 300 条，别越滚越大
        if len(data) > 300:
            keep = sorted(data.items(), key=lambda kv: kv[1])[-300:]
            data = dict(keep)
        tmp = DELIVERED + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, DELIVERED)
    except Exception as e:
        log(f"!! 存已送记录失败: {e}")


def read_letter(path):
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            with open(path, encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
        except Exception as e:
            log(f"!! 读不了 {os.path.basename(path)}: {e}")
            return None
    # 二进制兜底，总比没有强
    try:
        with open(path, "rb") as f:
            return f.read().decode("utf-8", "replace")
    except Exception as e:
        log(f"!! 读不了 {os.path.basename(path)}: {e}")
        return None


def bridge():
    with open(BRIDGE_FILE, encoding="utf-8") as f:
        b = json.load(f)
    origin = str(b.get("origin", "")).rstrip("/")
    token = str(b.get("token", ""))
    if not origin or not token:
        raise RuntimeError("bridge.json 里没有 origin/token（桥没开？）")
    return origin, token


def say(origin, token, text):
    body = json.dumps({"text": text}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        origin + "/dsh-world/bridge/say",
        data=body,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "x-dsh-world-token": token,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status, r.read().decode("utf-8", "replace")


def deliver(f, delivered):
    name = f.name
    if name in delivered:
        return
    if name in SKIP_NAMES or name.startswith(SKIP_PREFIX):
        return
    if os.path.splitext(name)[1].lower() not in LETTER_EXT:
        return
    age = time.time() - f.stat().st_mtime
    if age < STABLE_SECONDS:
        return  # 主人还在写

    content = read_letter(f.path)
    if content is None:
        return

    stamped = time.strftime("%Y-%m-%d %H:%M", time.localtime(f.stat().st_mtime))
    body = content.strip()
    note = ""
    if len(body) > MAX_CHARS:
        note = f"\n\n（信很长，这里只送了前 {MAX_CHARS} 字，剩下的你自己去看原文吧）"
        body = body[:MAX_CHARS]

    text = f"（主人往抽屉里放了一封信：{name}，{stamped} 写的）\n\n{body}{note}"

    last_err = None
    for attempt in range(1, RETRY + 1):
        try:
            origin, token = bridge()
            status, resp = say(origin, token, text)
            log(f">> 送达《{name}》 -> HTTP {status} {resp.strip()[:80]}")
            delivered[name] = time.time()
            save_delivered(delivered)
            return
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code} {e.read().decode('utf-8', 'replace')[:120]}"
        except Exception as e:
            last_err = str(e)
        if attempt < RETRY:
            time.sleep(2 * attempt)

    log(f"!! 送不出去《{name}》: {last_err}（下次还会再试）")


def today_section():
    """读桌面「日程.txt」。

    只有"最近 20 小时内动过"的才算今天的安排——
    昨晚写的，今早推；前天写的，不推。这样永远不会把旧的当成新的。
    """
    path = desktop_schedule()
    try:
        age = time.time() - os.path.getmtime(path)
    except Exception:
        return ""
    if age > 20 * 3600:
        return ""      # 太久没改了，当没有

    try:
        with open(path, encoding="utf-8-sig") as f:
            raw = f.read()
    except Exception:
        return ""

    lines = []
    for ln in raw.splitlines():
        s = ln.strip()
        if not s:
            continue
        if s.startswith("（") or s.startswith("("):
            continue      # 括号里的说明不算安排
        lines.append(s)
    return "\n".join(lines).strip()


def room_snapshot():
    """整理一份她房间的现状：写 room/今天的样子.md，返回一句概况。"""
    pics = []
    try:
        for f in os.listdir(ROOM):
            p = os.path.join(ROOM, f)
            if os.path.isfile(p) and f.lower().endswith((".png", ".jpg", ".jpeg")):
                pics.append((os.path.getmtime(p), f))
        pics.sort(reverse=True)
    except Exception:
        pass

    letters = {}
    for sub in ("inbox", "outbox"):
        n = 0
        try:
            d = os.path.join(ROOM, sub)
            for f in os.listdir(d):
                if (os.path.isfile(os.path.join(d, f))
                        and f not in SKIP_NAMES
                        and not f.startswith(SKIP_PREFIX)):
                    n += 1
        except Exception:
            pass
        letters[sub] = n

    try:
        diaries = sum(1 for f in os.listdir(DIARY_DIR)
                      if f.endswith(".md") and f[0].isdigit())
    except Exception:
        diaries = 0

    latest = ""
    if pics:
        latest = (time.strftime("%m-%d %H:%M", time.localtime(pics[0][0]))
                  + " 的《" + os.path.splitext(pics[0][1])[0] + "》")

    lines = [
        "# 今天的样子",
        "",
        "（每天八点半自动更新，主人不用管）",
        "",
        f"- 你房间里的画：{len(pics)} 张",
        f"- 你的日记：{diaries} 篇",
        f"- 抽屉里：来信 {letters['inbox']} 封，回信 {letters['outbox']} 封",
    ]
    if latest:
        lines.append(f"- 最近画的一张：{latest}")

    try:
        with open(os.path.join(ROOM, "今天的样子.md"), "w", encoding="utf-8-sig") as f:
            f.write("\n".join(lines) + "\n")
    except Exception as e:
        log(f"!! 房间快照写不进去: {e}（不影响推送）")

    return (f"（你房间今天有 {len(pics)} 张画、{diaries} 篇日记，"
            f"抽屉里躺着 {letters['inbox']} 封信）")


def affinity_line():
    """把亲密度读出来，附在每日推送里——让她看得见。"""
    try:
        with open(PET_FILE, encoding="utf-8-sig") as f:
            pet = json.load(f)
        a = pet.get("affinity", {})
        pts = int(a.get("points", 0))
        pets = int(a.get("pets", 0))
        feeds = int(a.get("feeds", 0))
        if pts == 0 and pets == 0 and feeds == 0:
            return ""
        return (f"（主人摸过你 {pets} 次、喂过你 {feeds} 次，"
                f"亲密度 {pts}/100）")
    except Exception:
        return ""


def push_brief(delivered, outside=""):
    """每天 8:30 之后，把今天的安排送进她的家。一天只送一次。"""
    now = time.localtime()
    today = time.strftime("%Y-%m-%d", now)
    key = "__brief__" + today
    if key in delivered:
        return
    if (now.tm_hour, now.tm_min) < BRIEF_AT:
        return

    text = today_section()
    if not text:
        log(f"-- 今天日程是空的，不打扰（{today}）")
        delivered[key] = time.time()
        save_delivered(delivered)
        return

    snap = room_snapshot()
    aff = affinity_line()
    body = f"（早上八点半，主人把今天的安排放在了你桌上）\n\n{text}"
    if snap:
        body += f"\n\n{snap}"
    if aff:
        body += f"\n{aff}"
    if outside:
        body += f"\n{outside}"

    last_err = None
    for attempt in range(1, RETRY + 1):
        try:
            origin, token = bridge()
            status, resp = say(origin, token, body)
            log(f">> 日程送达（{today}） -> HTTP {status} {resp.strip()[:60]}")
            delivered[key] = time.time()
            save_delivered(delivered)
            return
        except Exception as e:
            last_err = str(e)
            if attempt < RETRY:
                time.sleep(2 * attempt)
    log(f"!! 日程送不出去: {last_err}（下次再试）")


def main():
    os.makedirs(INBOX, exist_ok=True)
    os.makedirs(STATE, exist_ok=True)
    delivered = load_delivered()
    log(f"== 信箱哨兵上线，盯着 {INBOX} ==")
    try:
        origin, token = bridge()
        log(f"   桥: {origin}（token 前 8 位 {token[:8]}…）")
    except Exception as e:
        log(f"   !! 现在读不到桥: {e}（会一直重试）")

    outside_line = ""
    next_outside = 0.0
    next_classic = 0.0
    next_auto = 0.0
    next_music = 0.0
    next_night = 0.0
    next_clean = time.time() + 300      # 起来 5 分钟后先清一次
    while True:
        if time.time() >= next_clean:
            try:
                import cleanup
                cleanup.do_clean()
            except Exception as e:
                log(f"!! 清缓存失败: {e}")
            next_clean = time.time() + CLEAN_EVERY

        if time.time() >= next_music:
            try:
                import now_playing
                now_playing.main()
            except Exception as e:
                log(f"!! 听音乐失败: {e}")
            next_music = time.time() + MUSIC_EVERY

        if time.time() >= next_night:
            try:
                import pet_night
                if pet_night.is_night():
                    pet_night.nap()
            except Exception as e:
                log(f"!! 夜里困不了: {e}")
            next_night = time.time() + NIGHT_EVERY

        if time.time() >= next_auto:
            try:
                import auto_watch
                auto_watch.tick()
            except Exception as e:
                log(f"!! 自动陪看出错: {e}")
            next_auto = time.time() + AUTO_WATCH_EVERY

        if time.time() >= next_classic:
            try:
                import classic_daily
                ok, note = classic_daily.ensure()
                log(f"-- 今日一条：{note}")
            except Exception as e:
                log(f"!! 今日一条失败: {e}")
            next_classic = time.time() + CLASSIC_EVERY

        if time.time() >= next_outside:
            try:
                import outside_world
                outside_line = outside_world.build() or ""
                if outside_line:
                    log(f"-- 外面看过了：{outside_line[:60]}")
            except Exception as e:
                log(f"!! 看外面失败: {e}")
            next_outside = time.time() + OUTSIDE_EVERY

        try:
            push_brief(delivered, outside_line)
        except Exception as e:
            log(f"!! 日程检查出错: {e}")
        try:
            if os.path.isdir(INBOX):
                files = sorted(
                    (p for p in os.scandir(INBOX) if p.is_file()),
                    key=lambda p: p.stat().st_mtime,
                )
                for f in files:
                    try:
                        deliver(f, delivered)
                    except Exception as e:
                        log(f"!! 处理 {f.name} 出错: {e}")
        except Exception as e:
            log(f"!! 扫描出错: {e}")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("== 信箱哨兵下线 ==")
