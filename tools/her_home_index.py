"""生成"琛琛的家"索引页，然后拿浏览器打开。

双击执行一次：
    1. 现场扫一遍她的房间、日记、画、课、日志
    2. 生成一个 HTML（每个条目都能点开）
    3. 用默认浏览器打开

所以它不是死清单——每次打开都是当下的样子。
"""

import html
import os
import subprocess
import sys
import time
import webbrowser

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOME = os.path.expanduser("~")
WORLD = os.path.join(HOME, ".dsh", "worlds", "default")
ROOM = os.path.join(WORLD, "room")
DIARY = os.path.join(WORLD, "diary")
ACTIVITY = os.path.join(WORLD, "activity")
CONV = os.path.join(WORLD, "conversations")
PETS = os.path.join(HOME, ".dsh", "dsh-pet")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS = os.path.join(ROOT, "logs")
OUT = os.path.join(ROOT, "琛琛的家.html")

SKIP_IMG = ("屏幕", "色卡", "热键-", "printwindow", "看动漫")


def say(m):
    """pythonw 下 stdout 是 None，print 会炸。"""
    try:
        print(m, flush=True)
    except Exception:
        pass


def url(p):
    """本地路径 → file:// URL。"""
    p = os.path.abspath(p).replace("\\", "/")
    out = []
    for ch in p:
        if ch == " ":
            out.append("%20")
        elif ch == "#":
            out.append("%23")
        elif ch == "?":
            out.append("%3F")
        elif ord(ch) > 127:
            out.append(ch)          # 现代浏览器认 UTF-8 中文路径，保持可读
        else:
            out.append(ch)
    return "file:///" + "".join(out)


def sz(n):
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.0f} KB"
    return f"{n / 1024 / 1024:.1f} MB"


def ago(t):
    d = time.time() - t
    if d < 90:
        return "刚改过"
    if d < 3600:
        return f"{int(d / 60)} 分钟前"
    if d < 86400:
        return f"{int(d / 3600)} 小时前"
    return time.strftime("%m-%d %H:%M", time.localtime(t))


def ls(d, exts=None, skip=()):
    """目录里符合条件的文件，按修改时间倒序。"""
    out = []
    try:
        for f in os.listdir(d):
            if exts and not f.lower().endswith(exts):
                continue
            if any(s in f for s in skip):
                continue
            p = os.path.join(d, f)
            if not os.path.isfile(p):
                continue
            try:
                st = os.stat(p)
            except OSError:
                continue
            out.append((f, p, st.st_size, st.st_mtime))
    except OSError:
        pass
    out.sort(key=lambda x: -x[3])
    return out


def row(f, p, size, mtime):
    return (
        '<a class="file" href="%s" target="_blank">'
        '<span class="fn">%s</span>'
        '<span class="meta">%s · %s</span></a>'
        % (url(p), html.escape(f), sz(size), ago(mtime))
    )


def tile(f, p, size, mtime):
    return (
        '<a class="tile" href="%s" target="_blank" title="%s">'
        '<img src="%s" loading="lazy" alt="">'
        '<span>%s</span></a>'
        % (url(p), html.escape(f), url(p), html.escape(f))
    )


CSS = """
*{box-sizing:border-box}
body{
  margin:0;padding:34px 30px 70px;background:#0d0f13;color:#dfe3ea;
  font-family:"Segoe UI","Microsoft YaHei UI","Microsoft YaHei",sans-serif;
  font-size:14px;line-height:1.6;
}
body::before{
  content:"";position:fixed;inset:0;pointer-events:none;
  background:radial-gradient(900px 500px at 12% -10%,rgba(94,140,255,.16),transparent 60%),
             radial-gradient(700px 420px at 92% 4%,rgba(255,120,200,.10),transparent 60%);
}
.wrap{max-width:1180px;margin:0 auto;position:relative}
h1{
  font-size:25px;margin:0 0 4px;font-weight:600;letter-spacing:.5px;
  background:linear-gradient(92deg,#9fc4ff,#e7b6ff 60%,#ffd6a5);
  -webkit-background-clip:text;background-clip:text;color:transparent;
}
.sub{color:#7b8494;font-size:12.5px;margin-bottom:30px}
.sub b{color:#a8b3c6;font-weight:500}
h2{
  font-size:14px;margin:34px 0 12px;color:#97a3b6;font-weight:600;
  letter-spacing:1.2px;display:flex;align-items:center;gap:9px;
}
h2::after{content:"";flex:1;height:1px;background:linear-gradient(90deg,#222a36,transparent)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(255px,1fr));gap:9px}
a.file{
  display:flex;flex-direction:column;gap:3px;padding:10px 13px;border-radius:10px;
  background:#151922;border:1px solid #1f2530;text-decoration:none;color:inherit;
  transition:.16s;overflow:hidden;
}
a.file:hover{background:#1b2130;border-color:#33405a;transform:translateY(-1px)}
.fn{font-size:13.5px;color:#e6ebf5;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.meta{font-size:11px;color:#6d7787}
.wall{display:grid;grid-template-columns:repeat(auto-fill,minmax(155px,1fr));gap:10px}
a.tile{
  display:block;border-radius:10px;overflow:hidden;background:#151922;
  border:1px solid #1f2530;text-decoration:none;color:#8d97a7;font-size:11px;
  transition:.16s;
}
a.tile:hover{border-color:#48597a;transform:translateY(-2px)}
a.tile img{width:100%;height:118px;object-fit:cover;display:block;background:#0b0d11}
a.tile span{display:block;padding:6px 8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.big{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px}
a.card{
  display:block;padding:15px 17px;border-radius:12px;text-decoration:none;color:inherit;
  background:linear-gradient(160deg,#161b25,#12161e);border:1px solid #212836;transition:.16s;
}
a.card:hover{border-color:#3d4c6b;transform:translateY(-2px)}
a.card .t{font-size:14.5px;color:#e9eef7;margin-bottom:3px}
a.card .d{font-size:11.5px;color:#6d7787}
a.card .n{font-size:22px;font-weight:600;color:#8fb2ff;margin-bottom:2px}
.empty{color:#4e5765;font-size:12.5px;padding:8px 2px}
footer{margin-top:48px;color:#4a525f;font-size:11.5px;text-align:center}
"""


