"""Windows 系统通知（复用 dsh-world 的 WinRT 方案）。

toast(title, body)：用 PowerShell -EncodedCommand 调用 WinRT。
身份优先用已知的 DSH AppID，找不到就在开始菜单里搜。
"""

import base64
import subprocess
import sys

KNOWN_IDS = ["com.deepseek.dsh", "electron.app.DeepSeek Harness"]
_cache = {"appId": None}


def _b64(text):
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def _decode_expr(text):
    return "[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('%s'))" % _b64(text)


def _xml_escape(text):
    table = {"<": "&lt;", ">": "&gt;", "&": "&amp;", "'": "&apos;", '"': "&quot;"}
    return "".join(table.get(c, c) for c in text)


def _cap(text, n):
    chars = list(text)
    return "".join(chars[:n]) + ("…" if len(chars) > n else "")


def _script(app_id, title, body, lookup):
    payload = (
        '<toast><visual><binding template="ToastGeneric"><text>%s</text><text>%s</text>'
        "</binding></visual></toast>" % (_xml_escape(_cap(title, 64)), _xml_escape(_cap(body, 500)))
    )
    lines = [
        "$ErrorActionPreference = 'Stop'; [Console]::OutputEncoding = [Text.Encoding]::UTF8; $ProgressPreference = 'SilentlyContinue'",
        "try {",
        "$null = [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]",
        "$null = [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]",
        "$appId = %s" % _decode_expr(app_id or ""),
    ]
    if lookup:
        lines += [
            "$apps = @(Get-StartApps)",
            "if ($appId) {",
            "  if (-not ($apps | Where-Object { $_.AppID -eq $appId })) { throw '开始菜单里没有该通知身份' }",
            "} else {",
            "  $known = @(%s)" % ", ".join(_decode_expr(i) for i in KNOWN_IDS),
            "  $app = $known | ForEach-Object { $id = $_; $apps | Where-Object { $_.AppID -eq $id } } | Select-Object -First 1",
            "  if (-not $app) { $app = $apps | Where-Object { $_.Name -like '*DeepSeek Harness*' } | Select-Object -First 1 }",
            "  if (-not $app) { throw '开始菜单里找不到 DSH 的通知身份' }",
            "  $appId = $app.AppID",
            "}",
        ]
    lines += [
        "$notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId)",
        'if ("$($notifier.Setting)" -ne "Enabled") { throw "Windows 关闭了通知（$($notifier.Setting)）" }',
        "$xml = New-Object Windows.Data.Xml.Dom.XmlDocument",
        "$xml.LoadXml(%s)" % _decode_expr(payload),
        "$notifier.Show([Windows.UI.Notifications.ToastNotification]::new($xml))",
        "[Console]::Out.Write($appId)",
        "} catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }",
    ]
    return "\n".join(lines)


def toast(title, body):
    """弹一条 Windows 通知；返回 (ok, detail)。"""
    lookup = _cache["appId"] is None
    script = _script(_cache["appId"], title, body, lookup)
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
            capture_output=True,
            timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as e:
        return False, "%s: %s" % (type(e).__name__, e)
    out = (proc.stdout or b"").decode("utf-8", "replace").strip()
    err = (proc.stderr or b"").decode("utf-8", "replace").strip()
    if proc.returncode == 0:
        if out:
            _cache["appId"] = out
        return True, out
    _cache["appId"] = None
    return False, err[:200]


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ok, detail = toast("琛琛", "测试：系统通知兜底已就绪")
    print("ok=%s detail=%s" % (ok, detail))
