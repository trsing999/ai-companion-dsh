"""把她说的话转进深深的气泡。

dsh-world 的 outlets 会把她的回复 POST 过来，这里转一手，
塞进 dsh-pet 的 broadcast —— 于是不管主人开着什么窗口，都能看见她说话。

监听：127.0.0.1:18762/push
上游：cordis.patch.yml 里 dsh-world 的 outlets 多一条指向这里
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bubble_gate

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOME = os.path.expanduser("~")
DSH = os.path.join(HOME, ".dsh")
WORLD = os.path.join(DSH, "worlds", "default")
BRIDGE = os.path.join(WORLD, "bridge.json")
CONFIG = os.path.join(DSH, "dsh-pet", "main-config.jsonc")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "logs", "world_to_pet.log")

PORT = 18762
PET_ID = "main"
MAX_CHARS = 300          # 气泡太长了看不清，截一下


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


def origin():
    try:
        with open(BRIDGE, encoding="utf-8-sig") as f:
            return str(json.load(f).get("origin", "")).rstrip("/")
    except Exception:
        return os.environ.get("DSH_WEB_URL", "http://127.0.0.1:14077").rstrip("/")


def surface():
    try:
        with open(CONFIG, encoding="utf-8-sig") as f:
            d = str((json.load(f).get("pets") or [{}])[0].get("display", "web"))
        return d if d in ("web", "desktop", "both") else "web"
    except Exception:
        return "web"


def _post_bubble(text, seconds=12):
    surf = surface()
    body = json.dumps({"text": text, "duration": seconds, "surface": surf},
                      ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        origin() + f"/dsh-pet-7340/broadcast?pet={PET_ID}&surface={surf}",
        data=body, method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return 200 <= r.status < 300
    except Exception as e:
        log(f"  气泡失败: {e}")
        return False


def bubble(text, seconds=12, force=False):
    """过限流这一关再发——见 bubble_gate。"""
    ok, why = bubble_gate.allow(text, force=force)
    if not ok:
        log(f"  气泡被拦：{why}　（{clean(text)[:30]}）")
        return False
    sent = _post_bubble(text, seconds)
    if sent:
        bubble_gate.done(text)
    return sent


def clean(text):
    t = " ".join(str(text).split())
    if len(t) > MAX_CHARS:
        t = t[:MAX_CHARS] + "…"
    return t


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass          # 别把每个请求都打到日志里

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b""
            try:
                data = json.loads(raw.decode("utf-8", "replace") or "{}")
            except Exception:
                data = {"text": raw.decode("utf-8", "replace")}

            kind = str(data.get("kind") or "")
            text = data.get("text") or data.get("message") or ""

            if text and kind in ("reply", "reach", ""):
                if bubble(clean(text)):
                    log(f"  {kind or 'text'} → 气泡 OK: {clean(text)[:40]}")
                # 被限流的话，bubble() 里已经记过原因了，这里不再重复报"失败"
            elif kind:
                log(f"  跳过 kind={kind}")
        except Exception as e:
            log(f"  处理出错: {e}")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    log(f"== 转接上线：127.0.0.1:{PORT}/push → 深深气泡 ==")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        log("== 转接下线 ==")


if __name__ == "__main__":
    main()
