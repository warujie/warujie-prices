# Screenshots of the deck builder's round 3 (foil shine and dots, finishes, commander box, phone sheet) on the staging test site (a throwaway probe)
import json, os, time, urllib.parse, urllib.request
from playwright.sync_api import sync_playwright
SITE = os.environ.get("SITE", "https://staging-warujie.warujie-mtg.workers.dev/")
OUT = os.environ.get("OUT", "probe_out/")
DECK = ("About\nName ボロス・バーン\n\nDeck\n4 稲妻\n4 Ragavan, Nimble Pilferer\n4 Monastery Swiftspear\n4 ボロスの魔除け\n4 Lightning Helix\n"
        "4 Skewer the Critics\n4 Lava Spike\n4 Rift Bolt\n4 Goblin Guide *F*\n4 Sacred Foundry\n4 Inspiring Vantage\n4 Arid Mesa\n12 Mountain\n\nSideboard\n2 Blood Moon\n3 Path to Exile\n\nMaybeboard\n2 Eidolon of the Great Revel\n2 Fireblast\n")
DECK2 = "About\nName エルフ\n\nDeck\n4 Llanowar Elves\n4 Elvish Mystic\n4 Heritage Druid\n4 Nettle Sentinel\n4 Elvish Archdruid\n20 Forest\n"
DECK3 = ("About\nName アトラクサ\n\nCommander\n1 Atraxa, Praetors' Voice\n\nDeck\n1 Sol Ring *F*\n1 Arcane Signet\n1 Swords to Plowshares\n1 Cultivate\n"
         "1 Doubling Season *F*\n1 Deepglow Skate\n1 Evolution Sage\n1 Command Tower\n1 Jace, Multiverse Architect *F*\n1 Rhystic Study\n1 Smothering Tithe\n1 Avenger of Zendikar\n1 Parallel Lives\n"
         "1 Hallowed Fountain\n1 Breeding Pool\n1 Kodama's Reach\n1 Beast Within\n10 Forest\n10 Plains\n10 Island\n10 Swamp\n\nMaybeboard\n1 Cyclonic Rift\n")
now = int(time.time() * 1000)
STORE = {"v": 1, "cur": "burn1", "folders": ["大会用", "統率者"], "decks": [
    {"id": "burn1", "fmt": "modern", "text": DECK, "made": now, "edited": now, "folder": "大会用"},
    {"id": "atx1", "fmt": "commander", "text": DECK3, "made": now - 86400000, "edited": now - 86400000, "folder": "統率者"},
    {"id": "elf1", "fmt": "pauper", "text": DECK2, "made": now - 86400000 * 3, "edited": now - 86400000 * 3}]}
WANT = "2 Blood Moon\n1 Sacred Foundry\n1 The One Ring\n1 Rhystic Study\n"
INIT = "try { if (!localStorage.getItem('probe-seeded')) { localStorage.setItem('warujie-decks', %s); localStorage.setItem('warujie-want-list', %s); localStorage.setItem('akuchie-theme', 'light'); localStorage.setItem('akuchie-market', 'us'); localStorage.setItem('probe-seeded', '1'); } } catch (e) {}" % (
    json.dumps(json.dumps(STORE, ensure_ascii=False)), json.dumps(WANT))
os.makedirs(OUT, exist_ok=True)
log = open(OUT + "log.txt", "w")


def wait_for_build():
    # the test site has the new build once its page has the 統率者 box
    for i in range(40):
        try:
            req = urllib.request.Request(SITE + "?probe=" + str(time.time()), headers={"User-Agent": "warujie.jp probe"})
            if b"imp-title-row" in urllib.request.urlopen(req, timeout=30).read(): print("build there after", i, file=log, flush=True); return
        except Exception as e: print("wait", repr(e)[:120], file=log, flush=True)
        time.sleep(30)
    print("build NOT seen", file=log, flush=True)


def builder_ready(page):
    page.wait_for_selector("#importBody .deck-section", timeout=90000)
    try: page.wait_for_function("[...document.querySelectorAll('.want-bar')].some(e => e.textContent.includes('約') || e.textContent.includes('¥'))", timeout=60000)
    except Exception: print("no price bar", file=log, flush=True)
    page.wait_for_timeout(3000)


