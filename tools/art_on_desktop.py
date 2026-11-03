"""把她的画浮到桌面。

规则（主人定的）：
    - 有新画 → 自己浮出来
    - 你点一下 → 关上，**这张就不再出来了**
    - 只有她画出**新的**一张，才会再浮出来
    - 右键 → 想再看一眼、或者干脆关掉程序

所以它是"等她画新的"这种性质，不是一直挂在屏幕上。
记住哪张看过：logs/art_seen.json

用法：
    python tools/art_on_desktop.py            # 常驻，每分钟看一眼有没有新画
    python tools/art_on_desktop.py 某个.png    # 只显示指定的图
    python tools/art_on_desktop.py --again    # 不管看过没看过，现在先给主人看一眼
    python tools/art_on_desktop.py --once     # 显示一下就退出（调试用）
"""

import json
import os
import sys
import time
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import memory
except Exception:
    memory = None

HOME = os.path.expanduser("~")
ROOM = os.path.join(HOME, ".dsh", "worlds", "default", "room")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "logs", "art_on_desktop.log")
SEEN = os.path.join(ROOT, "logs", "art_seen.json")

# 她自己的画（排除截图和色卡这些工具产物）
SKIP = ("屏幕", "色卡", "热键-", "printwindow", "看动漫")
MAX_W = 420
REFRESH = 60          # 秒，多久看一眼有没有新画


def log(msg):
    """pythonw 下 stdout 是 None，print 会炸；同时写文件方便排查。"""
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


def seen_load():
    try:
        with open(SEEN, encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict):
            return d
    except Exception:
        pass
    return {}


def seen_save(d):
    try:
        os.makedirs(os.path.dirname(SEEN), exist_ok=True)
        with open(SEEN, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    except OSError:
        pass


def mark_seen(path):
    try:
        d = seen_load()
        d["path"] = path
        d["mtime"] = os.path.getmtime(path)
        d["at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        seen_save(d)
    except OSError:
        pass


def is_new(path):
    """这张画我还没给主人看过？——按"路径 + 修改时间"认。"""
    if not path:
        return False
    try:
        m = os.path.getmtime(path)
    except OSError:
        return False
    d = seen_load()
    if d.get("path") != path:
        return True
    try:
        return abs(float(d.get("mtime") or 0) - m) >= 1
    except (TypeError, ValueError):
        return True


def latest_art():
    best = None
    try:
        for f in os.listdir(ROOM):
            if not f.lower().endswith((".png", ".jpg", ".jpeg")):
                continue
            if any(s in f for s in SKIP):
                continue
            p = os.path.join(ROOM, f)
            if not os.path.isfile(p):
                continue
            m = os.path.getmtime(p)
            if best is None or m > best[0]:
                best = (m, p)
    except OSError:
        pass
    return best[1] if best else None


def run(fixed_path=None, once=False, again=False):
    from PIL import Image, ImageTk

    root = tk.Tk()
    root.overrideredirect(True)          # 无边框
    root.attributes("-topmost", True)    # 置顶
    root.configure(bg="#101014")         # 图会铺满，这个底基本看不见
    root.withdraw()                      # 先藏着，有画才露头

    label = tk.Label(root, bg="#101014", bd=0)
    label.pack()

    state = {"path": None, "img": None, "shown": False}

    def place(w, h):
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        root.geometry(f"{w}x{h}+{sw - w - 40}+{sh - h - 120}")

    def load(p):
        img = Image.open(p).convert("RGB")
        w, h = img.size
        if w > MAX_W:
            s = MAX_W / w
            img = img.resize((max(1, int(w * s)), max(1, int(h * s))))
        return img

    def put_on_screen(p):
        img = load(p)
        tkimg = ImageTk.PhotoImage(img)
        label.configure(image=tkimg)
        label.image = tkimg
        state["img"] = tkimg
        state["path"] = p
        place(*img.size)
        root.deiconify()
        root.lift()
        try:
            root.attributes("-topmost", True)
        except Exception:
            pass
        state["shown"] = True
        log(f"  浮出来了：{os.path.basename(p)}（{img.size[0]}x{img.size[1]}）")

    def close_art(_=None):
        """点一下：关上，这张就到此为止，等她画新的。"""
        if not state["shown"]:
            return
        root.withdraw()
        state["shown"] = False
        if state["path"]:
            mark_seen(state["path"])
            try:
                memory.note("art", f"主人看了《{os.path.basename(state['path'])}》，收起来了。")
            except Exception:
                pass
        log("  收起来了——这张看过就不打扰了，等她画新的")
        return "break"

    def bring_back():
        if state["path"] and os.path.exists(state["path"]):
            put_on_screen(state["path"])
        else:
            p = latest_art()
            if p:
                put_on_screen(p)
            else:
                log("  房间里还没有画")

    def menu(event):
        m = tk.Menu(root, tearoff=0)
        m.add_command(label="再看一眼这张", command=bring_back)
        m.add_command(label="关上（等新的再说）", command=close_art)
        m.add_separator()
        m.add_command(label="关掉这个浮画（程序退出）", command=root.destroy)
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()
        return "break"

    def tick():
        """每分钟看一眼：有新画就浮出来。"""
        p = fixed_path or latest_art()
        if p and not state["shown"] and is_new(p):
            try:
                put_on_screen(p)
                mark_seen(p)
            except Exception as e:
                log(f"  这张没打开：{e}")
        if not once:
            root.after(REFRESH * 1000, tick)

    root.bind("<Button-1>", close_art)
    root.bind("<Button-3>", menu)
    root.bind("<Escape>", close_art)
    label.bind("<Button-3>", menu)

    log("== 浮画上线 ==")

    # 启动时：有新的就浮出来；没有就安静等着
    p = fixed_path or latest_art()
    if p and (again or fixed_path or is_new(p)):
        try:
            put_on_screen(p)
            mark_seen(p)
        except Exception as e:
            log(f"  这张没打开：{e}")
    elif p:
        log(f"  最新一张已经看过了，安静等着（{os.path.basename(p)}）")
    else:
        log("  房间里还没有画，等着")

    if once:
        root.after(1500, root.destroy)

    root.after(REFRESH * 1000, tick)
    root.mainloop()
    log("== 浮画下线 ==")
    return 0


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    once = "--once" in sys.argv
    again = "--again" in sys.argv
    path = args[0] if args else None
    if path and not os.path.exists(path):
        log(f"  找不到这张图：{path}")
        return 1
    return run(fixed_path=path, once=once, again=again)


if __name__ == "__main__":
    sys.exit(main())
