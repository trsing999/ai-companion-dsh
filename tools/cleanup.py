"""清理缓存：把占地方又没用的东西删掉。

只删"能重新生成"的东西——视频下载、抽帧、截图、日志。
绝不碰她的日记、画、我是谁、信。

用法：
    python tools/cleanup.py            # 按默认天数清
    python tools/cleanup.py --dry      # 只看看会删多少，不动手
"""

import os
import shutil
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOME = os.path.expanduser("~")
DSH = os.path.join(HOME, ".dsh")
ROOM = os.path.join(DSH, "worlds", "default", "room")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (路径, 保留天数, 说明, 是否整目录清空)
TARGETS = [
    (os.path.join(ROOT, "downloads"), 0, "视频下载缓存", True),
    (os.path.join(ROOM, "课"), 7, "课程抽帧", False),
    (os.path.join(ROOM, "看动漫"), 3, "动漫抽帧", False),
    (os.path.join(ROOM, "看屏幕"), 3, "屏幕截图", False),
    (os.path.join(ROOT, "logs"), 7, "日志", False),
]


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def scan():
    """返回 [(说明, 路径, 能删多少字节, 多少个文件)]"""
    now = time.time()
    out = []
    for path, days, label, wipe in TARGETS:
        if not os.path.isdir(path):
            continue
        total, count = 0, 0
        for root, dirs, files in os.walk(path):
            for f in files:
                p = os.path.join(root, f)
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                if wipe or (now - st.st_mtime) > days * 86400:
                    total += st.st_size
                    count += 1
        if count:
            out.append((label, path, total, count, days))
    return out


def do_clean(dry=False):
    items = scan()
    if not items:
        print("\n  没有需要清理的东西，很干净 ✅\n")
        return 0

    total = sum(i[2] for i in items)
    print("\n  " + "=" * 46)
    for label, path, size, count, days in items:
        rule = "全部" if days == 0 else f"{days} 天前"
        print(f"  {label:<12} {count:>5} 个文件  {human(size):>9}  （{rule}）")
    print("  " + "-" * 46)
    print(f"  合计可释放   {human(total)}")

    if dry:
        print("\n  （--dry：只是看看，没动手）\n")
        return 0

    freed = 0
    for label, path, size, count, days in items:
        now = time.time()
        for root, dirs, files in os.walk(path, topdown=False):
            for f in files:
                p = os.path.join(root, f)
                try:
                    st = os.stat(p)
                    if days == 0 or (now - st.st_mtime) > days * 86400:
                        os.remove(p)
                        freed += st.st_size
                except OSError:
                    pass
            if not days:
                try:
                    if not os.listdir(root):
                        os.rmdir(root)
                except OSError:
                    pass

    print(f"\n  ✔ 清完了，释放 {human(freed)}\n")
    return 0


def main():
    return do_clean(dry="--dry" in sys.argv)


if __name__ == "__main__":
    sys.exit(main())
