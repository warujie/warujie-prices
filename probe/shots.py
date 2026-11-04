# Screenshots of the metagame tab's sample lists, deck search by card and the card page's decks box on the
# staging test site (a throwaway probe for the site thread "Improve deck browsing in metagame tab"; never merge)
import os, time, urllib.request
from playwright.sync_api import sync_playwright
SITE = os.environ.get("SITE", "https://staging-warujie.warujie-mtg.workers.dev/")
OUT = "probe_out/"
os.makedirs(OUT, exist_ok=True)
log = open(OUT + "log.txt", "w")
def say(*a): print(*a, file=log, flush=True)

def wait_for_build():
    for i in range(40):
        try:
            req = urllib.request.Request(SITE + "?probe=" + str(time.time()), headers={"User-Agent": "warujie.jp probe"})
            if b"align-items: stretch; gap: 1px; overflow: hidden" in urllib.request.urlopen(req, timeout=30).read(): say("build there after", i); return
        except Exception as e: say("wait", repr(e)[:120])
        time.sleep(30)
    say("build NOT seen")

BOLT = "b68be6a7-0515-42e0-abe9-b3f14b118c19"
def run(p):
    b = p.chromium.launch()
    for tag, w, h in (("desktop", 1280, 900), ("phone", 390, 844)):
        phone = tag == "phone"
        ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2, is_mobile=phone, has_touch=phone, locale="ja-JP")
        ctx.add_init_script("try { localStorage.setItem('akuchie-lang', 'ja'); } catch (e) {}")
        page = ctx.new_page(); page.set_default_navigation_timeout(120000)
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        def step(name, fn):
            try: fn(); say(tag, name, "ok")
            except Exception as e: say(tag, name, "FAILED", repr(e)[:400])
        def shot(name): page.screenshot(path=f"{OUT}{name}-{tag}.png")
        def meta():
            page.goto(SITE + "?view=meta&format=modern&days=30")
            page.wait_for_selector("#metaBody .meta-row", timeout=90000); page.wait_for_timeout(4000)
        def lists():
            meta()
            row = page.locator("#metaBody .meta-row").nth(1)
            if phone: row.click(); page.wait_for_timeout(400)
            row.locator(".meta-lists-btn").click(); page.wait_for_selector("#metaBody .mlp .mlp-cols", timeout=60000); page.wait_for_timeout(2500)
            page.evaluate("(() => { const r = document.querySelectorAll('#metaBody .meta-row')[1]; window.scrollTo(0, r.getBoundingClientRect().top + scrollY - (%d)); })()" % (130 if phone else 90))
            page.wait_for_timeout(1500); shot("1-meta-lists")
            if phone:
                page.evaluate("document.querySelector('#metaBody .mlp').scrollIntoView({ block: 'start' }); scrollBy(0, -130)"); page.wait_for_timeout(1200); shot("1b-meta-lists")
        step("lists", lists)
        def find():
            meta()
            page.click("#metaFind"); page.locator("#metaFind").type("ボルト", delay=80); page.wait_for_selector("#metaFindList .mfind-card", timeout=30000); page.wait_for_timeout(1500)
            shot("2-meta-search-card")
            page.keyboard.press("Enter"); page.wait_for_timeout(3000)
            if phone: page.evaluate("document.activeElement.blur()")
            shot("2b-meta-decks-with-card")
            page.click("#metaFind"); page.locator("#metaFind").type("ボロス", delay=80); page.wait_for_selector("#metaFindList .suggest-item", timeout=30000); page.wait_for_timeout(1500)
            shot("2c-meta-search-deck-and-cards")
        step("find", find)
        def deck():
            page.goto(SITE + "?view=deck&format=modern&days=30&deck=Boros%20Energy&list=3")
            page.wait_for_selector("#deckBody .dlp-tile", timeout=90000); page.wait_for_timeout(6000)
            shot("3-deck-lists")
            page.click('.dlp-nav[data-dlstep="1"]'); page.wait_for_timeout(3000); shot("3b-deck-next-list")
        step("deck", deck)
        def card():
            page.goto(SITE + "?card=" + BOLT)
            page.wait_for_selector("#cardViewCard .cp-name", timeout=90000); page.wait_for_timeout(2000)
            page.evaluate("document.getElementById('cardDecksWatch').scrollIntoView()")
            page.wait_for_selector("#cardDecksBox:not([hidden]) .cdk-row", timeout=60000); page.wait_for_timeout(2000)
            page.evaluate("document.getElementById('cardDecksBox').scrollIntoView({ block: 'start' }); scrollBy(0, -%d)" % (140 if phone else 250))
            page.wait_for_timeout(1500); shot("4-card-page-decks")
        step("card", card)
        say(tag, "errors:", errs)
        ctx.close()
    b.close()

if __name__ == "__main__":
    wait_for_build()
    with sync_playwright() as p: run(p)