def run(p):
    b = p.chromium.launch()
    for w, h, tag in ((1280, 900, "desktop"), (390, 844, "phone")):
        ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if tag == "phone" else 1, is_mobile=tag == "phone", has_touch=tag == "phone", locale="ja-JP")
        ctx.add_init_script(INIT)
        page = ctx.new_page()
        page.set_default_navigation_timeout(120000)
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        def step(name, fn):
            try: fn()
            except Exception as e: print(tag, name, "FAILED", repr(e)[:400], file=log, flush=True)
        def head():
            page.goto(SITE + "?view=import&d=atx1"); builder_ready(page)
            page.screenshot(path=f"{OUT}1-head-commander-{tag}.png")
            print(tag, "CMDR VALUE:", page.input_value("#impCmdr"), file=log, flush=True)
            page.click("#impCmdr"); page.wait_for_timeout(300)
            page.screenshot(path=f"{OUT}2-commander-focused-{tag}.png")
            page.locator("#impCmdr").evaluate("e => e.blur()"); page.wait_for_timeout(300)
        step("head", head)
        def foil():
            if page.locator("#importBody [data-iview=image]").count(): page.click("#importBody [data-iview=image]"); page.wait_for_timeout(4000)
            el = page.locator("#importBody .dc-pic.foil").first
            el.scroll_into_view_if_needed(); page.evaluate("window.scrollBy(0, -120)"); page.wait_for_timeout(2000)
            page.screenshot(path=f"{OUT}3-foil-pictures-{tag}.png")
            page.wait_for_timeout(4500)
            page.screenshot(path=f"{OUT}3b-foil-pictures-later-{tag}.png")
            page.click("#importBody [data-iview=list]"); page.wait_for_timeout(1500)
            el = page.locator("#importBody .dl-name .foil-dot").first
            el.scroll_into_view_if_needed(); page.evaluate("window.scrollBy(0, -200)"); page.wait_for_timeout(500)
            page.screenshot(path=f"{OUT}4-foil-dots-list-{tag}.png")
        step("foil", foil)
        def finishes():
            for name in ("Jace, Multiverse Architect", "Sol Ring"):
                sel = f"#importBody [data-ip='main'][data-in=\"{name}\"][data-imp-act='art']"
                page.locator(sel).first.scroll_into_view_if_needed(); page.click(sel); page.wait_for_selector("#artPicker .ap-item", timeout=60000); page.wait_for_timeout(3000)
                page.screenshot(path=f"{OUT}5-art-picker-{name.split(',')[0].replace(' ', '-').lower()}-{tag}.png")
                print(tag, name, "FINISHES:", page.evaluate("[...document.querySelectorAll('#artPicker [data-ap-finish]')].map(b => b.textContent)"), "items", page.locator("#artPicker .ap-item").count(), "fin-tags", page.locator("#artPicker .fin-tag").count(), file=log, flush=True)
                page.keyboard.press("Escape"); page.wait_for_timeout(500)
        step("finishes", finishes)
        if tag == "phone":
            def sheet():
                page.evaluate("window.scrollTo(0, 0)"); page.wait_for_timeout(300)
                page.click("#impPbarStats"); page.wait_for_timeout(120)
                page.screenshot(path=f"{OUT}6-sheet-sliding-{tag}.png")
                page.wait_for_timeout(600)
                page.screenshot(path=f"{OUT}6b-sheet-open-{tag}.png")
            step("sheet", sheet)
        def card():
            page.goto(SITE); page.wait_for_timeout(2500)
            sel = "#searchInput" if page.locator("#searchInput").is_visible() else "#heroInput"
            page.fill(sel, "Sol Ring"); page.press(sel, "Escape"); page.press(sel, "Enter")
            page.wait_for_selector("#cardGrid .card-tile", timeout=60000); page.wait_for_timeout(1500)
            page.locator("#cardGrid .card-tile").first.click(); page.wait_for_selector("#cardViewCard .cp-name-sub, #cardViewCard h1, #cardViewCard", timeout=60000); page.wait_for_timeout(6000)
            v = page.locator("#versionMenuPanel")
            if v.count():
                v.scroll_into_view_if_needed(); page.wait_for_timeout(2500)
                page.screenshot(path=f"{OUT}7-card-page-printings-{tag}.png")
                print(tag, "CARD fin-tags:", page.locator("#versionMenuPanel .fin-tag").count(), file=log, flush=True)
        step("card", card)
        print(tag, "errors:", errs, file=log, flush=True)
        ctx.close()
    b.close()


if __name__ == "__main__":
    wait_for_build()
    with sync_playwright() as p:
        run(p)
    log.close()
