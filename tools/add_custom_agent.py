import json, os, shutil, sys, time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CFG_DIR = os.path.join(os.environ["APPDATA"], "dsh-pet-standalone-webm-chat")
CFG = os.path.join(CFG_DIR, "config.json")
EV_DIR = os.path.join(CFG_DIR, "agent-events")
EV = os.path.join(EV_DIR, "webpet.jsonl")

os.makedirs(EV_DIR, exist_ok=True)
bak = CFG + ".bak-customagent-" + time.strftime("%Y%m%d-%H%M%S")
shutil.copy2(CFG, bak)
print("backup:", bak)

raw = open(CFG, encoding="utf-8").read()
data = json.loads(raw)
existing = data["agent_link"].get("custom_agents") or []
if any(a.get("key") == "webpet" for a in existing):
    print("webpet already configured")
else:
    if '"custom_agents": [],' not in raw:
        print("NEEDLE NOT FOUND — aborting without change")
        sys.exit(2)
    block = (
        '"custom_agents": [\n'
        "      {\n"
        '        "key": "webpet",\n'
        '        "name": "网页大肥鱼",\n'
        '        "path": "' + EV.replace("\\", "\\\\") + '"\n'
        "      }\n"
        "    ],"
    )
    raw = raw.replace('"custom_agents": [],', block, 1)
    open(CFG, "w", encoding="utf-8", newline="").write(raw)

check = json.load(open(CFG, encoding="utf-8"))
print("custom_agents:", json.dumps(check["agent_link"]["custom_agents"], ensure_ascii=False))
print("events dir:", EV_DIR)
