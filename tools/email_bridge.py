"""邮箱 ↔ 琛琛：手机发邮件给她，她用邮件回你。

配置：~/.dsh/email_bridge.json
{
  "email": "you@qq.com",
  "password": "邮箱授权码（不是登录密码）",
  "imap_host": "imap.qq.com", "imap_port": 993,
  "smtp_host": "smtp.qq.com", "smtp_port": 465,
  "allow_from": ["you@qq.com"],
  "poll_seconds": 40
}

只处理来自 allow_from 的未读邮件；回复时保持邮件线程（In-Reply-To）。
"""

import email
import email.policy
import email.utils
import imaplib
import json
import os
import smtplib
import ssl
import sys
import time
import urllib.request
from email.mime.text import MIMEText

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CONF = os.path.join(os.path.expanduser("~"), ".dsh", "email_bridge.json")
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs", "email_bridge.log")
GATEWAY = "http://127.0.0.1:18761/v1/chat/completions"
STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs", "email_state.json")


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
        return json.loads(open(CONF, encoding="utf-8-sig").read())
    except (OSError, ValueError):
        return None


def load_state():
    try:
        return json.loads(open(STATE, encoding="utf-8").read())
    except (OSError, ValueError):
        return {"seen": []}


def save_state(st):
    try:
        with open(STATE, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False)
    except OSError:
        pass


def clean_body(msg):
    """取纯文本正文，去掉引用历史和签名。"""
    text = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and "attachment" not in str(
                part.get("Content-Disposition") or ""
            ):
                try:
                    text = part.get_content()
                    break
                except Exception:
                    continue
    else:
        try:
            text = msg.get_content()
        except Exception:
            text = ""
    if not text:
        return ""
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(">"):
            continue
        if stripped in ("-- ", "--"):
            break
        if stripped.startswith("在 20") and "写道" in stripped:
            break
        if stripped.startswith("From:") or stripped.startswith("发件人:"):
            break
        lines.append(line)
    return "\n".join(lines).strip()


def ask_world(text, timeout=180):
    body = json.dumps(
        {"model": "world", "messages": [{"role": "user", "content": text}]}
    ).encode("utf-8")
    req = urllib.request.Request(
        GATEWAY, data=body, method="POST", headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read())
    return (d["choices"][0]["message"]["content"] or "").strip()


def send_reply(conf, to_addr, subject, body, in_reply_to=None, references=None):
    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = conf["email"]
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["Message-ID"] = email.utils.make_msgid(domain=conf["email"].split("@")[-1])
    msg["X-DSH-Pet-Reply"] = "1"
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = references or in_reply_to
    ctx = ssl.create_default_context()
    port = int(conf.get("smtp_port", 465))
    if port == 465:
        with smtplib.SMTP_SSL(conf["smtp_host"], port, timeout=30, context=ctx) as s:
            s.login(conf["email"], conf["password"])
            s.send_message(msg)
    else:
        with smtplib.SMTP(conf["smtp_host"], port, timeout=30) as s:
            s.starttls(context=ctx)
            s.login(conf["email"], conf["password"])
            s.send_message(msg)
    log("replied to %s (%d chars)" % (to_addr, len(body)))


