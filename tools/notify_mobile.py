"""把通知推到手机（企业微信群机器人 / Server酱）。

配置：~/.dsh/mobile_push.json
  {"provider": "wecom", "webhook": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..."}
  {"provider": "serverchan", "sendkey": "SCT..."}

命令行自测：
  python notify_mobile.py --test
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CONF = os.path.join(os.path.expanduser("~"), ".dsh", "mobile_push.json")
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs", "notify_mobile.log")


def log(msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def config():
    try:
        return json.loads(open(CONF, encoding="utf-8-sig").read())
    except (OSError, ValueError):
        return None


def _post(url, payload, timeout=8):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST", headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")[:200]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:200]
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, str(e)[:100])


def push(title, text):
    """返回 (ok, detail)。没配置就返回 (False, 'no config') 而不是抛错。"""
    cfg = config()
    if not cfg:
        return False, "no config"
    provider = (cfg.get("provider") or "").lower()
    content = ("%s\n%s" % (title, text)).strip() if title else text
    if provider == "wecom":
        hook = (cfg.get("webhook") or "").strip()
        if not hook:
            return False, "missing webhook"
        status, detail = _post(hook, {"msgtype": "text", "text": {"content": content}})
        ok = status == 200 and '"errcode":0' in detail.replace(" ", "")
        log("wecom %s %s" % (status, detail[:80]))
        return ok, detail
    if provider == "serverchan":
        key = (cfg.get("sendkey") or "").strip()
        if not key:
            return False, "missing sendkey"
        url = "https://sctapi.ftqq.com/%s.send" % key
        status, detail = _post(
            url, {"title": title or "琛琛", "desp": text}, timeout=10
        )
        ok = status == 200
        log("serverchan %s %s" % (status, detail[:80]))
        return ok, detail
    return False, "unknown provider: %s" % provider


if __name__ == "__main__":
    if "--test" in sys.argv:
        cfg = config()
        print("config:", "ok" if cfg else "MISSING", (cfg or {}).get("provider"))
        ok, detail = push("琛琛", "这是一条测试消息，收到就说明手机通道通了。")
        print("push ok=", ok, "detail=", detail)
        sys.exit(0 if ok else 1)
    print("usage: python notify_mobile.py --test")
