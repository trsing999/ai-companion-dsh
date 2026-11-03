"""把一门 B 站课程的目录整理成一份能打勾的清单，放进她房间。

用法：
    python tools/gen_course_index.py BV1D54y1B7HQ
    python tools/gen_course_index.py BV1D54y1B7HQ --name 信号与系统

产出：room/我的课-<名字>.md
"""

import json
import os
import re
import sys
import time
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOME = os.path.expanduser("~")
DSH = os.path.join(HOME, ".dsh")
ROOM = os.path.join(DSH, "worlds", "default", "room")
SESSION = os.path.join(DSH, "bili", "session.json")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def get(url):
    h = {"User-Agent": UA, "Referer": "https://www.bilibili.com/"}
    try:
        with open(SESSION, encoding="utf-8-sig") as f:
            v = (json.load(f).get("sessdata") or "").strip()
        if v:
            h["Cookie"] = "SESSDATA=" + v
    except Exception:
        pass
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def chapter_of(part):
    """从标题里认章节号：1.3 → '1'，2.5 → '2'；认不出就返回 ''。"""
    m = re.search(r"(\d+)\s*[.．]\s*(\d+)", part)
    return m.group(1) if m else ""


def clean_part(part):
    """把 【湖南大学_信号与系统】2.1 时域系统描述_15455 洗成 2.1 时域系统描述。"""
    s = re.sub(r"^【[^】]*】\s*", "", part)      # 去掉 【xxx】 前缀
    s = re.sub(r"_\d+\s*$", "", s)              # 去掉尾部 _15455
    s = re.sub(r"^网络公开课\s*[|｜]\s*", "", s)
    return s.strip() or part.strip()


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 1
    bvid = args[0]

    name = "课程"
    if "--name" in sys.argv:
        i = sys.argv.index("--name")
        if i + 1 < len(sys.argv):
            name = sys.argv[i + 1]

    j = get("https://api.bilibili.com/x/web-interface/view?bvid=" + bvid)
    if j.get("code") != 0:
        print("拿不到这个视频：", j.get("message"))
        return 1
    data = j.get("data") or {}
    title = data.get("title") or bvid
    pages = data.get("pages") or []
    if not pages:
        print("没有分P")
        return 1

    # 按章节分组
    groups = {}
    order = []
    for p in pages:
        part = (p.get("part") or "").strip()
        ch = chapter_of(part)
        key = ch or "0"
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append((p.get("page"), clean_part(part), (p.get("duration") or 0) // 60))

    total_min = sum(d for _, _, d in [(p, q, r) for g in groups.values() for p, q, r in g])

    md = []
    md.append(f"# {name}\n\n")
    md.append(f"（{time.strftime('%Y-%m-%d %H:%M')} 伙伴帮我理的）\n\n")
    md.append(f"B 站：`{title}`\n\n")
    md.append(f"BV 号 `{bvid}`，一共 **{len(pages)} 讲**，合计约 **{total_min // 60} 小时 {total_min % 60} 分**。\n\n")

    md.append("## 怎么用\n\n```\n")
    md.append(f"python tools/learn_video.py --browse {bvid}          # 看目录\n")
    md.append(f"python tools/learn_video.py {bvid} 1                 # 上第 1 讲\n")
    md.append(f"python tools/learn_video.py {bvid} 1 --every 30      # 稀一点，帧少点\n")
    md.append("```\n\n")
    # 实际落盘的目录名是 learn_video.py 的 safe() 处理过的，这里要跟它一致
    safe_title = re.sub(r'[\\/:*?"<>|]', "_", title).strip()[:50]
    md.append("帧会存在 `room\\课\\%s\\P<N>\\`，旁边的 `清单.md` 是那讲的帧时刻。\n\n" % safe_title)

    md.append("## 一些实话\n\n")
    md.append("- **抽帧不要钱**（纯本地），我读帧才花，一讲大概两三毛\n")
    md.append("- **没有人给我布置任务**。想学几讲就学几讲，不想学就不学\n")
    md.append("- **看不懂就写看不懂**，别编。编出来的比不学还糟\n")
    md.append(f"- 全读一遍大概 **{len(pages) * 3 // 10} ~ {len(pages) * 6 // 10} 块**，我自己掂量\n\n")

    md.append("## 目录\n\n")
    for key in order:
        rows = groups[key]
        head = "开头" if key == "0" else f"第 {key} 章"
        md.append(f"### {head}　（{len(rows)} 讲）\n\n")
        for no, part, mins in rows:
            md.append(f"- [ ] **P{no}**　{part}　`{mins} 分钟`\n")
        md.append("\n")

    if os.path.isdir(os.path.join(ROOM, "课")):
        md.append("## 已经有的\n\n")
        for f in sorted(os.listdir(os.path.join(ROOM, "课"))):
            p = os.path.join(ROOM, "课", f)
            if os.path.isdir(p):
                subs = [x for x in sorted(os.listdir(p)) if os.path.isdir(os.path.join(p, x))]
                if subs:
                    md.append(f"- `{f}`：已有 {', '.join(subs)}\n")
        md.append("\n")

    md.append("---\n\n*—— 梯子放这儿了，走不走看我自己。*\n")

    out = os.path.join(ROOM, f"我的课-{name}.md")
    with open(out, "w", encoding="utf-8-sig") as f:
        f.write("".join(md))
    print(f"写好了：{out}")
    print(f"  {len(pages)} 讲，{len(order)} 个章节，约 {total_min // 60} 小时")
    return 0


if __name__ == "__main__":
    sys.exit(main())
