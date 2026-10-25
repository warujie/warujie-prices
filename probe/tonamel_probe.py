# Tonamel's MTG competition list (robots.txt allows /competitions): what the page loads and shows.
import json, re
from playwright.sync_api import sync_playwright
URL = "https://tonamel.com/competitions?game=mtg&region=JP"
out = {"xhr": []}
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1280, "height": 1600}, user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36 (warujie.jp probe)")
    def on_resp(r):
        ct = r.headers.get("content-type", "")
        if "json" in ct or "graphql" in r.url:
            try:
                body = r.text()
            except Exception as e:
                body = repr(e)
            out["xhr"].append({"url": r.url, "method": r.request.method, "post": (r.request.post_data or "")[:3000], "status": r.status, "body": body[:20000]})
    pg.on("response", on_resp)
    pg.goto(URL, wait_until="networkidle", timeout=90000)
    pg.wait_for_timeout(4000)
    out["text"] = pg.inner_text("body")[:15000]
    out["links"] = pg.evaluate("[...document.querySelectorAll('a[href]')].map(a => a.href).filter(h => /competition/.test(h)).slice(0, 60)")
    html = pg.content()
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    out["next_data"] = m.group(1)[:20000] if m else None
    out["nuxt"] = bool(re.search(r"__NUXT__", html))
    pg.screenshot(path="probe/tonamel.png")
    # one competition page, to see what an event shows (venue, date, organizer)
    if out["links"]:
        pg.wait_for_timeout(4000)
        pg.goto(out["links"][0], wait_until="networkidle", timeout=90000)
        pg.wait_for_timeout(3000)
        out["detail_url"] = out["links"][0]
        out["detail_text"] = pg.inner_text("body")[:8000]
    b.close()
json.dump(out, open("probe/tonamel.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: (v if k != "xhr" else [x["url"] for x in v]) for k, v in out.items() if k not in ("next_data",)}, ensure_ascii=False, indent=1)[:6000])
