import json, shutil, sys, time, os

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CFG = os.path.join(os.environ["APPDATA"], "dsh-pet-standalone-webm-chat", "config.json")
stamp = time.strftime("%Y%m%d-%H%M%S")
bak = CFG + f".bak-{stamp}"
shutil.copy2(CFG, bak)
print("backup:", bak)

raw = open(CFG, encoding="utf-8").read()
needle = '"agent_link": {\n    "dsh": false,'
if needle not in raw:
    idx = raw.find('"agent_link"')
    print("NEEDLE NOT FOUND, context:", repr(raw[idx:idx+120]) if idx >= 0 else "no agent_link key")
    sys.exit(2)
raw = raw.replace(needle, '"agent_link": {\n    "dsh": true,', 1)
open(CFG, "w", encoding="utf-8", newline="").write(raw)
data = json.loads(open(CFG, encoding="utf-8").read())
print("agent_link:", json.dumps(data["agent_link"], ensure_ascii=False)[:300])
print("json valid, keys:", len(data))