def build():
    now = time.strftime("%Y-%m-%d %H:%M")
    parts = [
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        "<title>琛琛的家</title><style>", CSS, "</style></head><body><div class='wrap'>",
        "<h1>琛琛的家</h1>",
        f"<div class='sub'>生成于 <b>{now}</b>　·　这里的东西每打开一次都重新扫一遍</div>",
    ]

    # ── 房间文件 ──
    room_files = [f for f in ls(ROOM) if not f[0].lower().endswith((".png", ".jpg", ".jpeg"))]
    parts.append("<h2>她的房间 · 文件</h2><div class='grid'>")
    if room_files:
        parts += [row(*f) for f in room_files]
    else:
        parts.append("<div class='empty'>空的</div>")
    parts.append("</div>")

    # ── 日记 ──
    days = ls(DIARY, (".md",))
    parts.append("<h2>她的日记</h2><div class='grid'>")
    if days:
        parts += [row(*f) for f in days]
    else:
        parts.append("<div class='empty'>还没写</div>")
    parts.append("</div>")

    # ── 画 ──
    pics = ls(ROOM, (".png", ".jpg", ".jpeg"), SKIP_IMG)
    parts.append("<h2>她画的画</h2><div class='wall'>")
    if pics:
        parts += [tile(*f) for f in pics[:24]]
    else:
        parts.append("<div class='empty'>还没画</div>")
    parts.append("</div>")

    # ── 看动漫 ──
    eps = []
    d = os.path.join(ROOM, "看动漫")
    try:
        eps = sorted(os.listdir(d), reverse=True)
    except OSError:
        pass
    parts.append("<h2>她看过的动漫</h2><div class='grid'>")
    if eps:
        for e in eps[:16]:
            p = os.path.join(d, e)
            if os.path.isdir(p):
                n = len([x for x in os.listdir(p) if x.lower().endswith((".jpg", ".png"))])
                parts.append(
                    '<a class="file" href="%s" target="_blank">'
                    '<span class="fn">%s</span><span class="meta">%d 帧</span></a>'
                    % (url(p), html.escape(e), n)
                )
    else:
        parts.append("<div class='empty'>还没看</div>")
    parts.append("</div>")

    # ── 课和书 ──
    parts.append("<h2>她在学的</h2><div class='grid'>")
    # 先把她能打勾的课程清单摆最前面
    for f in ls(ROOM, (".md",)):
        if f[0].startswith("我的课"):
            parts.append(row(*f))
    items = []
    for sub in ("课", "书", "收藏", "看屏幕", "inbox", "outbox"):
        p = os.path.join(ROOM, sub)
        if os.path.isdir(p):
            n = len([x for x in os.listdir(p)])
            items.append((sub, p, n))
    for name, p, n in items:
        parts.append(
            '<a class="file" href="%s" target="_blank">'
            '<span class="fn">%s\\</span><span class="meta">%d 项</span></a>'
            % (url(p), html.escape(name), n)
        )
    parts.append("</div>")

    # ── 记忆与身体 ──
    parts.append("<h2>她走过的路</h2><div class='big'>")
    for name, p, desc in (
        ("今天的活动", ACTIVITY, "她今天都干了什么"),
        ("和主人的对话", CONV, "原话，按天分文件"),
        ("整间屋子", WORLD, "房间 + 日记 + 存档"),
        ("她的身体（脚本）", os.path.join(ROOT, "tools"), "让她能干活的东西"),
        ("运行日志", LOGS, "出问题先看这儿"),
        ("桌宠配置", PETS, "那只小鲸鱼"),
    ):
        if os.path.isdir(p):
            n = len(os.listdir(p))
            parts.append(
                '<a class="card" href="%s" target="_blank">'
                "<div class='n'>%d</div><div class='t'>%s</div><div class='d'>%s</div></a>"
                % (url(p), n, html.escape(name), html.escape(desc))
            )
    parts.append("</div>")

    parts.append(
        "<footer>点任意一项就会打开它　·　想刷新就再双击一次那个快捷方式</footer>"
        "</div></body></html>"
    )
    return "".join(parts)


def main():
    if not os.path.isdir(WORLD):
        say("找不到她的世界目录：" + WORLD)
        return 1
    page = build()
    try:
        with open(OUT, "w", encoding="utf-8") as f:
            f.write(page)
    except OSError as e:
        say("写文件失败：%s" % e)
        return 1
    say("已生成：%s（%d KB）" % (OUT, len(page) // 1024))

    # 这台机器 .html 没设默认打开方式，系统会弹"选择应用"——
    # 所以直接点名 Edge，最省事；实在没有才交给系统。
    for edge in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                 r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                 os.path.join(os.environ.get("LOCALAPPDATA", ""),
                              r"Microsoft\Edge\Application\msedge.exe")):
        if os.path.exists(edge):
            try:
                subprocess.Popen([edge, OUT], close_fds=True)
                return 0
            except Exception as e:
                say("Edge 没起来：%s" % e)
    try:
        os.startfile(OUT)
        return 0
    except Exception as e:
        say("startfile 不行：%s" % e)
    try:
        webbrowser.open(url(OUT))
    except Exception as e:
        say("浏览器也没打开：%s" % e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
