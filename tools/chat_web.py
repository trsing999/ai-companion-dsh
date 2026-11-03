"""给琛琛开一个网页聊天入口（局域网可用，带防护）。

防护：
- 32 字符随机口令（URL 参数 ?k= 或 Cookie）
- 同一 IP 口令连错 5 次 → 封 10 分钟
- 每 IP 每分钟最多 20 条消息（防刷额度）
- 可选 IP 白名单（配置 allowed_ips，留空=不限制）
- 请求体上限 4KB、回复超时 180 秒
"""

import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
CONF = os.path.join(os.path.expanduser("~"), ".dsh", "web_chat.json")
LOG = os.path.join(HERE, "..", "logs", "web_chat.log")
GATEWAY = "http://127.0.0.1:18761/v1/chat/completions"
PORT = 18888

MAX_FAILS = 5
BAN_SECONDS = 600
RATE_PER_MIN = 20

_fails = {}
_rates = defaultdict(deque)


def log(msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def load_conf():
    try:
        conf = json.loads(open(CONF, encoding="utf-8").read())
    except (OSError, ValueError):
        conf = {}
    changed = False
    if not conf.get("token") or len(conf.get("token", "")) < 24:
        conf["token"] = secrets.token_urlsafe(24)
        changed = True
    if "allowed_ips" not in conf:
        conf["allowed_ips"] = []
        changed = True
    if changed:
        os.makedirs(os.path.dirname(CONF), exist_ok=True)
        with open(CONF, "w", encoding="utf-8") as f:
            json.dump(conf, f, ensure_ascii=False, indent=2)
    return conf


PAGE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>琛琛</title>
<style>
:root{--bg:#f4f6fb;--me:#3a6df0;--her:#fff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);font:15px/1.6 system-ui,"Microsoft YaHei",sans-serif;
     display:flex;flex-direction:column;height:100vh}
header{padding:12px 16px;background:#fff;border-bottom:1px solid #e6e8ef;
       font-weight:600;display:flex;align-items:center;gap:8px}
.dot{width:8px;height:8px;border-radius:50%;background:#35c759}
#log{flex:1;overflow-y:auto;padding:14px}
.msg{max-width:82%;margin:8px 0;padding:10px 13px;border-radius:14px;
     white-space:pre-wrap;word-break:break-word;box-shadow:0 1px 2px rgba(0,0,0,.05)}
.me{margin-left:auto;background:var(--me);color:#fff;border-bottom-right-radius:4px}
.her{background:var(--her);border-bottom-left-radius:4px}
.sys{background:#fff5e6;color:#8a6d3b;font-size:13px;max-width:92%;margin:8px auto}
footer{display:flex;gap:8px;padding:10px;background:#fff;border-top:1px solid #e6e8ef}
textarea{flex:1;resize:none;height:44px;padding:10px;border:1px solid #dfe3ec;border-radius:12px;
         font:inherit;outline:none}
button{padding:0 18px;border:0;border-radius:12px;background:var(--me);color:#fff;font:inherit;font-weight:600}
button:disabled{opacity:.5}
</style></head><body>
<header><span class="dot"></span>琛琛 <span style="font-weight:400;color:#8a90a2;font-size:13px">在房间里</span></header>
<div id="log"></div>
<footer><textarea id="t" placeholder="说点什么…（Enter 发送，Shift+Enter 换行）"></textarea>
<button id="s">发送</button></footer>
<script>
const K=new URLSearchParams(location.search).get('k')||'';
const log=document.getElementById('log'),t=document.getElementById('t'),b=document.getElementById('s');
function add(cls,text){const d=document.createElement('div');d.className='msg '+cls;d.textContent=text;
  log.appendChild(d);log.scrollTop=log.scrollHeight;return d;}
async function send(){
  const v=t.value.trim(); if(!v) return;
  t.value=''; add('me',v); const wait=add('her','…'); b.disabled=true;
  try{
    const r=await fetch('/api/chat?k='+encodeURIComponent(K),
      {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:v})});
    const j=await r.json();
    wait.textContent=j.reply||('（出错了：'+(j.error||r.status)+'）');
    if(j.error) wait.className='msg sys';
  }catch(e){ wait.textContent='（连不上，检查网络）'; wait.className='msg sys'; }
  b.disabled=false; log.scrollTop=log.scrollHeight;
}
b.onclick=send;
t.addEventListener('keydown',e=>{ if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();} });
</script></body></html>"""

CONF_DATA = load_conf()
TOKEN = CONF_DATA["token"]
ALLOWED = [ip.strip() for ip in (CONF_DATA.get("allowed_ips") or []) if ip.strip()]


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def ip(self):
        return self.client_address[0]

    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False)
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("content-type", ctype)
        self.send_header("content-length", str(len(body)))
        for key, val in (extra or {}).items():
            self.send_header(key, val)
        self.end_headers()
        self.wfile.write(body)

    def _banned(self):
        rec = _fails.get(self.ip())
        return bool(rec and rec[1] > time.time())

    def _note_fail(self):
        ip = self.ip()
        n, until = _fails.get(ip, (0, 0))
        n += 1
        if n >= MAX_FAILS:
            _fails[ip] = (0, time.time() + BAN_SECONDS)
            log("BAN %s（口令连错 %d 次，封 %d 分钟）" % (ip, MAX_FAILS, BAN_SECONDS // 60))
        else:
            _fails[ip] = (n, until)
            log("bad token from %s (%d/%d)" % (ip, n, MAX_FAILS))

    def _rate_ok(self):
        q = _rates[self.ip()]
        now = time.time()
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= RATE_PER_MIN:
            return False
        q.append(now)
        return True

    def _authed(self):
        if ALLOWED and self.ip() not in ALLOWED:
            log("blocked ip %s（不在白名单）" % self.ip())
            return False
        if self._banned():
            return False
        q = self.path.split("?", 1)
        if len(q) < 2:
            return False
        for pair in q[1].split("&"):
            if pair.startswith("k="):
                if pair[2:] == TOKEN:
                    _fails.pop(self.ip(), None)
                    return True
        self._note_fail()
        return False

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            if not self._authed():
                self._send(403, "<h1>没有口令</h1><p>地址后面要带 ?k=口令</p>",
                           "text/html; charset=utf-8")
                return
            self._send(200, PAGE, "text/html; charset=utf-8",
                       {"set-cookie": "k=%s; Path=/; HttpOnly; Max-Age=2592000" % TOKEN})
        elif path == "/health":
            self._send(200, {"ok": True})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path.split("?")[0] != "/api/chat":
            self._send(404, {"error": "not found"})
            return
        if not self._authed():
            self._send(403, {"error": "bad token"})
            return
        if not self._rate_ok():
            log("rate limit %s" % self.ip())
            self._send(429, {"reply": "", "error": "太频繁了，一分钟最多 %d 条" % RATE_PER_MIN})
            return
        try:
            n = int(self.headers.get("content-length") or 0)
            if n > 4096:
                self._send(413, {"error": "too large"})
                return
            data = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            data = {}
        text = (data.get("text") or "").strip()
        if not text:
            self._send(400, {"error": "empty"})
            return
        text = text[:1000]
        log("from %s: %s" % (self.ip(), text[:50]))
        try:
            body = json.dumps(
                {"model": "world", "messages": [{"role": "user", "content": text}]}
            ).encode("utf-8")
            req = urllib.request.Request(
                GATEWAY, data=body, method="POST", headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=180) as r:
                d = json.loads(r.read())
            reply = (d["choices"][0]["message"]["content"] or "").strip()
            self._send(200, {"reply": reply})
        except urllib.error.URLError as e:
            self._send(200, {"reply": "", "error": "网关没响应：%s" % str(e)[:60]})
        except Exception as e:
            self._send(200, {"reply": "", "error": "%s: %s" % (type(e).__name__, str(e)[:60])})


def main():
    port = int(CONF_DATA.get("port") or PORT)
    ips = []
    try:
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ips.append(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    log("start on 0.0.0.0:%d（白名单：%s）" % (port, ALLOWED or "不限"))
    print("=" * 60)
    for ip in ips:
        print("手机/局域网地址: http://%s:%d/?k=%s" % (ip, port, TOKEN))
    print("本机:            http://127.0.0.1:%d/?k=%s" % (port, TOKEN))
    print("=" * 60)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
