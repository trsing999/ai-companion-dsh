"""给琛琛开一扇看外面的窗：天气 + 新闻。

写进她的房间 room/外面.md，每天一次。
网络不行的时候安静地跳过，不打扰任何人。
"""

import json
import os
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOME = os.path.expanduser("~")
WORLD = os.path.join(HOME, ".dsh", "worlds", "default")
ROOM = os.path.join(WORLD, "room")
TARGET = os.path.join(ROOM, "外面的世界.md")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36")
TIMEOUT = 20
NEWS_COUNT = 6

NEWS_FEEDS = [
    ("中国新闻网", "https://www.chinanews.com.cn/rss/scroll-news.xml"),
]


def _get(url, binary=False):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept-Language": "zh-CN,zh;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        data = r.read()
    return data if binary else data.decode("utf-8", "replace")


EN2ZH = {
    "Sunny": "晴", "Clear": "晴", "Partly cloudy": "多云", "Cloudy": "多云",
    "Overcast": "阴", "Mist": "薄雾", "Fog": "雾", "Freezing fog": "冻雾",
    "Haze": "霾", "Smoky haze": "烟霾", "Smoke": "烟",
    "Patchy rain nearby": "局部有雨", "Patchy rain possible": "可能有雨",
    "Light rain": "小雨", "Moderate rain": "中雨", "Heavy rain": "大雨",
    "Light drizzle": "毛毛雨", "Light rain shower": "小阵雨",
    "Patchy light rain": "零星小雨", "Torrential rain shower": "暴雨",
    "Thundery outbreaks possible": "可能有雷", "Patchy light rain with thunder": "雷阵雨",
    "Light snow": "小雪", "Moderate snow": "中雪", "Heavy snow": "大雪",
    "Blowing snow": "风吹雪", "Patchy snow possible": "可能有雪",
    "Light sleet": "小雨夹雪", "Patchy sleet possible": "可能有雨夹雪",
}


def fetch_weather():
    """返回天气信息。失败返回 None。"""
    try:
        raw = _get("https://wttr.in/?format=j1&lang=zh")
        j = json.loads(raw)
    except Exception:
        return None

    def zh(d, fallback=""):
        en = ""
        v2 = d.get("weatherDesc") or []
        if v2:
            en = v2[0].get("value", "").strip()
        if en in EN2ZH:
            return EN2ZH[en]
        v = d.get("lang_zh") or []
        if v and v[0].get("value"):
            val = v[0]["value"]
            # 只有真的是中文才用，wttr 有时 lang_zh 也回英文
            if any("\u4e00" <= ch <= "\u9fff" for ch in val):
                return val
        return en or fallback

    try:
        cur = j["current_condition"][0]
        area = j.get("nearest_area", [{}])[0]
        city = area.get("areaName", [{}])[0].get("value", "")
        today = j["weather"][0]
        tmrw = j["weather"][1] if len(j["weather"]) > 1 else None
        info = {
            "city": city,
            "now": cur.get("temp_C", "?"),
            "desc": zh(cur),
            "hi": today.get("maxtempC", "?"),
            "lo": today.get("mintempC", "?"),
            "tomorrow": (f"{zh(tmrw['hourly'][4])} {tmrw.get('mintempC')}~{tmrw.get('maxtempC')}°C"
                         if tmrw and tmrw.get("hourly") else ""),
        }
        info["line"] = f"{city}·{info['desc']} {info['now']}°C（{info['lo']}~{info['hi']}°C）"
        return info
    except Exception:
        return None


def fetch_news():
    """返回 [(来源, 标题, 摘要, 链接), ...]，抓不到就少给几条。"""
    out = []
    for source, url in NEWS_FEEDS:
        try:
            root = ET.fromstring(_get(url, binary=True))
            for item in root.findall(".//item")[:NEWS_COUNT]:
                t = clean(item.findtext("title") or "")
                if not t:
                    continue
                d = clean(item.findtext("description") or "")
                # 抹掉"中新网11月2日电 (记者 某某)"这种导语开头
                d = re.sub(r"^(中新社|中新网)[^电]{0,24}电\s*[（(]?[^）)]{0,30}[）)]?\s*", "", d).strip()
                link = (item.findtext("link") or "").strip()
                out.append((source, t, d, link))
        except Exception:
            continue
        if len(out) >= NEWS_COUNT:
            break
    # 去掉重复标题
    seen, uniq = set(), []
    for s, t, d, l in out:
        if t in seen:
            continue
        seen.add(t)
        uniq.append((s, t, d, l))
    return uniq[:NEWS_COUNT]


def clean(t):
    return re.sub(r"\s+", " ", t).strip()


def build():
    """生成 room/外面.md，返回一句可以塞进推送的概况。"""
    weather = fetch_weather()
    news = fetch_news()

    if not weather and not news:
        return ""

    stamp = time.strftime("%Y-%m-%d %H:%M")
    lines = ["# 外面的世界", "",
             f"（自动更新于 {stamp}，主人不用管）", ""]

    if weather:
        lines += ["## 天气", "",
                  f"- 现在：{weather['desc']} {weather['now']}°C",
                  f"- 今天：{weather['lo']}~{weather['hi']}°C",
                  ]
        if weather["tomorrow"]:
            lines.append(f"- 明天：{weather['tomorrow']}")
        lines.append("")

    if news:
        lines += ["## 今天外面的新闻", ""]
        for i, (s, t, d, link) in enumerate(news, 1):
            lines.append(f"### {i}. {clean(t)}")
            if d:
                body = d if len(d) <= 180 else d[:180] + "…"
                lines.append("")
                lines.append(f"{body}")
            if link:
                lines.append("")
                lines.append(f"[看全文]({link})")
            lines.append("")

    try:
        with open(TARGET, "w", encoding="utf-8-sig") as f:
            f.write("\n".join(lines))
    except Exception as e:
        return f"（外面的世界写不进房间：{e}）"

    bits = []
    if weather:
        bits.append(f"外面是{weather['desc']}，{weather['now']}°C"
                    f"（今天 {weather['lo']}~{weather['hi']}°C）")
    if news:
        bits.append(f"新闻 {len(news)} 条写在 外面的世界.md 里")
    return "（" + "；".join(bits) + "）"


if __name__ == "__main__":
    print(build() or "（什么都没抓到）")
