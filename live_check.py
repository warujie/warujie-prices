# Checks the live site (warujie.jp's Worker on workers.dev) after the 2026-10-27 publish.
from playwright.sync_api import sync_playwright
SITE = "https://warujie.warujie-mtg.workers.dev/"
out = []
def log(*a): out.append(" ".join(str(x) for x in a)); print(*a, flush=True)
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1280, "height": 900}, user_agent="warujie.jp live check (GitHub Actions)")
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(SITE + "?set=blc"); pg.wait_for_timeout(8000)
    log("set blc: precon box visible", pg.locator("#setPrecons").is_visible(), "decks", pg.locator("#setPrecons .pc-deck").count(), "deck list shown", pg.locator("#setPrecons .pc-list").is_visible())
    log("set blc: text", pg.locator("#setPrecons").inner_text()[:300].replace("\n", " | ") if pg.locator("#setPrecons").count() else "none")
    if pg.locator("#setPrecons .pc-tog").count():
        pg.locator("#setPrecons .pc-tog").click(); pg.wait_for_timeout(500)
        log("after 表示: list shown", pg.locator("#setPrecons .pc-list").is_visible(), pg.locator("#setPrecons").inner_text()[:400].replace("\n", " | "))
    pg.goto(SITE + "?view=import"); pg.wait_for_timeout(8000)
    log("import: precon decks loaded", pg.evaluate("loadPrecons().then(d => d ? [d.decks.length, Object.keys(d.sets).length] : null)"), "picker visible", pg.locator("#preconPick").is_visible())
    pg.goto(SITE); pg.wait_for_selector("#heroInput", state="visible"); pg.wait_for_timeout(3000)
    pg.fill("#heroInput", "アジャニ"); pg.press("#heroInput", "Enter"); pg.wait_for_timeout(8000)
    t = pg.locator("#cardGrid .card-tile")
    log("search アジャニ: tiles", t.count(), "filter button", pg.locator("#filterOpenBtn").is_visible(), "first", t.first.inner_text()[:120].replace("\n", " | ") if t.count() else "", "img", t.first.locator("img").get_attribute("src") if t.count() else "")
    pg.screenshot(path="probe_out/search.png")
    pg.goto(SITE + "?view=about"); pg.wait_for_timeout(5000)
    log("about: rows", pg.locator("#aboutView .src-row").count(), "Rakuten mentioned", "楽天" in pg.content() and "Rakuten" in pg.locator("#aboutView").inner_text())
    log("home shop boxes present", pg.locator("#homeShop").count())
    pg.screenshot(path="probe_out/about.png")
    log("page errors", errs[:5])
    b.close()
open("probe_out/live_check.txt", "w").write("\n".join(out) + "\n")
