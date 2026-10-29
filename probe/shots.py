# Screenshots of the one want list (the ☆ tray with deck buttons over the builder) on the staging test site (a throwaway probe)
import json, os, time, urllib.parse, urllib.request
from playwright.sync_api import sync_playwright
SITE = os.environ.get("SITE", "https://staging-warujie.warujie-mtg.workers.dev/")
OUT = os.environ.get("OUT", "probe_out/")
DECK = ("About\nName ボロス・バーン\n\nDeck\n4 稲妻\n4 Ragavan, Nimble Pilferer\n4 Monastery Swiftspear\n4 ボロスの魔除け\n4 Lightning Helix\n"
        "4 Skewer the Critics\n4 Lava Spike\n4 Rift Bolt\n4 Goblin Guide *F*\n4 Sacred Foundry\n4 Inspiring Vantage\n4 Arid Mesa\n12 Mountain\n\nSideboard\n2 Blood Moon\n3 Path to Exile\n\nMaybeboard\n2 Eidolon of the Great Revel\n2 Fireblast\n")
DECK2 = "About\nName エルフ\n\nDeck\n4 Llanowar Elves\n4 Elvish Mystic\n4 Heritage Druid\n4 Nettle Sentinel\n4 Elvish Archdruid\n20 Forest\n"
DECK3 = ("About\nName アトラクサ\n\nCommander\n1 Atraxa, Praetors' Voice\n\nDeck\n1 Sol Ring *F*\n1 Arcane Signet\n1 Swords to Plowshares\n1 Cultivate\n"
         "1 Doubling Season *F*\n1 Deepglow Skate\n1 Evolution Sage\n1 Command Tower\n1 Jace, Multiverse Architect *F*\n1 The Necrobloom (PMH3) 194s *F*\n1 Rhystic Study\n1 Smothering Tithe\n1 Avenger of Zendikar\n1 Parallel Lives\n"
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
    for i in range(40):
        try:
            req = urllib.request.Request(SITE + "?probe=" + str(time.time()), headers={"User-Agent": "warujie.jp probe"})
            if b"minmax(0, 1fr); gap: 6px; }" in urllib.request.urlopen(req, timeout=30).read(): print("build there after", i, file=log, flush=True); return
        except Exception as e: print("wait", repr(e)[:120], file=log, flush=True)
        time.sleep(30)
    print("build NOT seen", file=log, flush=True)


def builder_ready(page):
    page.wait_for_selector("#importBody .deck-section", timeout=90000)
    page.wait_for_timeout(4000)


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
        def go():
            page.goto(SITE + "?view=import&d=burn1"); builder_ready(page)
            page.screenshot(path=f"{OUT}1-builder-{tag}.png")
            if tag == "phone": page.click("#impPbarWant")
            else: page.click("#wantBtn")
            page.wait_for_selector("#wantTray .wt-deck", timeout=60000); page.wait_for_timeout(4000)
            page.screenshot(path=f"{OUT}2-tray-over-deck-{tag}.png")
            page.locator("#wantTray .wt-row", has_text="The One Ring").locator("[data-tadd=main]").click(); page.wait_for_timeout(1200)
            page.screenshot(path=f"{OUT}3-after-plus-one-ring-{tag}.png")
            print(tag, "row:", page.inner_text("#wantTray .wt-row:has-text('The One Ring') .wt-deck"), file=log, flush=True)
            page.click("#wantTray [data-tview=image]"); page.wait_for_timeout(2500)
            page.screenshot(path=f"{OUT}4-tray-pictures-{tag}.png")
            page.click("#wantTray [data-tview=list]"); page.wait_for_timeout(500)
            page.keyboard.press("Escape"); page.wait_for_timeout(500)
            page.goto(SITE + "?view=decks"); page.wait_for_selector("#dkGrid .dk-want", timeout=90000); page.wait_for_timeout(2000)
            page.click("#dkGrid .dk-want"); page.wait_for_selector("#wantTray .wt-row", timeout=60000); page.wait_for_timeout(2500)
            print(tag, "deck buttons on my decks:", page.locator("#wantTray [data-tadd]").count(), file=log, flush=True)
            page.screenshot(path=f"{OUT}5-tray-on-my-decks-{tag}.png")
        step("go", go)
        print(tag, "errors:", errs, file=log, flush=True)
        ctx.close()
    b.close()


if __name__ == "__main__":
    wait_for_build()
    with sync_playwright() as p:
        run(p)
