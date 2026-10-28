# Screenshots of the deck builder on the staging test site (a throwaway probe; nothing is kept but the pictures)
import json, time
from playwright.sync_api import sync_playwright
SITE = "https://staging-warujie.warujie-mtg.workers.dev/"
OUT = "probe_out/"
DECK = ("About\nName ボロス・バーン\n\nDeck\n4 稲妻\n4 Ragavan, Nimble Pilferer\n4 Monastery Swiftspear\n4 ボロスの魔除け\n4 Lightning Helix\n"
        "4 Skewer the Critics\n4 Lava Spike\n4 Rift Bolt\n4 Goblin Guide\n4 Sacred Foundry\n4 Inspiring Vantage\n4 Arid Mesa\n12 Mountain\n\nSideboard\n2 Blood Moon\n3 Path to Exile\n")
DECK2 = "About\nName エルフ\n\nDeck\n4 Llanowar Elves\n4 Elvish Mystic\n4 Heritage Druid\n4 Nettle Sentinel\n4 Elvish Archdruid\n20 Forest\n"
now = int(time.time() * 1000)
STORE = {"v": 1, "cur": "burn1", "decks": [
    {"id": "burn1", "fmt": "modern", "text": DECK, "made": now, "edited": now},
    {"id": "elf1", "fmt": "pauper", "text": DECK2, "made": now - 86400000 * 3, "edited": now - 86400000 * 3}]}
WANT = "2 Blood Moon\n1 Sacred Foundry\n1 The One Ring\n"
INIT = "try { if (!localStorage.getItem('probe-seeded')) { localStorage.setItem('warujie-decks', %s); localStorage.setItem('warujie-want-list', %s); localStorage.setItem('probe-seeded', '1'); } } catch (e) {}" % (
    json.dumps(json.dumps(STORE, ensure_ascii=False)), json.dumps(WANT))
log = open(OUT + "log.txt", "w")
with sync_playwright() as p:
    b = p.chromium.launch()
    for w, h, tag in ((1280, 900, "desktop"), (390, 844, "phone")):
        ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if tag == "phone" else 1, is_mobile=tag == "phone", has_touch=tag == "phone", locale="ja-JP")
        ctx.add_init_script(INIT)
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        for attempt in range(20):   # until the test site has the new build
            page.goto(SITE + "?view=decks")
            try:
                page.wait_for_selector("#dkGrid a.dk-card", timeout=20000); break
            except Exception:
                print(tag, "not yet", attempt, file=log, flush=True); page.wait_for_timeout(30000)
        page.wait_for_function("[...document.querySelectorAll('#dkGrid .dk-yen')].some(e => e.textContent.startsWith('約'))", timeout=60000)
        page.wait_for_timeout(2500)
        page.screenshot(path=f"{OUT}decks-{tag}.png", full_page=tag == "phone")
        page.goto(SITE + "?view=import&d=burn1"); page.wait_for_selector("#importBody .deck-section", timeout=60000)
        page.wait_for_timeout(3000)
        if tag == "desktop":
            page.fill("#impQ", "除去"); page.wait_for_selector("#impQList .imp-pick"); page.wait_for_timeout(2500)
            page.screenshot(path=f"{OUT}build-search-{tag}.png")
            page.click("#impTabs [data-pane=want]"); page.wait_for_timeout(2000)
            page.screenshot(path=f"{OUT}build-want-{tag}.png")
            page.click("[data-iview=image]"); page.wait_for_timeout(3000)
            page.screenshot(path=f"{OUT}build-pictures-{tag}.png")
        else:
            page.screenshot(path=f"{OUT}build-{tag}.png")
            page.click("#impPbar .imp-pbar-add"); page.fill("#impQ", "青 カウンター"); page.wait_for_selector("#impQList .imp-pick"); page.wait_for_timeout(2500)
            page.screenshot(path=f"{OUT}build-sheet-{tag}.png")
            page.keyboard.press("Escape")
        print(tag, "errors:", errs, file=log)
        ctx.close()
    b.close()
log.close()
