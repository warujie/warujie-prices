python3 probe/build_events.py --out probe/hfee/events-h.json --only hareruya --fees probe/hfee/hareruya_fees.json --fee-minutes 9
python3 - <<'P'
import json, collections
ev=json.load(open('probe/hfee/events-h.json'))['events']
c=json.load(open('probe/hfee/hareruya_fees.json'))['fees']
print(len(ev), 'events;', sum('fee' in e for e in ev), 'with a fee;', len(c), 'pairs read')
print(len({(e['store'],e['name']) for e in ev}), 'pairs in all')
print(collections.Counter(v['fee'] for v in c.values()).most_common(15))
for k,v in list(c.items())[:25]: print(k, v['fee'])
P