def poll_once(conf, st):
    ctx = ssl.create_default_context()
    imap = imaplib.IMAP4_SSL(conf["imap_host"], int(conf.get("imap_port", 993)), ssl_context=ctx)
    handled = 0
    try:
        imap.login(conf["email"], conf["password"])
        # 163/126 邮箱要求客户端先发 ID 命令，否则报 Unsafe Login
        try:
            _id = '("name" "dsh-pet" "version" "1.0" "vendor" "python-imap")'
            imap.xatom("ID", _id)
        except Exception:
            pass
        imap.select("INBOX")
        typ, data = imap.search(None, "ALL")
        if typ != "OK":
            return 0
        ids = data[0].split()
        for num in ids[-15:]:
            typ, raw = imap.fetch(num, "(RFC822)")
            if typ != "OK" or not raw or not raw[0]:
                continue
            msg = email.message_from_bytes(raw[0][1], policy=email.policy.default)
            if msg.get("X-DSH-Pet-Reply"):
                continue
            uid_key = msg.get("Message-ID") or num.decode()
            if uid_key in st["seen"]:
                continue
            sender = email.utils.parseaddr(msg.get("From", ""))[1].lower()
            allow = [a.lower() for a in (conf.get("allow_from") or [conf["email"]])]
            if sender not in allow:
                log("skip mail from %s (not allowed)" % sender)
                st["seen"].append(uid_key)
                continue
            body = clean_body(msg)
            if not body:
                raw_subject = (msg.get("Subject") or "").strip()
                if raw_subject and not raw_subject.lower().startswith("re:"):
                    body = raw_subject
                    log("empty body, fall back to subject: %s" % body[:40])
            if not body:
                log("skip empty mail %s" % uid_key)
                st["seen"].append(uid_key)
                continue
            # 过滤系统通知 / 审批提示，避免把 DSH 的审批请求当成主人的来信
            SYSTEM_MARKS = (
                "琛琛想动一下权限",
                "回一句话就行",
                "放行：回复",
                "拒绝：回复",
                "原始邮件",
                "工具：pwsh",
                "工具：",
                "审批",
                "approval",
                "Approve",
            )
            if any(mark in body for mark in SYSTEM_MARKS):
                log("skip system/approval mail: %s" % body[:40].replace("\n", " "))
                st["seen"].append(uid_key)
                st["seen"] = st["seen"][-300:]
                save_state(st)
                continue
            log("mail from %s: %s" % (sender, body[:50].replace("\n", " ")))
            try:
                reply = ask_world(body)
            except Exception as e:
                log("world failed: %s %s" % (type(e).__name__, str(e)[:80]))
                reply = "（我这边一时没接上自己的世界，等一下再试好吗）"
            subject = msg.get("Subject", "（无主题）")
            if not subject.startswith("Re:"):
                subject = "Re: " + subject
            try:
                send_reply(
                    conf,
                    sender,
                    subject,
                    reply,
                    msg.get("Message-ID"),
                    msg.get("References"),
                )
                handled += 1
            except Exception as e:
                log("smtp failed: %s %s" % (type(e).__name__, str(e)[:100]))
            st["seen"].append(uid_key)
            st["seen"] = st["seen"][-300:]
            save_state(st)
        try:
            imap.store("1:*", "+FLAGS", "\\Seen") if False else None
        except Exception:
            pass
    finally:
        try:
            imap.logout()
        except Exception:
            pass
    return handled


def prime(conf, st):
    """首次运行：把现有邮件的 Message-ID 全部记为已见，不处理历史。"""
    import ssl as _ssl

    ctx = _ssl.create_default_context()
    im = imaplib.IMAP4_SSL(conf["imap_host"], int(conf.get("imap_port", 993)), ssl_context=ctx)
    try:
        im.login(conf["email"], conf["password"])
        im.select("INBOX")
        typ, data = im.search(None, "ALL")
        ids = data[0].split()[-50:] if typ == "OK" else []
        for num in ids:
            t, raw = im.fetch(num, "(BODY.PEEK[HEADER])")
            if t != "OK" or not raw or not raw[0]:
                continue
            msg = email.message_from_bytes(raw[0][1], policy=email.policy.default)
            key = msg.get("Message-ID")
            if key and key not in st["seen"]:
                st["seen"].append(key)
        save_state(st)
        log("基线已建立：%d 封历史邮件不再处理" % len(ids))
    finally:
        try:
            im.logout()
        except Exception:
            pass


def main():
    conf = load_conf()
    if not conf:
        log("没有配置：%s 不存在" % CONF)
        print("请先创建配置文件，格式见脚本开头注释")
        return
    log("start; %s（每 %s 秒查一次）" % (conf["email"], conf.get("poll_seconds", 40)))
    fresh = not os.path.exists(STATE)
    st = load_state()
    if fresh:
        prime(conf, st)
    while True:
        try:
            n = poll_once(conf, st)
            if n:
                log("handled %d mail(s)" % n)
        except Exception as e:
            log("poll error: %s %s" % (type(e).__name__, str(e)[:100]))
        time.sleep(int(conf.get("poll_seconds", 40)))


if __name__ == "__main__":
    main()
