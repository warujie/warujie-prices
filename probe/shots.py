# Screenshots of the deck builder's round 2 (commander box, cart, foil, filters, other names) on the staging test site (a throwaway probe)
import json, os, time, urllib.parse, urllib.request
from playwright.sync_api import sync_playwright
SITE = os.environ.get("SITE", "https://staging-warujie.warujie-mtg.workers.dev/")
OUT = os.environ.get("OUT", "probe_out/")
DECK = ("About\nName ボロス・バーン\n\nDeck\n4 稲妻\n4 Ragavan, Nimble Pilferer\n4 Monastery Swiftspear\n4 ボロスの魔除け\n4 Lightning Helix\n"
        "4 Skewer the Critics\n4 Lava Spike\n4 Rift Bolt\n4 Goblin Guide *F*\n4 Sacred Foundry\n4 Inspiring Vantage\n4 Arid Mesa\n12 Mountain\n\nSideboard\n2 Blood Moon\n3 Path to Exile\n\nMaybeboard\n2 Eidolon of the Great Revel\n2 Fireblast\n")
DECK2 = "About\nName エルフ\n\nDeck\n4 Llanowar Elves\n4 Elvish Mystic\n4 Heritage Druid\n4 Nettle Sentinel\n4 Elvish Archdruid\n20 Forest\n"
DECK3 = ("About\nName アトラクサ\n\nCommander\n1 Atraxa, Praetors' Voice\n\nDeck\n1 Sol Ring *F*\n1 Arcane Signet\n1 Swords to Plowshares\n1 Cultivate\n"
         "1 Doubling Season *F*\n1 Deepglow Skate\n1 Evolution Sage\n1 Command Tower\n1 Rhystic Study\n1 Smothering Tithe\n1 Avenger of Zendikar\n1 Parallel Lives\n"
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
            if b"impCmdr" in urllib.request.urlopen(req, timeout=30).read(): print("build there after", i, file=log, flush=True); return
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
        def cmd():
            page.goto(SITE + "?view=import&d=atx1"); builder_ready(page)
            if tag == "phone": page.evaluate("setImpSheet(false)"); page.wait_for_timeout(500)
            page.screenshot(path=f"{OUT}1-head-pips-commander-{tag}.png")
            page.fill("#impCmdr", "ゴルガリ" if tag == "desktop" else "ジャラド"); page.wait_for_timeout(2500)
            page.screenshot(path=f"{OUT}2-commander-search-{tag}.png")
            print(tag, "CMDR:", page.inner_text("#impCmdrList")[:300].replace("\n", " | "), file=log, flush=True)
            page.fill("#impCmdr", ""); page.wait_for_timeout(300)
            page.click("#impCart summary"); page.wait_for_timeout(800)
            page.screenshot(path=f"{OUT}3-cart-{tag}.png")
            page.click("#impCart summary"); page.wait_for_timeout(300)
            if tag == "phone": page.evaluate("window.scrollTo(0, 0)")
            page.click("#impTabs [data-pane=stats]" if tag == "desktop" else "#impPbarStats"); page.wait_for_timeout(5000)
            page.screenshot(path=f"{OUT}4-stats-hand-icons-{tag}.png")
            page.click("#impHandBtn"); page.wait_for_timeout(3500)
            page.screenshot(path=f"{OUT}5-hand-{tag}.png"); page.keyboard.press("Escape"); page.wait_for_timeout(400)
            if tag == "phone": page.evaluate("setImpSheet(false)"); page.wait_for_timeout(500)
            if page.locator("#importBody [data-iview=image]").count(): page.click("#importBody [data-iview=image]"); page.wait_for_timeout(4000)
            el = page.locator("#importBody .dc-pic.foil").first
            if el.count():
                el.scroll_into_view_if_needed(); page.wait_for_timeout(1500)
                page.screenshot(path=f"{OUT}6-foil-pictures-{tag}.png")
            else: print(tag, "no foil pictures", file=log, flush=True)
            if page.locator("#importBody [data-iview=list]").count(): page.click("#importBody [data-iview=list]"); page.wait_for_timeout(1500)
            el = page.locator("#importBody .foil-tag").first
            if el.count(): el.scroll_into_view_if_needed(); page.wait_for_timeout(500); page.screenshot(path=f"{OUT}7-foil-list-{tag}.png")
            page.screenshot(path=f"{OUT}8-commander-full-{tag}.png", full_page=True)
        step("commander", cmd)
        def filt():
            page.goto(SITE + "?view=import&d=burn1"); builder_ready(page)
            if tag == "phone": page.click("#impPbar button"); page.wait_for_timeout(800)
            page.click("#filterOpenBtn"); page.wait_for_timeout(1200)
            page.locator("#sideAdvSlot .chip[data-color=U]").click(); page.wait_for_timeout(2500)
            page.screenshot(path=f"{OUT}9-filters-drawer-{tag}.png")
            page.click("#filterClose") if page.locator("#filterClose").is_visible() else page.keyboard.press("Escape"); page.wait_for_timeout(1500)
            page.screenshot(path=f"{OUT}10-filtered-search-{tag}.png")
            print(tag, "FILTERED:", page.inner_text("#impQNote")[:200].replace("\n", " | "), file=log, flush=True)
            if page.locator("[data-imp-unfilter]").count(): page.click("[data-imp-unfilter]"); page.wait_for_timeout(500)
        step("filters", filt)
        def ub():
            page.goto(SITE + "?q=" + urllib.parse.quote("Battle at the Big Bridge")); page.wait_for_selector(".card-tile", timeout=60000); page.wait_for_timeout(3000)
            page.screenshot(path=f"{OUT}11-search-ub-name-{tag}.png")
            print(tag, "UB SEARCH:", page.locator(".card-tile").first.inner_text()[:120].replace("\n", " | "), file=log, flush=True)
            page.locator(".card-tile").first.click(); page.wait_for_selector("#cardViewCard .cp-name-sub", timeout=60000); page.wait_for_timeout(5000)
            page.screenshot(path=f"{OUT}12-card-page-other-name-{tag}.png")
            print(tag, "CARD:", page.inner_text("#cardViewCard")[:300].replace("\n", " | "), file=log, flush=True)
            sw = page.locator("#offerFoil")
            if sw.count():
                if sw.get_attribute("aria-checked") != "true": sw.click()
                page.wait_for_timeout(1500); page.evaluate("window.scrollTo(0, 0)"); page.wait_for_timeout(500)
                page.screenshot(path=f"{OUT}13-card-page-foil-{tag}.png")
            else: print(tag, "no foil switch", file=log, flush=True)
        step("ub", ub)
        print(tag, "errors:", errs, file=log, flush=True)
        ctx.close()
    b.close()


if __name__ == "__main__":
    wait_for_build()
    with sync_playwright() as p:
        run(p)
    log.close()
