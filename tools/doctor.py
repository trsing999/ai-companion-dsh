"""环境自检：这台机器上，哪些能跑，哪些还缺东西。

新克隆下来先跑这个，别急着启动服务。

    python tools/doctor.py

它会告诉你三件事：
  ✓ 现在就能跑的（零配置、零成本）
  ○ 改一下配置就能跑的
  ✗ 跑不了的（缺宿主或依赖）

退出码：0 = 至少有一个能跑；1 = 环境太缺，先补依赖
"""

import importlib
import json
import os
import platform
import shutil
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOME = os.path.expanduser("~")
DSH = os.path.join(HOME, ".dsh")
ROOM = os.path.join(DSH, "worlds", "default", "room")
BRIDGE = os.path.join(DSH, "worlds", "default", "bridge.json")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

OK, MAYBE, NO = "✓", "○", "✗"


def line(mark, name, note=""):
    print(f"  {mark} {name}" + (f"  —  {note}" if note else ""))


def has(mod):
    try:
        importlib.import_module(mod)
        return True
    except Exception:
        return False


def main():
    print()
    print("=" * 62)
    print("  ai-companion-dsh  环境自检")
    print("=" * 62)

    ready, need_cfg, blocked = [], [], []

    # ── 基础环境 ──
    print("\n【基础环境】")
    py = sys.version_info
    tag = f"Python {py.major}.{py.minor}.{py.micro}"
    if py >= (3, 9):
        line(OK, tag)
    else:
        line(NO, tag, "需要 3.9 或更高")
        blocked.append("Python 版本太低")

    win = platform.system() == "Windows"
    line(OK if win else MAYBE, f"平台 {platform.system()}",
         "" if win else "大部分功能用了 Win32 API，非 Windows 需要重写")

    pil = has("PIL")
    cv2 = has("cv2")
    line(OK if pil else MAYBE, "Pillow（截图/图像）",
         "" if pil else "pip install Pillow")
    line(OK if cv2 else MAYBE, "opencv-python（视频抽帧）",
         "" if cv2 else "pip install opencv-python（只在看课时需要）")

    # ── 宿主 ──
    print("\n【宿主 dsh-world】")
    if os.path.isdir(os.path.join(DSH, "worlds", "default")):
        line(OK, f"找到世界目录 {os.path.join(DSH, 'worlds', 'default')}")
        if os.path.exists(BRIDGE):
            try:
                with open(BRIDGE, encoding="utf-8-sig") as f:
                    b = json.load(f)
                line(OK, "bridge.json 正常", f"origin={b.get('origin')}")
                host = True
            except Exception as e:
                line(MAYBE, "bridge.json 读不了", str(e)[:40])
                host = False
        else:
            line(MAYBE, "没有 bridge.json", "宿主没起来，或者没开 bridge")
            host = False
    else:
        line(NO, "没有 ~/.dsh/worlds/default", "没装宿主，人格层跑不起来")
        host = False
        blocked.append("缺 dsh-world 宿主")

    if os.path.isdir(ROOM):
        n = len([x for x in os.listdir(ROOM) if x.endswith('.md')])
        line(OK, f"房间有 {n} 个 markdown")
    else:
        line(MAYBE, "没有房间目录", "梦境/记忆类脚本要用它当素材")

    # ── 可选配置 ──
    print("\n【可选配置】（没有也能跑别的）")
    for f, desc in (
        ("mobile_push.json", "手机推送"),
        ("email_bridge.json", "邮件收发"),
        ("mobile_approval.json", "手机审批"),
        (os.path.join("bili", "session.json"), "B 站登录态（看课用）"),
    ):
        p = os.path.join(DSH, f)
        if os.path.exists(p):
            line(OK, desc)
        else:
            line(MAYBE, desc, "没配，相关功能跳过")

    # ── 分类结论 ──
    print("\n" + "─" * 62)
    print("【结论】")

    if pil:
        ready += ["breath.py 读硬件", "bubble_gate.py 看气泡额度", "cleanup.py 清缓存"]
    if os.path.isdir(ROOM):
        ready += ["dream.py 拼一个梦", "memory.py 记一条事实"]
    ready += ["doctor.py（就是本文件）", "demo.py 一键演示"]

    if pil and os.path.isdir(ROOM):
        need_cfg += ["her_home_index.py 索引页"]

    if host:
        ready += ["world_gateway.py", "world_to_pet.py", "inbox_watcher.py"]
    else:
        blocked += ["world_gateway.py 等全部桥接脚本（需要宿主）"]

    if cv2 and os.path.exists(os.path.join(DSH, "bili", "session.json")):
        need_cfg += ["learn_video.py 自助看课"]
    elif cv2:
        maybe = "learn_video.py（装好了 cv2，但没 B 站登录态）"
        need_cfg.append(maybe)

    print("\n  现在就能跑：")
    for x in ready:
        print(f"     ✓ {x}")
    if need_cfg:
        print("\n  改一下配置就能跑：")
        for x in need_cfg:
            print(f"     ○ {x}")
    if blocked:
        print("\n  跑不了（缺东西）：")
        for x in blocked:
            print(f"     ✗ {x}")

    print("\n" + "=" * 62)
    if ready:
        print("  下一步： python tools/demo.py")
        print("  它会用零成本的方式，让你看到这套东西在干什么。")
        print("=" * 62 + "\n")
        return 0
    print("  先补依赖： pip install -r requirements.txt")
    print("=" * 62 + "\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
