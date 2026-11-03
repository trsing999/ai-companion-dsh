"""让她看一眼屏幕：截屏 + 本地 OCR 提取文字（离线，不调用视觉模型）。

产物：
  <world>/room/屏幕.png       原分辨率截图（她自己也能 read_image，但模型无视觉）
  <world>/room/屏幕文字.md    屏幕上的文字，按行整理，带时间戳
"""

import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
WORLD = os.path.join(os.path.expanduser("~"), ".dsh", "worlds", "default")
ROOM = os.path.join(WORLD, "room")
SHOT = os.path.join(ROOM, "屏幕.png")
TEXT = os.path.join(ROOM, "屏幕文字.md")
OCR = os.path.join(HERE, "ocr.ps1")
LOG = os.path.join(HERE, "..", "logs", "look_screen.log")


def log(msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def capture():
    from PIL import ImageGrab

    img = ImageGrab.grab(all_screens=True)
    os.makedirs(ROOM, exist_ok=True)
    img.save(SHOT, "PNG")
    log("shot %dx%d -> %s" % (img.size[0], img.size[1], SHOT))
    return SHOT


def ocr(path):
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", OCR, "-Path", path],
            capture_output=True,
            timeout=90,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, e)
    out = (proc.stdout or b"").decode("utf-8", "replace").strip()
    if not out:
        err = (proc.stderr or b"").decode("utf-8", "replace").strip()
        return None, err[:200] or "OCR 没有返回内容"
    return out, None


def write_note(text, err=None):
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    lines = ["# 主人屏幕上的文字（%s）" % now, ""]
    if err:
        lines += ["> 这次没读到：%s" % err, ""]
    else:
        lines.append("这是我从主人屏幕截图里认出来的字（本地 OCR，没有联网、没有发给任何人）。")
        lines.append("顺序是画面上的行，可能有点乱，也可能认错字。")
        lines.append("")
        for raw in text.splitlines():
            t = raw.strip()
            if t:
                lines.append("- " + t)
    tmp = TEXT + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(tmp, TEXT)
    log("wrote %s (%d lines)" % (TEXT, len([l for l in text.splitlines() if l.strip()])))


def main():
    shot = capture()
    text, err = ocr(shot)
    write_note(text or "", err)
    if err:
        print("OCR failed:", err)
        return 1
    print("OK lines:", len([l for l in text.splitlines() if l.strip()]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
