# Dry run of the Tonamel reader (no publishing): counts by prefecture, samples, unplaced events.
import collections, json, sys
from datetime import datetime, timedelta, timezone
sys.path.insert(0, "probe")
import build_events as b
today = (datetime.now(timezone.utc) + timedelta(hours=9)).date()
log = lambda s: print(s, flush=True)
ev = b.read_tonamel(today, log)
json.dump(ev, open("probe/tonamel.json", "w"), ensure_ascii=False, indent=0)
last = (today + timedelta(days=35)).isoformat()
print("all:", len(ev), "dates:", min((e["d"] for e in ev), default=""), max((e["d"] for e in ev), default=""))
ev = [e for e in ev if today.isoformat() <= e["d"] <= last]
print("events in 35 days:", len(ev))
print("by prefecture:", collections.Counter(b.PREF_NAMES[e["p"] - 1] for e in ev).most_common())
print("by store:", collections.Counter(e["store"] for e in ev).most_common(80))
print("formats:", collections.Counter(tuple(e.get("f") or []) for e in ev).most_common(12))
print("okinawa / zero:", [e for e in ev if e["p"] == 47 or "ゼロ" in e["store"] or "zero" in e["store"].lower()][:20])
for e in ev[:15]: print(e)
