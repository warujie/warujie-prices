# Phone layout options for the deck page's card pictures, on the staging test site
# (a throwaway probe for the site thread "Improve deck browsing in metagame tab"; never merge)
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
            if b"warujie-deck-extra" in urllib.request.urlopen(req, timeout=30).read(): say("build there after", i); return
        except Exception as e: say("wait", repr(e)[:120])
        time.sleep(30)
    say("build NOT seen")

A = """
.deck-grid, .deck-flow .deck-grid { gap: 10px 8px !important; }
.deck-card { display: grid !important; grid-template-columns: minmax(0, 1fr) auto; gap: 1px 4px !important; }
.deck-card .dc-pic, .deck-card .dc-name { grid-column: 1 / -1; }
.deck-card .dc-pic { margin-bottom: 3px; }
.dc-name { font-size: 11px !important; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; line-height: 1.35 !important; }
.dc-rate, .dc-yen { font-size: 10.5px !important; line-height: 1.3; }
.dc-yen { text-align: right; }
"""
B = """
.deck-grid, .deck-flow .deck-grid { grid-template-columns: repeat(4, minmax(0, 1fr)) !important; gap: 8px 5px !important; }
.deck-card { display: grid !important; grid-template-columns: minmax(0, 1fr) auto; gap: 0 2px !important; }
.deck-card .dc-pic { grid-column: 1 / -1; margin-bottom: 2px; }
.dc-name { display: none !important; }
.dc-count { min-width: 22px !important; padding: 0 5px !important; font-size: 11px !important; }
.dc-rate, .dc-yen { font-size: 10px !important; line-height: 1.3; }
.dc-yen { text-align: right; }
"""
DECK = "?view=deck&format=standard&days=30&deck=Mono%20Green%20Landfall"
def run(p):
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="ja-JP", color_scheme="dark")
    ctx.add_init_script("try { localStorage.setItem('akuchie-lang', 'ja'); localStorage.setItem('akuchie-deck-view', 'image'); } catch (e) {}")
    page = ctx.new_page(); page.set_default_navigation_timeout(120000)
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    def step(name, fn):
        try: fn(); say(name, "ok")
        except Exception as e: say(name, "FAILED", repr(e)[:400])
    def load():
        page.goto(SITE + DECK); page.wait_for_selector("#deckBody .deck-card img", timeout=90000); page.wait_for_timeout(8000)
    def to_main():
        page.evaluate("(() => { const e = document.querySelector('#deckBody .deck-group'); window.scrollTo(0, e.getBoundingClientRect().top + scrollY - 130); })()")
        page.wait_for_timeout(2500)
    def shot(name): page.screenshot(path=f"{OUT}{name}.png")
    def strip():
        load(); page.evaluate("window.scrollTo(0, 260)"); page.wait_for_timeout(2500); shot("q1-strip")
    step("strip", strip)
    def dx_closed():
        page.evaluate("(() => { const e = document.querySelector('#deckBody .deck-dx'); window.scrollTo(0, e.getBoundingClientRect().top + scrollY - 300); })()")
        page.wait_for_timeout(2000); shot("q2-details-closed")
    step("closed", dx_closed)
    def dx_open():
        page.click("#deckDxBtn"); page.wait_for_timeout(1500)
        page.evaluate("(() => { const e = document.querySelector('#deckBody .deck-dx'); window.scrollTo(0, e.getBoundingClientRect().top + scrollY - 140); })()")
        page.wait_for_timeout(1500); shot("q3-details-open")
    step("open", dx_open)
    say("errors:", errs)
    b.close()

if __name__ == "__main__":
    wait_for_build()
    with sync_playwright() as p: run(p)
