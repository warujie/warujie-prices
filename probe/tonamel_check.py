# Dry run of the Tonamel reader (no publishing): counts by prefecture, samples, unplaced events.
import collections, json, sys
from datetime import datetime, timedelta, timezone
sys.path.insert(0, "probe")
import build_events as b
today = (datetime.now(timezone.utc) + timedelta(hours=9)).date()
log = lambda s: print(s, flush=True)
# one raw page first, to see the shapes
start = int(datetime(today.year, today.month, today.day, tzinfo=b.JST).timestamp())
body = json.dumps({"operationName": "getPublicCompetitions", "query": b.TONAMEL_QUERY, "variables": {
    "condition": {"gameId": "mtg", "startAfter": str(start), "statuses": [], "region": "JP", "regionPrefectureIds": []},
    "filter": {"first": 32, "last": 0, "before": "", "after": ""}}}).encode()
try:
    raw = b.fetch(b.TONAMEL_API, data=body)
    j = json.loads(raw)
    nodes = [e["node"] for e in j["data"]["publicCompetitions"]["edges"]]
    print("raw page:", len(nodes), "statuses:", collections.Counter(n.get("status") for n in nodes))
    for n in nodes[:3]:
        n = dict(n); n["description"] = (n.get("description") or "")[:100]; print(json.dumps(n, ensure_ascii=False))
    unplaced = [(n["title"], [(t.get("location") or {}) for t in n.get("tournaments") or []]) for n in nodes
                if not any(b.place_of(((t.get("location") or {}).get("address") or {}).get("input", "") or "")[0] for t in n.get("tournaments") or [])]
    print("unplaced on page 1:", json.dumps(unplaced[:12], ensure_ascii=False))
except Exception as e:
    print("raw error:", repr(e)[:800])
ev = b.read_tonamel(today, log)
last = (today + timedelta(days=35)).isoformat()
ev = [e for e in ev if today.isoformat() <= e["d"] <= last]
print("events in 35 days:", len(ev))
print("by prefecture:", collections.Counter(b.PREF_NAMES[e["p"] - 1] for e in ev).most_common())
print("by store:", collections.Counter(e["store"] for e in ev).most_common(60))
print("formats:", collections.Counter(tuple(e["f"]) for e in ev).most_common(12))
print("okinawa / zero:", [e for e in ev if e["p"] == 47 or "ゼロ" in e["store"] or "zero" in e["store"].lower()][:20])
for e in ev[:15]: print(e)
