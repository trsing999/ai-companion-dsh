"""world 网关：让琛琛的"大脑"变成 dsh-world。

两个面：
1. OpenAI 兼容入口  POST /v1/chat/completions
   琛琛的 chat provider 指向这里；它发来的最后一条 user 消息
   经 /dsh-world/bridge/say 送进 world，等 world 的回复，再按 OpenAI 格式回给琛琛。
2. 推送接收口  POST /push
   world 的 outlets 把 reply / busy / reach 推到这里，存进队列配对给等待中的请求。

bridge token 从 <world>/bridge.json 读取（world 启动时生成）。
"""

import json
import os
import queue
import sys
import threading
import time
import urllib.error
import urllib.request
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WORLD = os.path.join(os.environ["USERPROFILE"], ".dsh", "worlds", "default")
BRIDGE_FILE = os.path.join(WORLD, "bridge.json")
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs", "world_gateway.log")
PORT = 18761
DSH_PORTS = [12761, 5222, 33977, 17474, 3080, 38080]
WAIT_SECONDS = 120

_replies = queue.Queue()
_lock = threading.Lock()


def log(msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def bridge_info():
    try:
        raw = open(BRIDGE_FILE, encoding="utf-8").read()
        return json.loads(raw)
    except (OSError, ValueError):
        return None


def dsh_port():
    # 1) 最可靠：world 自己在 bridge.json 里写了当前 DSH 的 origin
    info = bridge_info() or {}
    origin = str(info.get("origin") or "")
    if origin.startswith("http://") or origin.startswith("https://"):
        try:
            from urllib.parse import urlsplit

            port = urlsplit(origin).port
            if port:
                return int(port)
        except Exception:
            pass
    # 2) 已知端口
    for port in DSH_PORTS:
        try:
            urllib.request.urlopen("http://127.0.0.1:%d/" % port, timeout=0.3)
            return port
        except urllib.error.HTTPError:
            return port
        except Exception:
            continue
    # 3) netstat 枚举本机监听端口，找带 dsh-world 路由的那个
    try:
        out = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout
        cands = []
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[3] == "LISTENING" and parts[1].startswith("127.0.0.1:"):
                try:
                    cands.append(int(parts[1].rsplit(":", 1)[1]))
                except ValueError:
                    pass
        for port in cands:
            try:
                urllib.request.urlopen(
                    "http://127.0.0.1:%d/dsh-world/bridge/say" % port, timeout=0.4
                )
            except urllib.error.HTTPError as e:
                if e.code in (403, 405):
                    return port
            except Exception:
                continue
    except Exception:
        pass
    return None


def say_to_world(text):
    """把话送进 world；成功返回 id，失败返回 (None, 原因)。"""
    info = bridge_info()
    if not info:
        return None, "bridge.json 不存在（world 的 bridge 未启用或世界没在运行）"
    port = dsh_port()
    if not port:
        return None, "找不到 DSH 端口"
    body = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:%d/dsh-world/bridge/say" % port,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "x-dsh-world-token": info.get("token", ""),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            payload = json.loads(r.read() or b"{}")
        return payload.get("id"), None
    except urllib.error.HTTPError as e:
        return None, "HTTP %d %s" % (e.code, e.read().decode("utf-8", "replace")[:120])
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, str(e)[:80])


def wait_reply(timeout=WAIT_SECONDS):
    try:
        return _replies.get(timeout=timeout)
    except queue.Empty:
        return None


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _send(self, code, obj, ctype="application/json"):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8") if not isinstance(obj, bytes) else obj
        self.send_response(code)
        self.send_header("content-type", ctype)
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        path = self.path.split("?")[0].rstrip("/")
        try:
            n = int(self.headers.get("content-length") or 0)
            raw = self.rfile.read(n) if n else b"{}"
        except Exception:
            raw = b"{}"

        if path == "/push":
            try:
                data = json.loads(raw or b"{}")
            except ValueError:
                data = {}
            text = (data.get("text") or "").strip()
            kind = data.get("kind") or "reply"
            if text:
                log("outlet %s: %s" % (kind, text[:60]))
                _replies.put({"text": text, "kind": kind})
            self._send(200, {"ok": True})
            return

        if path.endswith("/chat/completions"):
            try:
                req = json.loads(raw or b"{}")
            except ValueError:
                self._send(400, {"error": {"message": "invalid json"}})
                return
            msgs = req.get("messages") or []
            last_user = ""
            for m in reversed(msgs):
                if m.get("role") == "user":
                    last_user = (m.get("content") or "").strip()
                    break
            if not last_user:
                last_user = "（主人在看你，没说话）"
            # 清掉可能残留的旧回复
            while True:
                try:
                    _replies.get_nowait()
                except queue.Empty:
                    break
            sid, err = say_to_world(last_user)
            if err:
                log("say failed: %s" % err)
                self._send(200, self._completion("（我现在接不上我的世界：%s）" % err, req))
                return
            log("say -> world id=%s" % sid)
            reply = wait_reply()
            if not reply:
                text = "（我在房间里忙，没顾上回你）"
                log("reply timeout")
            else:
                text = reply["text"]
                log("reply <- %s: %s" % (reply.get("kind"), text[:60]))
            if req.get("stream"):
                self._send_stream(text, req)
            else:
                self._send(200, self._completion(text, req))
            return

        self._send(404, {"error": {"message": "not found"}})

    def do_GET(self):
        if self.path.rstrip("/") in ("/health", "/v1/models"):
            self._send(200, {"ok": True, "bridge": bool(bridge_info())})
        else:
            self._send(404, {"error": {"message": "not found"}})

    @staticmethod
    def _completion(text, req):
        return {
            "id": "chatcmpl-world",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": req.get("model") or "world",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

    def _send_stream(self, text, req):
        self.send_response(200)
        self.send_header("content-type", "text/event-stream; charset=utf-8")
        self.send_header("cache-control", "no-cache")
        self.send_header("connection", "close")
        self.end_headers()
        base = {
            "id": "chatcmpl-world",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": req.get("model") or "world",
        }
        for piece in (text[i : i + 24] for i in range(0, len(text), 24)):
            chunk = dict(base)
            chunk["choices"] = [{"index": 0, "delta": {"content": piece}, "finish_reason": None}]
            self.wfile.write(("data: " + json.dumps(chunk, ensure_ascii=False) + "\n\n").encode("utf-8"))
            self.wfile.flush()
        end = dict(base)
        end["choices"] = [{"index": 0, "delta": {}, "finish_reason": "stop"}]
        self.wfile.write(("data: " + json.dumps(end, ensure_ascii=False) + "\n\n").encode("utf-8"))
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()


def main():
    info = bridge_info()
    log("start; bridge=%s; dsh port=%s" % ("ok" if info else "MISSING", dsh_port()))
    if not info:
        log("提示：world 的 bridge 未启用，需要改 profile 配置并重启 DSH")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
