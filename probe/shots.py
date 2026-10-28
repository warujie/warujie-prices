# Preview of the planned deck builder tools: the staging test site with mock-ups drawn on it (a throwaway probe)
import json, os, sys, time
from playwright.sync_api import sync_playwright
SITE = os.environ.get("SITE", "https://staging-warujie.warujie-mtg.workers.dev/")
OUT = os.environ.get("OUT", "probe_out/")
HERE = os.path.dirname(os.path.abspath(__file__)) + "/"
MOCK_JS = open(HERE + "mock.js", encoding="utf-8").read()
MOCK_CSS = open(HERE + "mock.css", encoding="utf-8").read()
DECK = ("About\nName ボロス・バーン\n\nDeck\n4 稲妻\n4 Ragavan, Nimble Pilferer\n4 Monastery Swiftspear\n4 ボロスの魔除け\n4 Lightning Helix\n"
        "4 Skewer the Critics\n4 Lava Spike\n4 Rift Bolt\n4 Goblin Guide\n4 Sacred Foundry\n4 Inspiring Vantage\n4 Arid Mesa\n12 Mountain\n\nSideboard\n2 Blood Moon\n3 Path to Exile\n")
DECK2 = "About\nName エルフ\n\nDeck\n4 Llanowar Elves\n4 Elvish Mystic\n4 Heritage Druid\n4 Nettle Sentinel\n4 Elvish Archdruid\n20 Forest\n"
DECK3 = ("About\nName アトラクサ\n\nCommander\n1 Atraxa, Praetors' Voice\n\nDeck\n1 Sol Ring\n1 Arcane Signet\n1 Swords to Plowshares\n1 Cultivate\n"
         "1 Doubling Season\n1 Deepglow Skate\n1 Evolution Sage\n1 Command Tower\n10 Forest\n10 Plains\n10 Island\n10 Swamp\n")
now = int(time.time() * 1000)
STORE = {"v": 1, "cur": "burn1", "decks": [
    {"id": "burn1", "fmt": "modern", "text": DECK, "made": now, "edited": now},
    {"id": "atx1", "fmt": "commander", "text": DECK3, "made": now - 86400000, "edited": now - 86400000},
    {"id": "elf1", "fmt": "pauper", "text": DECK2, "made": now - 86400000 * 3, "edited": now - 86400000 * 3}]}
WANT = "2 Blood Moon\n1 Sacred Foundry\n1 The One Ring\n1 Rhystic Study\n"
INIT = "try { if (!localStorage.getItem('probe-seeded')) { localStorage.setItem('warujie-decks', %s); localStorage.setItem('warujie-want-list', %s); localStorage.setItem('akuchie-theme', 'light'); localStorage.setItem('probe-seeded', '1'); } } catch (e) {}" % (
    json.dumps(json.dumps(STORE, ensure_ascii=False)), json.dumps(WANT))
os.makedirs(OUT, exist_ok=True)
log = open(OUT + "log.txt", "w")


def mock(page):
    page.add_style_tag(content=MOCK_CSS)
    page.add_script_tag(content=MOCK_JS)


def builder_ready(page):
    page.wait_for_selector("#importBody .deck-section", timeout=90000)
    try: page.wait_for_function("[...document.querySelectorAll('.want-bar')].some(e => e.textContent.includes('約') || e.textContent.includes('¥'))", timeout=60000)
    except Exception: print("no price bar", file=log, flush=True)
    page.wait_for_timeout(2500)


def run(p, route=None):
    b = p.chromium.launch()
    for w, h, tag in ((1280, 900, "desktop"), (390, 844, "phone")):
        ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if tag == "phone" else 1, is_mobile=tag == "phone", has_touch=tag == "phone", locale="ja-JP")
        ctx.add_init_script(INIT)
        if route: ctx.route("**/*", route)
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        def step(name, fn):
            try: fn()
            except Exception as e: print(tag, name, "FAILED", repr(e)[:400], file=log, flush=True)
        def open_precon():
            page.goto(SITE + "?view=decks"); page.wait_for_selector("#dkGrid .dk-card", timeout=60000)
            page.click("#preconBtn")
            try:
                page.wait_for_selector("#preconList .pc-deck", timeout=60000)
                page.locator("#preconList .pc-deck").nth(1).click()
            except Exception:
                print("no precons, using the Atraxa deck", file=log, flush=True); page.goto(SITE + "?view=import&d=atx1")
            builder_ready(page); mock(page)
        # A: one thin line under the bar
        def a1():
            page.goto(SITE + "?view=import&d=burn1"); builder_ready(page); mock(page)
            page.evaluate("MOCK.slimLine({ maybe: ['Eidolon of the Great Revel', 'Fireblast'] })"); page.wait_for_timeout(2500)
            page.screenshot(path=f"{OUT}A1-line-{tag}.png")
            page.screenshot(path=f"{OUT}A1-line-full-{tag}.png", full_page=True)
        step("A1", a1)
        def a2():
            open_precon()
            page.evaluate("MOCK.slimLine({ commander: true })"); page.wait_for_timeout(3000)
            page.screenshot(path=f"{OUT}A2-line-commander-{tag}.png")
        step("A2", a2)
        # B: a 統計 tab in the left panel (a sheet on phones)
        def b1():
            open_precon()
            page.evaluate("MOCK.slimTab({ commander: true, open: true })"); page.wait_for_timeout(3000)
            page.screenshot(path=f"{OUT}B1-tab-commander-{tag}.png")
            if tag == "phone":
                page.evaluate("setImpSheet(false)"); page.wait_for_timeout(800)
                page.screenshot(path=f"{OUT}B2-tab-closed-phone.png")
        step("B1", b1)
        print(tag, "errors:", errs, file=log, flush=True)
        ctx.close()
    b.close()


if __name__ == "__main__":
    with sync_playwright() as p:
        run(p)
    log.close()
