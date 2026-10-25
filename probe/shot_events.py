# Screenshots of the staging test site's 大会 tab after the Tonamel publish.
import json
from playwright.sync_api import sync_playwright
BASE = "https://staging-warujie.warujie-mtg.workers.dev/"
out = {}
with sync_playwright() as p:
    b = p.chromium.launch()
    for name, w, h, q in [("kanto", 1280, 1000, "?view=events&area=kanto"), ("okinawa-phone", 390, 844, "?view=events&area=okinawa&days=30"), ("tonamel-all", 1280, 1000, "?view=events&area=all&shop=tonamel"), ("amenity", 1280, 1000, "?view=events&area=kanto&shop=amenity&days=all")]:
        pg = b.new_page(viewport={"width": w, "height": h}, user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36 warujie-probe")
        pg.goto(BASE + q, wait_until="domcontentloaded", timeout=60000)
        try:
            pg.wait_for_selector("#evBody .ev-day, #evBody .ev-wait, #evBody .status-line", timeout=60000)
        except Exception as e:
            out[name + "_error"] = str(e)
        pg.wait_for_timeout(1500)
        out[name] = pg.evaluate("""(() => ({
          tabVisible: !!document.getElementById('tabEvents') && !document.getElementById('tabEvents').hidden,
          summary: (document.getElementById('evSummary') || {}).innerText,
          note: (document.getElementById('evNote') || {}).innerText,
          days: document.querySelectorAll('#evBody .ev-day').length,
          rows: document.querySelectorAll('#evBody .ev-row').length,
          wait: !!document.querySelector('#evBody .ev-wait'),
          fmt: [...document.querySelectorAll('#evFormat option')].map(o => o.textContent),
          shop: [...document.querySelectorAll('#evShop option')].slice(0, 25).map(o => o.textContent),
          city: [...document.querySelectorAll('#evCity option')].slice(0, 12).map(o => o.textContent),
          first: [...document.querySelectorAll('#evBody .ev-row')].slice(0, 8).map(r => r.innerText.replace(/\\s+/g, ' ')),
        }))()""")
        pg.screenshot(path=f"probe/events-{name}.png", full_page=False)
        pg.close()
    b.close()
json.dump(out, open("probe/events-site.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
