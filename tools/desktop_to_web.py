"""桌面版桌宠（琛琛）→ dsh-pet 插件（深深）反向桥。

监听琛琛日志里的点击音效行，POST 到 dsh-pet 的广播端点让深深冒泡回应。

端口策略：已知端口 → netstat 枚举本机监听端口逐个探测。
广播连接失败时重新发现一次再重试。
"""

import glob
import json
import os
import random
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bubble_gate

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LOG_DIR = os.path.join(os.environ["APPDATA"], "dsh-pet-standalone-webm-chat")
KNOWN_PORTS = [12761, 33977, 17474, 3080, 38080, 54719, 36618, 8080]
API_TPL = "http://127.0.0.1:%d/dsh-pet-7340/broadcast?pet=main&surface=any"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs", "desktop_to_web.log")
COOLDOWN = 3.0
LINES = [
    "你摸她……那我呢？",
    "我也要摸！",
    "唔，偏心。",
    "这边也摸一下嘛。",
    "她刚刚被摸了，我看见了。",
]

API = None
last_fire = 0.0


def log(msg):
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + msg
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def probe(port, timeout=0.3):
    try:
        urllib.request.urlopen("http://127.0.0.1:%d/dsh-pet-7340/" % port, timeout=timeout)
        return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


def listening_ports():
    ports = set()
    try:
        out = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout
    except Exception:
        return []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[3] == "LISTENING" and parts[1].startswith("127.0.0.1:"):
            try:
                ports.add(int(parts[1].rsplit(":", 1)[1]))
            except ValueError:
                pass
    return sorted(ports)


def discover_port():
    for port in KNOWN_PORTS:
        if probe(port):
            return port, "known"
    for port in listening_ports():
        if probe(port, timeout=0.25):
            return port, "listening"
    return None, "none"


def ensure_api(force=False):
    global API
    if API and not force:
        return API
    port, how = discover_port()
    if port:
        API = API_TPL % port
        log("dsh-pet api on port %d (via %s)" % (port, how))
    else:
        API = None
        log("PORT NOT FOUND：没有找到 dsh-pet 服务端口")
    return API


def newest_log():
    files = [f for f in glob.glob(os.path.join(LOG_DIR, "pet-*.log")) if "gate" not in f]
    return max(files, key=os.path.getmtime) if files else None


def broadcast(text):
    body = json.dumps({"text": text, "duration": 8000}).encode("utf-8")
    req = urllib.request.Request(
        API, data=body, method="POST", headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=8) as r:
        return r.status, r.read().decode("utf-8", "replace")[:200]


def fire(text):
    global API
    ok, why = bubble_gate.allow(text)
    if not ok:
        log("RATE LIMITED: %s" % why)
        return
    try:
        status, resp = broadcast(text)
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
        log("broadcast connection failed, re-discovering port")
        if not ensure_api(force=True):
            return
        try:
            status, resp = broadcast(text)
        except Exception as e:
            log("BROADCAST FAILED: %s %s" % (type(e).__name__, str(e)[:80]))
            return
    log("clicked -> broadcast %s %s" % (status, resp))
    try:
        if json.loads(resp).get("ok") is False:
            log("BROADCAST REJECTED: %s" % resp)
        else:
            bubble_gate.done(text)
    except ValueError:
        pass


def main():
    global last_fire, API
    ensure_api()
    path = newest_log()
    if not path:
        log("no pet log found")
        return
    log("tail %s" % path)
    fh = open(path, "rb")
    fh.seek(0, os.SEEK_END)
    last_check = time.time()
    while True:
        line = fh.readline()
        if not line:
            fh.seek(fh.tell())
            time.sleep(0.4)
            if time.time() - last_check > 60:
                last_check = time.time()
                if API:
                    port = int(API.split(":")[2].split("/")[0])
                    if not probe(port):
                        ensure_api(force=True)
                else:
                    ensure_api()
            cur = newest_log()
            if cur and cur != path:
                log("switch log -> %s" % cur)
                fh.close()
                path = cur
                fh = open(path, "rb")
                fh.seek(0, os.SEEK_END)
            continue
        text = line.decode("utf-8", "replace")
        if "播放音效" in text and ("duck" in text or "Ya" in text):
            now = time.time()
            if now - last_fire < COOLDOWN:
                continue
            last_fire = now
            if not API:
                ensure_api()
            if not API:
                continue
            fire(random.choice(LINES))


if __name__ == "__main__":
    main()
