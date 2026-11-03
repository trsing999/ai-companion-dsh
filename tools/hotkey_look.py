"""全局热键：Ctrl+Alt+L —— 让她看一眼屏幕。

按下 → 截屏 + 本地 OCR → 写 room/屏幕文字.md → 弹一条通知
（不截屏时 CPU 为 0；热键被占用会明确报错）
"""

import ctypes
import ctypes.wintypes as wintypes
import os
import subprocess
import sys
import threading
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
SCREEN = os.path.join(HERE, "look_screen_ocr.py")
LOG = os.path.join(HERE, "..", "logs", "hotkey_look.log")

MOD_ALT = 0x0001
MOD_SHIFT = 0x0004
MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000
VK_L = 0x4C
HOTKEY_ID = 1
WM_HOTKEY = 0x0312

_busy = threading.Lock()


def log(msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def capture_async():
    if not _busy.acquire(blocking=False):
        log("still running, skip")
        return

    def work():
        try:
            start = time.time()
            proc = subprocess.run(
                [PY, SCREEN],
                capture_output=True,
                timeout=120,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            out = (proc.stdout or b"").decode("utf-8", "replace").strip()
            err = (proc.stderr or b"").decode("utf-8", "replace").strip()
            ok = proc.returncode == 0
            log("capture rc=%s %.1fs %s%s" % (proc.returncode, time.time() - start, out[:60], (" | " + err[:80]) if err else ""))
            try:
                from win_toast import toast

                if ok:
                    toast("琛琛", "看过了，屏幕上的字都收进房间了")
                else:
                    toast("琛琛", "这次没看清：" + (err[:60] or "OCR 失败"))
            except Exception as e:
                log("toast failed: %s" % e)
        finally:
            _busy.release()

    threading.Thread(target=work, daemon=True).start()


def main():
    user32 = ctypes.windll.user32
    ok = user32.RegisterHotKey(None, HOTKEY_ID, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, VK_L)
    if not ok:
        log("注册失败：Ctrl+Alt+L 可能已被别的程序占用（错误码 %d）" % ctypes.get_last_error())
        sys.exit(1)
    log("热键已就绪：Ctrl+Alt+L")
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
            log("hotkey pressed")
            capture_async()
    user32.UnregisterHotKey(None, HOTKEY_ID)


if __name__ == "__main__":
    main()
