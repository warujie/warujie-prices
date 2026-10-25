# The live Worker (same as warujie.jp) after the 2026-10-25 publish: top bar, 大会 tab hidden, events.json not served.
import json
from playwright.sync_api import sync_playwright
BASE = "https://warujie.warujie-mtg.workers.dev/"
out = {}
with sync_playwright() as p:
    b = p.chromium.launch()
    for name, w, h in [("live-desktop", 1280, 800), ("live-phone", 390, 844)]:
        pg = b.new_page(viewport={"width": w, "height": h}, user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36 warujie-probe")
        pg.goto(BASE, wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_selector("#homeHero", state="visible", timeout=60000); pg.wait_for_timeout(1500)
        out[name] = pg.evaluate("""(async () => {
          const r = s => { const e = document.querySelector(s); if (!e) return null; const b = e.getBoundingClientRect(); return [Math.round(b.x), Math.round(b.y), Math.round(b.width)]; };
          const ev = await fetch('/data/events.json').then(r => r.status).catch(e => String(e));
          return { menu: r('#menuBtn'), brand: r('#brandLink'), want: r('#wantBtn'), lang: r('#langBtn'), tabEventsHidden: document.getElementById('tabEvents') ? document.getElementById('tabEvents').hidden : 'none',
                   tabs: [...document.querySelectorAll('.top-tab')].filter(t => !t.hidden).map(t => t.textContent), eventsJson: ev };
        })()""")
        pg.screenshot(path=f"probe/{name}.png")
        pg.goto(BASE + "?view=events", wait_until="domcontentloaded"); pg.wait_for_timeout(2500)
        out[name + "-events-url"] = pg.url
        pg.close()
    b.close()
print(json.dumps(out, ensure_ascii=False, indent=1))
