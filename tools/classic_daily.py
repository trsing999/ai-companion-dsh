"""每天一段古籍：《世说新语》。

一段几十个字，讲的都是真人真事——有脾气、有怪癖、有分寸。
不打打杀杀，也不替你总结。原文给你，你自己读。

用法：
    python tools/classic_daily.py          # 保证今天有一条（有了就不动）
    python tools/classic_daily.py --next   # 立刻换下一段
    python tools/classic_daily.py --fetch  # 重新抓一遍书库

产物：
    room/书/世说新语.json        抓下来的条目（不用管）
    room/书/今天读的.md          今天这一段
    room/书/世说新语·累积.md     读过的都攒在这儿
"""

import html
import json
import os
import re
import sys
import time
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WORLD = os.path.join(os.path.expanduser("~"), ".dsh", "worlds", "default")
BOOK_DIR = os.path.join(WORLD, "room", "书")
STORE = os.path.join(BOOK_DIR, "世说新语.json")
TODAY = os.path.join(BOOK_DIR, "今天读的.md")
ALL = os.path.join(BOOK_DIR, "世说新语·累积.md")

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"}

CHAPTERS = [
    ("de-xing", "德行"),
    ("yan-yu", "言语"),
    ("zheng-shi", "政事"),
    ("wen-xue", "文学"),
    ("fang-zheng", "方正"),
    ("ya-liang", "雅量"),
]
NAME2SLUG = {name: slug for slug, name in CHAPTERS}

BASE = "https://ctext.org/shi-shuo-xin-yu/{}/zh"
MIN_LEN = 12


def fetch_chapter(slug, name):
    url = BASE.format(slug)
    req = urllib.request.Request(url, headers=UA)
    raw = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    out = []
    for block in re.findall(r'<td class="ctext">([\s\S]*?)</td>', raw):
        t = re.sub(r"<[^>]+>", " ", block)
        t = html.unescape(t)
        t = re.sub(r"\s+", " ", t).strip()
        if len(t) >= MIN_LEN:
            out.append({"chapter": name, "text": t})
    return out


def build_store(verbose=True):
    os.makedirs(BOOK_DIR, exist_ok=True)
    items = []
    for slug, name in CHAPTERS:
        try:
            got = fetch_chapter(slug, name)
            items.extend(got)
            if verbose:
                print(f"  {name}: {len(got)} 条", flush=True)
        except Exception as e:
            if verbose:
                print(f"  {name}: 抓失败 {type(e).__name__}", flush=True)
        time.sleep(1)
    if items:
        with open(STORE, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=1)
    return len(items)


def load_store():
    try:
        with open(STORE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def pick(items, index):
    return items[index % len(items)] if items else None


def render(item, index, total):
    stamp = time.strftime("%Y-%m-%d %H:%M")
    slug = NAME2SLUG.get(item["chapter"], "de-xing")
    return (
        f"# 今天这一条（{stamp}）\n\n"
        f"> 《世说新语·{item['chapter']}》　第 {index % total + 1} / {total} 条\n"
        f"> [原文出处](https://ctext.org/shi-shuo-xin-yu/{slug}/zh)\n\n"
        f"---\n\n"
        f"{item['text']}\n\n"
        f"---\n\n"
        f"原文就是这样，没有翻译、没有总结。看不懂的地方留着，过几天再看可能就懂了。\n"
    )


def ensure(force_next=False, verbose=False):
    """保证今天有一条。返回 (成功, 说明)。"""
    os.makedirs(BOOK_DIR, exist_ok=True)

    if not os.path.exists(STORE):
        n = build_store(verbose=verbose)
        if not n:
            return False, "书库抓不到"

    items = load_store()
    if not items:
        return False, "书库是空的"

    today = time.strftime("%Y-%m-%d")
    idx = time.localtime().tm_yday - 1

    if os.path.exists(TODAY) and not force_next:
        try:
            with open(TODAY, encoding="utf-8-sig") as f:
                if today in f.read(200):
                    return True, "今天已经有了"
        except OSError:
            pass
        idx += 1

    item = pick(items, idx)
    if item is None:
        return False, "没得选了"

    try:
        with open(TODAY, "w", encoding="utf-8-sig") as f:
            f.write(render(item, idx, len(items)))
        if not os.path.exists(ALL):
            with open(ALL, "w", encoding="utf-8-sig") as f:
                f.write("# 世说新语·读过的\n\n")
        with open(ALL, "a", encoding="utf-8-sig") as f:
            f.write(f"\n## {today} · {item['chapter']}\n\n{item['text']}\n")
    except OSError as e:
        return False, f"写不进去：{e}"

    return True, f"{item['chapter']} 第 {idx % len(items) + 1} 条"


def main():
    args = sys.argv[1:]
    if "--fetch" in args:
        print("抓书库里……", flush=True)
        n = build_store()
        print(f"共 {n} 条", flush=True)
        return 0 if n else 1

    ok, note = ensure(force_next="--next" in args, verbose=True)
    print(("OK " if ok else "失败：") + note, flush=True)
    if ok and os.path.exists(TODAY):
        try:
            with open(TODAY, encoding="utf-8-sig") as f:
                body = f.read()
            m = re.search(r"---\n\n(.+?)\n", body, re.S)
            if m:
                print(m.group(1)[:100], flush=True)
        except OSError:
            pass
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
