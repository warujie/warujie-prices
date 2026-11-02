import json
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={'width':1280,'height':900}, locale='ja-JP')
    pg.add_init_script("try{localStorage.setItem('akuchie-lang','ja')}catch(e){}")
    pg.goto('https://warujie.warujie-mtg.workers.dev/?view=events', wait_until='networkidle')
    pg.wait_for_timeout(4000)
    print('summary:', pg.evaluate("(document.querySelector('.ev-count, #evCount')||{}).textContent"))
    pg.locator('#evPlace').click(); pg.wait_for_timeout(800)
    rows = pg.evaluate("[...document.querySelectorAll('#evPlaceList label, #evPlaceList .ev-pl-city, #evPlaceList .ev-pl-pref')].map(x=>x.innerText.replace(/\\s+/g,' ').trim())")
    seen=set()
    for r in rows:
        if r not in seen: seen.add(r); print('ROW', r)
        if len(seen)>45: break
    pg.screenshot(path='probe_out/live-menu.png')
    t = pg.evaluate("document.body.innerText")
    print('高田馬場 in page:', t.count('高田馬場'), ' トーナメントセンター:', t.count('トーナメントセンター'))
    b.close()
