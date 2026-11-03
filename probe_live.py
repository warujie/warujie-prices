import json, collections
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.goto('https://warujie.warujie-mtg.workers.dev/?view=events', wait_until='networkidle')
    pg.wait_for_timeout(3000)
    data = pg.evaluate("fetch('/data/events.json').then(r=>r.text())")
    b.close()
ev = json.loads(data)
ev = ev.get('events', ev) if isinstance(ev, dict) else ev
print('events:', len(ev))
c = collections.Counter((e.get('p'), e.get('c'), e.get('a', ''), e.get('shop'), e.get('store')) for e in ev)
for k, n in sorted(c.items(), key=lambda x: (str(x[0][0]), str(x[0][1]), str(x[0][2]))):
    print('AREA', json.dumps(list(k) + [n], ensure_ascii=False))
