# Screenshots of the deck page's matchups, rising cards and 比べる box on the staging test site (a throwaway probe for the site thread "Improve deck browsing in metagame tab"; never merge)
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
            if b"deck-cmp-btn" in urllib.request.urlopen(req, timeout=30).read(): say("build there after", i); return
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
        def deck():
            page.goto(SITE + "?view=deck&format=modern&days=30&deck=Boros%20Energy")
            page.wait_for_selector("#deckBody .dlp-tile", timeout=90000); page.wait_for_timeout(7000)
        def to(sel, gap):
            page.evaluate("(s => { const e = document.querySelector(s); window.scrollTo(0, e.getBoundingClientRect().top + scrollY - %d); })('%s')" % (gap, sel))
            page.wait_for_timeout(1500)
        def mu():
            deck(); to("#deckBody .deck-mu", 140 if phone else 150); shot("5-deck-matchups")
        step("matchups", mu)
        def mv():
            to("#deckBody .deck-mv", 140 if phone else 150); shot("6-deck-rising-cards")
        step("moves", mv)
        def cmp_lists():
            deck(); page.click("#deckCmpBtn"); page.wait_for_selector("#deckBody .deck-cmp .cmp-t", timeout=30000); page.wait_for_timeout(1500)
            to("#deckBody .deck-cmp", 140 if phone else 150); shot("7-compare-lists")
        step("compare lists", cmp_lists)
        def cmp_mine():
            page.evaluate("""() => { const c = deckState.current; const l = c.choices.find(x => x.id === 'avg');
              const keep = l.main.filter((x, i) => i % 3 !== 0);
              deckNew('About\\nName 自分のボロス\\n\\n' + keep.map(x => x[0] + ' ' + x[1]).join('\\n'), 'modern'); drawDeck(); }""")
            page.select_option("#deckCmpSel", "d:" + page.evaluate("decks.decks[0].id")); page.wait_for_timeout(2000)
            to("#deckBody .deck-cmp", 140 if phone else 150); shot("8-compare-my-deck")
        step("compare my deck", cmp_mine)
        say(tag, "errors:", errs)
        ctx.close()
    b.close()

if __name__ == "__main__":
    wait_for_build()
    with sync_playwright() as p: run(p)
