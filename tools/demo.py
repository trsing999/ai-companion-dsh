"""一键演示：30 秒看到这套东西在干什么。

不需要配置、不需要宿主、不花一分钱、不写任何文件。

    python tools/demo.py

三件小事：
  ① 量这台机器的状态（纯 ctypes，不装 psutil）
  ② 把仓库文档硬拼成一个"梦"（不调模型）
  ③ 看气泡限流的额度（跨进程文件锁）
"""

import os
import random
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)


def rule(title):
    print("\n" + "─" * 60)
    print("  " + title)
    print("─" * 60)


def main():
    print()
    print("=" * 60)
    print("  ai-companion-dsh · 演示")
    print("  下面三件事，全部零成本、零配置。")
    print("=" * 60)

    # ── ① 感知 ──
    rule("① 感知 · 她能量到这台机器累不累")
    try:
        import breath

        d = breath.read_all()
        notes, lines = breath.comments(d["cpu"], d["mem"], d["pwr"])
        for ln in lines:
            print("   " + ln)
        if notes:
            print("\n   如果她愿意，就会说：")
            for n in notes:
                print("     「" + n + "」")
        print("\n   ↑ 这一段没调模型 —— 全是 ctypes 直接问 Windows 要数")
    except Exception as e:
        print("   跳过（" + str(e)[:60] + "）")

    # ── ② 做梦 ──
    rule("② 做梦 · 把今天读到的东西硬拼在一起")
    try:
        import dream

        rng = random.Random(int(time.strftime("%Y%m%d")))
        sample = os.path.join(ROOT, "examples", "room-sample")
        pieces = dream.gather_from_dir(sample, rng) if os.path.isdir(sample) else []
        if not pieces:
            pieces = dream.gather_from_dir(os.path.join(ROOT, "docs"), rng)
        body = dream.build(rng, pieces)
        if body:
            print()
            for ln in body.splitlines():
                print("   " + ln)
            print("\n   —— 掺进去的碎片：")
            for tag, text in pieces:
                print(f"      [{tag}] {text}")
            print("\n   ↑ 全是字符串拼接。荒诞来自并置，不来自文笔。0 token")
        else:
            print("   素材不够，拼不出来")
    except Exception as e:
        print("   跳过（" + str(e)[:60] + "）")

    # ── ③ 限流 ──
    rule("③ 限流 · 气泡有额度，防止把屏幕糊住")
    try:
        import tempfile

        import bubble_gate

        # 演示用临时状态文件，别污染真实的气泡额度
        tmp = os.path.join(tempfile.gettempdir(), "demo_bubble_rate.json")
        for p in (tmp, tmp + ".lock"):
            try:
                os.remove(p)
            except OSError:
                pass
        bubble_gate.STATE = tmp
        bubble_gate.LOCK = tmp + ".lock"

        s = bubble_gate.stats()
        print(f"   规则：一分钟最多 {s['上限']} 条，同一句 90 秒内不重复")
        print(f"   现在还能说：{s['还能说']} 条")
        print("\n   试试连发三条：")
        for t in ("测试一", "测试二", "测试三"):
            ok, why = bubble_gate.allow(t)
            mark = "放行" if ok else "拦下"
            print(f"     {mark}  {t}" + ("" if ok else f"  （{why}）"))
        print("\n   ↑ 额度在放行时立刻扣掉 —— 宁可少发，不能拦不住")
    except Exception as e:
        print("   跳过（" + str(e)[:60] + "）")

    # ── 收尾 ──
    print("\n" + "=" * 60)
    print("  这三件事的共同点：**一次模型都没调**。")
    print()
    print("  想接上完整系统，需要宿主 + 配置：")
    print("    python tools/doctor.py     ← 先看你这台机器缺什么")
    print("    docs/SETUP.md             ← 从零搭建的步骤")
    print("=" * 60 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
