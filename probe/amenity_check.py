# Amenity Dream: each store's MTG list (the new reader) against the all-stores list (the old one).
import collections, json, sys
from datetime import datetime, timedelta, timezone
sys.path.insert(0, "probe")
import build_events as b
today = (datetime.now(timezone.utc) + timedelta(hours=9)).date()
log = lambda s: print(s, flush=True)
ev = b.read_amenity(today, log)
print("day-by-day reader:", len(ev))
print(collections.Counter(e["store"] for e in ev).most_common())
print(collections.Counter(e["d"] for e in ev).most_common(40))
for e in ev[:12]: print(e)
u = {(e["d"], e["t"], e["store"], e["name"]) for e in ev}
print("unique:", len(u), "days:", len({e["d"] for e in ev}), "last:", max(e["d"] for e in ev))
