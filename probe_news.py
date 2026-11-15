from playwright.sync_api import sync_playwright
U = "https://staging-warujie.warujie-mtg.workers.dev/?view=news"
with sync_playwright() as p:
    b = p.chromium.launch()
    for name, w, h in [("desktop", 1280, 1600), ("phone", 390, 3000)]:
        pg = b.new_page(viewport={"width": w, "height": h})
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(U, wait_until="domcontentloaded", timeout=60000)
        try: pg.wait_for_selector("#newsShops .nw-post, #newsShops .nw-empty:not(:has(.spinner))", timeout=40000)
        except Exception as e: print("wait", e)
        pg.wait_for_timeout(6000)
        pg.screenshot(path=f"probe_out/{name}.png")
        print(name, "errors", errs)
        print(pg.evaluate("({items: newsState.data && newsState.data.items.length, status: newsState.status, posts: newsState.x && newsState.x.length, big: newsState.big && newsState.big.length, ev: evCal.status, bigJp: evCal.events.filter(e => e.big && e.d >= todayJst()).length, shops: [...document.querySelectorAll('#newsShops .nw-post-store')].map(e => e.textContent), text: [...document.querySelectorAll('#newsShops .nw-post-text')].length})"))
    b.close()
