"""她自己上一讲。

不用主人播放。她自己下载、自己抽帧、自己看。

用法：
    python tools/learn_video.py BV1D54y1B7HQ 4          # 湖南大学信号与系统第 4 讲
    python tools/learn_video.py BV1D54y1B7HQ 4 --every 15
    python tools/learn_video.py --browse BV1D54y1B7HQ   # 只看目录，不下

流程：
    拿播放地址（带登录态优先，不行就游客）
    → 下载这一讲
    → OpenCV 每 N 秒抽一帧
    → 存进 room/课/<标题>/P<几>/
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOME = os.path.expanduser("~")
DSH = os.path.join(HOME, ".dsh")
SESSION = os.path.join(DSH, "bili", "session.json")
WORLD = os.path.join(DSH, "worlds", "default")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(ROOT, "downloads")
COURSE_DIR = os.path.join(WORLD, "room", "课")
LOG = os.path.join(ROOT, "logs", "learn_video.log")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
MAX_W = 1280
DEFAULT_EVERY = 20

KEEP_FRAMES = 200


def log(msg):
    line = time.strftime("%H:%M:%S ") + msg
    try:
        print(line, flush=True)
    except Exception:
        pass
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d ") + line + "\n")
    except OSError:
        pass


def cookie():
    try:
        with open(SESSION, encoding="utf-8-sig") as f:
            v = (json.load(f).get("sessdata") or "").strip()
        return "SESSDATA=" + v if v else ""
    except Exception:
        return ""


def get(url, with_cookie=True):
    h = {"User-Agent": UA, "Referer": "https://www.bilibili.com/"}
    ck = cookie()
    if with_cookie and ck:
        h["Cookie"] = ck
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def view(bvid):
    j = get(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}")
    if j.get("code") != 0:
        return None
    return j.get("data") or {}


def playurl(bvid, cid, qn=32):
    for with_cookie in (True, False):
        try:
            j = get(f"https://api.bilibili.com/x/player/playurl"
                    f"?bvid={bvid}&cid={cid}&qn={qn}&fnval=1&fourk=0", with_cookie)
            if j.get("code") == 0:
                durl = ((j.get("data") or {}).get("durl") or [])
                if durl:
                    return durl[0].get("url"), durl[0].get("size")
        except Exception:
            continue
    return None, None


def download(url, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    h = {"User-Agent": UA, "Referer": "https://www.bilibili.com/"}
    req = urllib.request.Request(url, headers=h)
    total = 0
    with urllib.request.urlopen(req, timeout=60) as r, open(path, "wb") as f:
        while True:
            chunk = r.read(256 * 1024)
            if not chunk:
                break
            f.write(chunk)
            total += len(chunk)
    return total


def extract(video_path, out_dir, every=DEFAULT_EVERY):
    import cv2
    from PIL import Image

    os.makedirs(out_dir, exist_ok=True)
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        log("  OpenCV 打不开这个视频")
        return 0
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    step = max(1, int(fps * every))
    saved = 0
    idx = 0
    while idx < total and saved < KEEP_FRAMES:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if not ok:
            break
        h, w = frame.shape[:2]
        if w > MAX_W:
            s = MAX_W / w
            frame = cv2.resize(frame, (int(w * s), int(h * s)))
        sec = int(idx / fps)
        name = f"{sec//60:02d}-{sec%60:02d}.jpg"
        p = os.path.join(out_dir, name)
        Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).save(
            p, "JPEG", quality=82, optimize=True)
        saved += 1
        idx += step
    cap.release()
    return saved


def write_index(out_dir, title, page_info, n, every):
    lines = [f"# {title}", "",
             f"- 第 {page_info.get('page')} 讲：{page_info.get('part')}",
             f"- 时长 {((page_info.get('duration') or 0))//60} 分钟",
             f"- 抽了 {n} 张，每 {every} 秒一张", ""]
    files = sorted(f for f in os.listdir(out_dir) if f.endswith(".jpg"))
    for i, f in enumerate(files, 1):
        lines.append(f"{i}. `{f}`")
    lines.append("")
    with open(os.path.join(out_dir, "清单.md"), "w", encoding="utf-8-sig") as fh:
        fh.write("\n".join(lines))


def safe(name):
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()[:50]


def main():
    args = sys.argv[1:]
    every = DEFAULT_EVERY
    if "--every" in args:
        i = args.index("--every")
        if i + 1 < len(args):
            every = int(args[i + 1])
        args = args[:i] + args[i + 2:]

    # 把 -- 开头的开关全摘掉，剩下的才是「BV 号 第几讲」
    # （以前只摘了 --every，导致 `--browse BV1xx` 里 bvid 被认成 "--browse"）
    args = [a for a in args if not a.startswith("--")]

    if not args:
        print(__doc__)
        return 1

    bvid = args[0]
    data = view(bvid)
    if not data:
        log("拿不到这个视频的信息")
        return 1

    title = data.get("title") or bvid
    pages = data.get("pages") or []
    if not pages:
        log("没有分P")
        return 1

    if "--browse" in sys.argv:
        print(f"  {title}（{len(pages)} 讲）")
        for p in pages:
            print(f"   P{p.get('page')}：{(p.get('part') or '')[:50]}"
                  f"（{(p.get('duration') or 0)//60} 分钟）")
        return 0

    page_no = int(args[1]) if len(args) > 1 and args[1].isdigit() else 1
    page = next((p for p in pages if p.get("page") == page_no), pages[0])
    cid = page.get("cid")

    log(f"打算上：{title} 第 {page.get('page')} 讲 {page.get('part')}")

    url, size = playurl(bvid, cid)
    if not url:
        log("拿不到播放地址")
        return 1
    log(f"  地址拿到了，约 {(size or 0)//1024//1024} MB")

    os.makedirs(TMP, exist_ok=True)
    vid = os.path.join(TMP, f"{bvid}-{page_no}.mp4")
    try:
        got = download(url, vid)
        log(f"  下载完：{got//1024//1024} MB")
    except Exception as e:
        log(f"  下载失败：{e}")
        return 1

    out_dir = os.path.join(COURSE_DIR, safe(title), f"P{page.get('page')}")
    log("  抽帧中……")
    n = extract(vid, out_dir, every)
    if n:
        write_index(out_dir, title, page, n, every)
        log(f"  ✔ 抽了 {n} 张 → {out_dir}")
    else:
        log("  ✘ 一帧都没抽出来")

    try:
        os.remove(vid)          # 视频看完就删，省地方
    except OSError:
        pass
    return 0 if n else 1


if __name__ == "__main__":
    sys.exit(main())
