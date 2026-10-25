# Amenity Dream: each store's MTG list (the new reader) against the all-stores list (the old one).
import collections, json, sys
from datetime import datetime, timedelta, timezone
sys.path.insert(0, "probe")
import build_events as b
today = (datetime.now(timezone.utc) + timedelta(hours=9)).date()
log = lambda s: print(s, flush=True)
ev = b.read_amenity(today, log)
print("per-store reader:", len(ev))
print(collections.Counter(e["store"] for e in ev).most_common())
print(collections.Counter(e["d"] for e in ev).most_common(40))
for e in ev[:12]: print(e)
old = b.parse_amenity(b.fetch("https://amenitydream.co.jp/matches/?type=2&shop=&date=", context=b.amenity_context()), today)
print("all-stores list:", len(old), collections.Counter(e["store"] for e in old).most_common())
