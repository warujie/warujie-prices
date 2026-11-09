import hashlib, time, urllib.request, gzip
from playwright.sync_api import sync_playwright
BASE = "https://warujie.warujie-mtg.workers.dev/"
WANT = "9642da4457ab42aa67e2878e8f3d9f7dc42ade68debf472bb237db6749dfd2d9"
out = open("probe_out/live_check.txt", "w")
def say(*a):
    print(*a); out.write(" ".join(str(x) for x in a) + "\n"); out.flush()
got = None
for i in range(40):
    req = urllib.request.Request(BASE + "?nocache=" + str(time.time()), headers={"User-Agent": "Mozilla/5.0 (warujie.jp live check)", "Accept-Encoding": "gzip"})
    try:
        r = urllib.request.urlopen(req, timeout=30); b = r.read()
        if r.headers.get("Content-Encoding") == "gzip": b = gzip.decompress(b)
        got = hashlib.sha256(b).hexdigest()
    except Exception as e:
        got = "error " + str(e)
    say("try", i, got == WANT, got[:16])
    if got == WANT: break
    time.sleep(30)
say("live matches main e8238cd:", got == WANT)
with sync_playwright() as p:
    b = p.chromium.launch()
    errs = []
    pg = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=1, is_mobile=True, has_touch=True)
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE + "?view=meta&format=standard"); pg.wait_for_timeout(5000)
    href = pg.evaluate("(() => { const a = document.querySelector('a[href*=\"view=deck\"]'); return a ? a.getAttribute('href') : '' })()")
    say("deck link", href)
    if href:
        pg.goto(BASE + href.lstrip("?").join(["?", ""]) if href.startswith("?") else href); pg.wait_for_timeout(5000)
        say("pbar", pg.locator(".deck-pbar [data-dtab]").all_inner_texts())
        if pg.locator(".deck-pbar [data-dtab=stats]").count():
            pg.click(".deck-pbar [data-dtab=stats]"); pg.wait_for_timeout(800)
            say("sheet open", pg.evaluate("document.documentElement.classList.contains('deck-sheet-open')"), pg.url)
            pg.screenshot(path="probe_out/deck-sheet.png")
            pg.go_back(); pg.wait_for_timeout(600)
            say("after back open", pg.evaluate("document.documentElement.classList.contains('deck-sheet-open')"), pg.url)
    pg.goto(BASE + "?set=dsk"); pg.wait_for_timeout(5000)
    say("set page related", pg.locator("#setRelated a.set-rel").count(), "quick", pg.locator("#setQuick").count(), "setShop", pg.locator("#setShop").count(), "rakuten text", "楽天" in pg.inner_text("body"))
    pg.screenshot(path="probe_out/set-page.png")
    pg.goto(BASE + "?q=" + urllib.request.quote("赤単 除去")); pg.wait_for_timeout(6000)
    say("search 赤単 除去 tiles", pg.locator("#results .card-tile, .card-tile").count())
    say("page errors", errs)
    b.close()
