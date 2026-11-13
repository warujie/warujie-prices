# One-off: screenshots of the Commander combo panel on the staging test site (warujie.jp's thread work).
import sys, time
from playwright.sync_api import sync_playwright
BASE = "https://staging-warujie.warujie-mtg.workers.dev/"
CARDS = [("kiki", "5af7d96c-7be4-4700-ba26-71fe1784c4d5"), ("altar", "2406fe35-33ff-473b-8ae4-5119c7cd362a"), ("oracle", "5bc47197-a561-4fdb-8324-88a5ce274926")]
def wait_combos(page):
    for _ in range(60):
        page.evaluate("(() => { const w = document.getElementById('combosWatch'); if (w) w.scrollIntoView({block:'center'}); })()")
        if page.locator("#combosBox .combo-row").count(): return True
        time.sleep(0.5)
    return False
with sync_playwright() as p:
    b = p.chromium.launch()
    for dev, vp, scale in [("desktop", {"width": 1280, "height": 900}, 2), ("phone", {"width": 390, "height": 844}, 3)]:
        ctx = b.new_context(viewport=vp, device_scale_factor=scale, is_mobile=(dev == "phone"), has_touch=(dev == "phone"), locale="ja-JP")
        page = ctx.new_page()
        reqs = []
        page.on("request", lambda r: reqs.append(r.url))
        for name, cid in CARDS:
            reqs.clear()
            page.goto(BASE + "?card=" + cid, wait_until="domcontentloaded")
            page.wait_for_selector("#cardView .cp-name", timeout=60000)
            time.sleep(4)
            early = [u for u in reqs if "/data/c/" in u or "combo_ja" in u]
            print(dev, name, "combo files before scrolling:", len(early), flush=True)
            page.screenshot(path=f"out/{dev}-{name}-top.png")
            ok = wait_combos(page)
            time.sleep(2.5)
            sizes = []
            print(dev, name, "combos shown:", ok, page.locator("#combosBox .combos-heading").inner_text() if ok else "", flush=True)
            if ok:
                page.locator("#combosBox").screenshot(path=f"out/{dev}-{name}-combos.png")
                page.locator("#combosBox .combo-steps summary").first.click(); time.sleep(0.5)
                page.locator("#combosBox .combo-row").first.screenshot(path=f"out/{dev}-{name}-steps.png")
        ctx.close()
    # shard sizes, for the record
    ctx = b.new_context(); page = ctx.new_page(); page.goto(BASE, wait_until="domcontentloaded")
    for key in ["5a", "24", "5b"]:
        n = page.evaluate(f"fetch('/data/c/{key}.json.gz').then(r => r.arrayBuffer()).then(a => a.byteLength).catch(e => String(e))")
        print("shard", key, "bytes:", n, flush=True)
    b.close()
