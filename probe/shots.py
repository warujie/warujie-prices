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
            if b"impQuick" in urllib.request.urlopen(req, timeout=30).read(): say("build there after", i); return
        except Exception as e: say("wait", repr(e)[:120])
        time.sleep(30)
    say("build NOT seen")

def run(p):
    b = p.chromium.launch()
    for tag, w, h, lang in (("desktop", 1280, 860, "ja"), ("desktop-en", 1280, 860, "en"), ("phone", 390, 844, "ja")):
        phone = tag == "phone"
        ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if phone else 1, is_mobile=phone, has_touch=phone, locale="ja-JP", color_scheme="dark")
        ctx.add_init_script(init(lang, "image"))
        page = ctx.new_page(); page.set_default_navigation_timeout(120000)
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        def step(name, fn):
            try: fn(); say(tag, name, "ok")
            except Exception as e: say(tag, name, "FAILED", repr(e)[:400])
        def builder():
            page.goto(SITE + "?view=import&d=yaw1")
            page.wait_for_selector("#importBody .deck-section", timeout=90000); page.wait_for_timeout(5000)
        def peek(nth, name):
            page.mouse.move(5, 5); page.wait_for_timeout(300)
            page.locator("#importBody a.deck-card").nth(nth).hover(); page.wait_for_selector("#cardPeek:not([hidden]) .peek-info", timeout=20000); page.wait_for_timeout(3500)
            say(tag, name, page.inner_text("#cardPeek .peek-info").replace("\n", " | "))
            page.screenshot(path=f"{OUT}{name}.png")
        if tag == "desktop":
            def a():
                builder()
                page.click("#impPaneStats [data-st-pick='cv:2']"); page.wait_for_timeout(1500)
                say("pick note:", page.inner_text("#importBody .st-pick-note"))
                page.screenshot(path=f"{OUT}1-stats-pick-curve-desktop.png")
                page.click("#impPaneStats [data-st-pick='type:land']"); page.wait_for_timeout(1500)
                page.screenshot(path=f"{OUT}1b-stats-pick-lands-desktop.png")
                page.click("#importBody [data-st-clear]"); page.wait_for_timeout(500)
                page.click("#impQuick"); page.keyboard.type("4 いなず"); page.wait_for_selector("#impQuickList [data-qi]", timeout=20000); page.wait_for_timeout(2500)
                page.screenshot(path=f"{OUT}2-quick-add-desktop.png")
                page.keyboard.press("Enter"); page.wait_for_timeout(2500)
                page.screenshot(path=f"{OUT}2b-quick-add-done-desktop.png")
                page.evaluate("document.activeElement.blur()")
                peek(3, "4-peek-price-formats-desktop")
            step("builder", a)
        elif tag == "desktop-en":
            step("en", lambda: (builder(), peek(2, "4b-peek-price-formats-english-desktop")))
        else:
            def a():
                builder()
                page.evaluate("""() => { const a = document.querySelectorAll('#importBody a.deck-card')[1]; const r = a.getBoundingClientRect();
                    a.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, pointerType: 'touch', clientX: r.left + 30, clientY: r.top + 30 })); }""")
                page.wait_for_selector("#cardHold:not([hidden]) img", timeout=20000); page.wait_for_timeout(3500)
                page.screenshot(path=f"{OUT}3-hold-card-phone.png")
            step("hold", a)
        say(tag, "errors:", errs)
        ctx.close()
    b.close()


if __name__ == "__main__":
    wait_for_build()
    with sync_playwright() as p:
        run(p)
