import json, collections, time
from playwright.sync_api import sync_playwright
STREETS = {"江木町", "宮子町", "本町", "中町", "城山町", "椿町", "港町", "大供", "大名", "上之園町", "南上原", "一本木町"}
for attempt in range(30):
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={'width': 1280, 'height': 900}, locale='ja-JP')
        pg.add_init_script("try{localStorage.setItem('akuchie-lang','ja')}catch(e){}")
        pg.goto('https://warujie.warujie-mtg.workers.dev/?view=events', wait_until='networkidle')
        pg.wait_for_timeout(3000)
        data = json.loads(pg.evaluate("fetch('/data/events.json',{cache:'no-store'}).then(r=>r.text())"))
        ev = data.get('events', data) if isinstance(data, dict) else data
        left = sorted({e.get('a') for e in ev} & STREETS)
        html = pg.content()
        tama = '多摩・島しょ' in html
        if not left and not tama or attempt == 29:
            print('attempt', attempt, 'events', len(ev), 'street names left:', left, 'tama box in page:', tama)
            c = collections.Counter((e.get('c'), e.get('a', ''), e.get('store')) for e in ev if e.get('shop') in ('tonamel', 'mint', 'x'))
            for k, n in sorted(c.items()): print('AREA', json.dumps(list(k) + [n], ensure_ascii=False))
            pg.locator('#evPlace').click(); pg.wait_for_timeout(800)
            rows = pg.evaluate("[...document.querySelectorAll('#evPlaceList .ev-pl-pref, #evPlaceList .ev-pl-city, #evPlaceList .ev-pl-stn')].map(x=>x.innerText.replace(/\\s+/g,' ').trim())")
            for r in rows[:40]: print('ROW', r)
            b.close(); break
        b.close()
    time.sleep(60)
