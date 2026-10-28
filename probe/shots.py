# Screenshots of the deck builder's tools (layout B) on the staging test site (a throwaway probe)
import json, os, time, urllib.request
from playwright.sync_api import sync_playwright
SITE = os.environ.get("SITE", "https://staging-warujie.warujie-mtg.workers.dev/")
OUT = os.environ.get("OUT", "probe_out/")
DECK = ("About\nName ボロス・バーン\n\nDeck\n4 稲妻\n4 Ragavan, Nimble Pilferer\n4 Monastery Swiftspear\n4 ボロスの魔除け\n4 Lightning Helix\n"
        "4 Skewer the Critics\n4 Lava Spike\n4 Rift Bolt\n4 Goblin Guide\n4 Sacred Foundry\n4 Inspiring Vantage\n4 Arid Mesa\n12 Mountain\n\nSideboard\n2 Blood Moon\n3 Path to Exile\n\nMaybeboard\n2 Eidolon of the Great Revel\n2 Fireblast\n")
DECK2 = "About\nName エルフ\n\nDeck\n4 Llanowar Elves\n4 Elvish Mystic\n4 Heritage Druid\n4 Nettle Sentinel\n4 Elvish Archdruid\n20 Forest\n"
DECK3 = ("About\nName アトラクサ\n\nCommander\n1 Atraxa, Praetors' Voice\n\nDeck\n1 Sol Ring\n1 Arcane Signet\n1 Swords to Plowshares\n1 Cultivate\n"
         "1 Doubling Season\n1 Deepglow Skate\n1 Evolution Sage\n1 Command Tower\n1 Rhystic Study\n1 Smothering Tithe\n1 Avenger of Zendikar\n1 Parallel Lives\n"
         "1 Hallowed Fountain\n1 Breeding Pool\n1 Kodama's Reach\n1 Beast Within\n10 Forest\n10 Plains\n10 Island\n10 Swamp\n\nMaybeboard\n1 Cyclonic Rift\n")
now = int(time.time() * 1000)
STORE = {"v": 1, "cur": "burn1", "folders": ["大会用", "統率者"], "decks": [
    {"id": "burn1", "fmt": "modern", "text": DECK, "made": now, "edited": now, "folder": "大会用"},
    {"id": "atx1", "fmt": "commander", "text": DECK3, "made": now - 86400000, "edited": now - 86400000, "folder": "統率者"},
    {"id": "elf1", "fmt": "pauper", "text": DECK2, "made": now - 86400000 * 3, "edited": now - 86400000 * 3}]}
WANT = "2 Blood Moon\n1 Sacred Foundry\n1 The One Ring\n1 Rhystic Study\n"
INIT = "try { if (!localStorage.getItem('probe-seeded')) { localStorage.setItem('warujie-decks', %s); localStorage.setItem('warujie-want-list', %s); localStorage.setItem('akuchie-theme', 'light'); localStorage.setItem('probe-seeded', '1'); } } catch (e) {}" % (
    json.dumps(json.dumps(STORE, ensure_ascii=False)), json.dumps(WANT))
os.makedirs(OUT, exist_ok=True)
log = open(OUT + "log.txt", "w")


def wait_for_build():
    # the test site has the new build once its page has the 統計 pane
    for i in range(40):
        try:
            req = urllib.request.Request(SITE + "?probe=" + str(time.time()), headers={"User-Agent": "warujie.jp probe"})
            if b"impPaneStats" in urllib.request.urlopen(req, timeout=30).read(): print("build there after", i, file=log, flush=True); return
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
        def decks():
            page.goto(SITE + "?view=decks"); page.wait_for_selector("#dkGrid .dk-card", timeout=60000); page.wait_for_timeout(4000)
            page.screenshot(path=f"{OUT}1-mydecks-{tag}.png")
        step("decks", decks)
        def cmd():
            page.goto(SITE + "?view=import&d=atx1"); builder_ready(page)
            page.screenshot(path=f"{OUT}2-commander-{tag}.png")
            if tag == "desktop":
                page.click("#impTabs [data-pane=stats]")
            else:
                page.click("#impPbarStats")
            page.wait_for_timeout(6000)
            page.screenshot(path=f"{OUT}3-stats-{tag}.png")
            print(tag, "STATS:", page.inner_text("#impPaneStats")[-900:].replace("\n", " | "), file=log, flush=True)
            page.evaluate("(() => { const t = [...document.querySelectorAll('#impPaneStats .st-tile')]; t[t.length - 2].scrollIntoView({ block: 'start' }); })()"); page.wait_for_timeout(600)
            page.screenshot(path=f"{OUT}3b-stats-lower-{tag}.png")
            if tag == "phone": page.evaluate("setImpSheet(false)"); page.wait_for_timeout(600)
            page.screenshot(path=f"{OUT}4-commander-full-{tag}.png", full_page=True)
            if page.locator(".imp-cheap").count():
                page.locator(".imp-cheap").first.click(); page.wait_for_timeout(8000)
                page.screenshot(path=f"{OUT}5-cheaper-{tag}.png"); page.keyboard.press("Escape"); page.wait_for_timeout(400)
            else: print(tag, "no 安く chips", file=log, flush=True)
        step("commander", cmd)
        def burn():
            page.goto(SITE + "?view=import&d=burn1"); builder_ready(page)
            page.select_option("#impOrder", "mv"); page.wait_for_timeout(800)
            page.screenshot(path=f"{OUT}6-burn-by-mv-full-{tag}.png", full_page=True)
            page.select_option("#impOrder", "type")
            page.click("#impHandBtn"); page.wait_for_timeout(3000)
            page.screenshot(path=f"{OUT}7-hand-{tag}.png"); page.keyboard.press("Escape")
        step("burn", burn)
        def tray():
            page.goto(SITE); page.wait_for_timeout(2000)
            page.evaluate("searchInput.value = '稲妻'; searchInput.form.requestSubmit()"); page.wait_for_timeout(4000)
            page.click("#wantBtn"); page.wait_for_timeout(2500)
            page.screenshot(path=f"{OUT}8-tray-{tag}.png")
        step("tray", tray)
        print(tag, "errors:", errs, file=log, flush=True)
        ctx.close()
    b.close()


if __name__ == "__main__":
    wait_for_build()
    with sync_playwright() as p:
        run(p)
    log.close()
