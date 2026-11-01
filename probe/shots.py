# Screenshots of the deck builder opening on 統計 and the card peek on the staging test site,
# plus mock-ups of four more ideas drawn over it (a throwaway probe for the site thread)
import json, os, time, urllib.parse, urllib.request
from playwright.sync_api import sync_playwright
SITE = os.environ.get("SITE", "https://staging-warujie.warujie-mtg.workers.dev/")
OUT = "probe_out/"
DECK = ("About\nName Yawgmoth\n\nDeck\n4 Yawgmoth, Thran Physician\n4 Delighted Halfling\n3 Young Wolf\n4 Agatha's Soul Cauldron\n3 Walking Ballista\n"
        "4 Strangleroot Geist\n2 Blood Artist\n4 Chord of Calling\n4 Eldritch Evolution\n4 Grist, the Hunger Tide\n1 Geralf, Visionary Stitcher\n"
        "4 Overgrown Tomb\n6 Forest\n3 Swamp\n4 Twilight Mire\n4 Llanowar Wastes\n2 Boseiju, Who Endures\n\nSideboard\n2 Thoughtseize\n3 Endurance\n")
now = int(time.time() * 1000)
STORE = {"v": 1, "cur": "yaw1", "folders": [], "decks": [{"id": "yaw1", "fmt": "modern", "text": DECK, "made": now, "edited": now}]}
def init(lang, view):
    return ("try { localStorage.setItem('warujie-decks', %s); localStorage.setItem('akuchie-theme', 'dark'); localStorage.setItem('akuchie-lang', '%s');"
            " localStorage.setItem('akuchie-deck-view', '%s'); } catch (e) {}") % (json.dumps(json.dumps(STORE, ensure_ascii=False)), lang, view)
MOCKS = open(os.path.join(os.path.dirname(__file__), "mocks.js"), encoding="utf-8").read()
os.makedirs(OUT, exist_ok=True)
log = open(OUT + "log.txt", "w")
def say(*a): print(*a, file=log, flush=True)

def wait_for_build():
    for i in range(40):
        try:
            req = urllib.request.Request(SITE + "?probe=" + str(time.time()), headers={"User-Agent": "warujie.jp probe"})
            if b"cardPeek" in urllib.request.urlopen(req, timeout=30).read(): say("build there after", i); return
        except Exception as e: say("wait", repr(e)[:120])
        time.sleep(30)
    say("build NOT seen")

def run(p):
    b = p.chromium.launch()
    for tag, w, h, lang, view in (("desktop", 1280, 860, "ja", "image"), ("desktop-list", 1280, 860, "ja", "list"), ("desktop-en", 1280, 860, "en", "image"), ("phone", 390, 844, "ja", "image")):
        phone = tag == "phone"
        ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if phone else 1, is_mobile=phone, has_touch=phone, locale="ja-JP", color_scheme="dark")
        ctx.add_init_script(init(lang, view))
        page = ctx.new_page(); page.set_default_navigation_timeout(120000)
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        def step(name, fn):
            try: fn(); say(tag, name, "ok")
            except Exception as e: say(tag, name, "FAILED", repr(e)[:400])
        def builder():
            page.goto(SITE + "?view=import&d=yaw1")
            page.wait_for_selector("#importBody .deck-section", timeout=90000); page.wait_for_timeout(5000)
        def hover_shot(sel, name, nth=3):
            page.mouse.move(5, 5); page.wait_for_timeout(300)
            page.locator(sel).nth(nth).hover(); page.wait_for_selector("#cardPeek:not([hidden]) img", timeout=20000); page.wait_for_timeout(2500)
            page.screenshot(path=f"{OUT}{name}.png")
        if tag == "desktop":
            def a():
                builder()
                say("tab:", page.get_attribute("#impTabs [aria-selected=true]", "data-pane"))
                page.screenshot(path=f"{OUT}1-builder-opens-on-stats-desktop.png")
                hover_shot("#importBody a.deck-card", "2-peek-deck-picture-desktop", 2)
            step("builder", a)
            def c():
                page.goto(SITE + "?q=" + urllib.parse.quote("除去 黒")); page.wait_for_selector("#cardGrid .card-tile", timeout=90000); page.wait_for_timeout(4000)
                say("grid tile width", page.evaluate("document.querySelector('#cardGrid .card-tile img').getBoundingClientRect().width"))
                hover_shot("#cardGrid a.card-tile", "4-peek-results-desktop", 1)
            step("results", c)
            def d():
                page.goto(SITE + "?view=meta"); page.wait_for_selector("#metaBody a[href*='view=deck']", timeout=90000); page.wait_for_timeout(2500)
                hover_shot("#metaBody a.meta-card", "5-peek-metagame-names-desktop", 2)
            step("meta", d)
            # mock-ups
            def m():
                builder(); page.add_script_tag(content=MOCKS); page.wait_for_timeout(300)
                page.evaluate("mockHighlight()"); page.wait_for_timeout(1500); page.screenshot(path=f"{OUT}idea1-stats-filter-deck-desktop.png")
                builder(); page.add_script_tag(content=MOCKS)
                page.evaluate("mockQuickAdd()"); page.wait_for_timeout(2500); page.screenshot(path=f"{OUT}idea2-quick-add-desktop.png")
                builder(); page.add_script_tag(content=MOCKS)
                page.mouse.move(5, 5); page.locator("#importBody a.deck-card").nth(3).hover(); page.wait_for_selector("#cardPeek:not([hidden]) img", timeout=20000)
                say("peek info", page.evaluate("mockPeekInfo()")); page.wait_for_timeout(2500); page.screenshot(path=f"{OUT}idea4-peek-price-formats-desktop.png")
            step("mocks", m)
        elif tag == "desktop-list":
            def a():
                builder(); hover_shot("#importBody a.dl-name", "3-peek-deck-list-desktop", 5)
            step("list", a)
        elif tag == "desktop-en":
            def a():
                builder(); hover_shot("#importBody a.deck-card", "6-peek-english-desktop", 2)
            step("en", a)
        else:
            def a():
                builder(); page.screenshot(path=f"{OUT}7-builder-phone.png")
                page.add_script_tag(content=MOCKS); page.evaluate("mockHold()"); page.wait_for_timeout(2500)
                page.screenshot(path=f"{OUT}idea3-hold-to-see-phone.png")
            step("phone", a)
        say(tag, "errors:", errs)
        ctx.close()
    b.close()

if __name__ == "__main__":
    wait_for_build()
    with sync_playwright() as p:
        run(p)
