"""开一扇窗：看一眼主人现在的屏幕。

**按需**——她什么时候想看，什么时候调一次。
不定时、不录屏、不推送、不总结。看到什么就是什么。

用法：
    python tools/peek.py            # 看一眼
    python tools/peek.py --force    # 就算当前是敏感窗口也看（她自己负责）

产物：
    room/看屏幕/2026-11-03-1230.png    原分辨率截图
    room/看屏幕/2026-11-03-1230.md     OCR 认出来的文字，敏感内容已打码
    room/看屏幕/最近.md                最新的一份，直接读这个就行

三道闸：
    1. 当前活动窗口命中敏感名单 → 整张跳过，不存（除非 --force）
    2. OCR 文字里含验证码/密码/身份证/卡号的整行 → 替换成 [已打码]
    3. 只保留最近 3 天，旧的自动清掉
"""

import ctypes
import os
import re
import subprocess
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
WORLD = os.path.join(os.path.expanduser("~"), ".dsh", "worlds", "default")
OUT_DIR = os.path.join(WORLD, "room", "看屏幕")
LATEST = os.path.join(OUT_DIR, "最近.md")
OCR_PS1 = os.path.join(HERE, "ocr.ps1")

KEEP_DAYS = 3

# 这些窗口开着的时候，整张跳过，连存都不存
SENSITIVE_TITLES = (
    "微信", "WeChat", "企业微信", "QQ", "TIM",
    "密码", "登录", "验证",
    "银行", "支付宝", "Alipay", "网上银行", "付款",
    "Lock", "锁屏", "安全中心",
    "密码本", "KeePass", "1Password", "Bitwarden",
)

# 命中这些词的行，整行打码
SENSITIVE_LINE_WORDS = (
    "验证码", "密码", "身份证", "银行卡", "卡号",
    "支付密码", "动态码", "短信码", "校验码",
)

# 单独出现也要盖掉的内容
PATTERNS = [
    (re.compile(r"\b1[3-9]\d{9}\b"), "[手机号已打码]"),
    (re.compile(r"\b\d{17}[\dXx]\b"), "[身份证已打码]"),
    (re.compile(r"\b\d{16,19}\b"), "[卡号已打码]"),
    (re.compile(r"\b\d{6}\b"), None),      # 6 位数字：只在敏感行里盖，见 mask()
]


def log(msg):
    print(msg, flush=True)


def active_window_title():
    """当前前台窗口的标题。拿不到就返回空串。"""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        n = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        return buf.value.strip()
    except Exception:
        return ""


def mask(text):
    """把文字里的敏感东西盖掉。"""
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if any(w in s for w in SENSITIVE_LINE_WORDS):
            out.append("[这行涉及敏感信息，已打码]")
            continue
        for pat, repl in PATTERNS:
            if repl is None:
                continue
            s = pat.sub(repl, s)
        out.append(s)
    return out


def capture(path):
    from PIL import ImageGrab
    img = ImageGrab.grab(all_screens=True)
    img.convert("RGB").save(path, "PNG")
    return img.size


def ocr(path):
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", OCR_PS1, "-Path", path],
            capture_output=True, timeout=90,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"
    out = (proc.stdout or b"").decode("utf-8", "replace").strip()
    if not out:
        err = (proc.stderr or b"").decode("utf-8", "replace").strip()
        return None, err[:200] or "OCR 没有返回内容"
    return out, None


def cleanup():
    """只留最近几天。"""
    cutoff = time.time() - KEEP_DAYS * 86400
    try:
        for f in os.listdir(OUT_DIR):
            p = os.path.join(OUT_DIR, f)
            if os.path.isfile(p) and os.path.getmtime(p) < cutoff:
                try:
                    os.remove(p)
                except OSError:
                    pass
    except OSError:
        pass


def main():
    force = "--force" in sys.argv
    os.makedirs(OUT_DIR, exist_ok=True)

    title = active_window_title()
    if title and not force:
        hit = next((w for w in SENSITIVE_TITLES if w in title), None)
        if hit:
            log(f"窗关着呢：当前窗口「{title}」里有敏感的东西（{hit}），这就不看了。")
            log("（真想看的话加 --force，但有的话我看了也不会说。）")
            return 0

    stamp = time.strftime("%Y-%m-%d-%H%M")
    png = os.path.join(OUT_DIR, stamp + ".png")
    md = os.path.join(OUT_DIR, stamp + ".md")

    size = capture(png)
    log(f"拍下来了：{size[0]}×{size[1]}  {os.path.basename(png)}")

    text, err = ocr(png)
    now = time.strftime("%Y-%m-%d %H:%M:%S")

    lines = [f"# 主人屏幕上的字（{now}）", ""]
    if title:
        lines.append(f"> 当时窗口：{title}")
    lines.append("")
    if err:
        lines += [f"> OCR 这次没读出来：{err}", ""]
    else:
        lines.append("本地 OCR，离线跑的，没发给任何人。顺序是画面上的行，可能认错字。")
        lines.append("")
        for s in mask(text or ""):
            lines.append("- " + s)

    body = "\n".join(lines) + "\n"
    with open(md, "w", encoding="utf-8-sig") as f:
        f.write(body)
    with open(LATEST, "w", encoding="utf-8-sig") as f:
        f.write(body)

    cleanup()
    log(f"文字存好了：{os.path.basename(md)}")
    log(f"最新的那份在：{LATEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
