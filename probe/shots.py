# Mock-ups (not built): two ways to make the builder's ☆ tab and the want tray one list, on the staging test site (a throwaway probe)
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



MOCK_CSS = """
.wt-row.mk { grid-template-rows: auto auto; }
.wt-row.mk .wt-pic { grid-row: span 2; align-self: start; }
.wt-deck { grid-column: 2 / -1; display: flex; align-items: center; justify-content: space-between; gap: 8px; font-size: 11.5px; color: var(--muted); }
.wt-deck b { color: var(--accent); font-weight: 700; }
.wt-deck-btns { display: flex; gap: 8px; flex: none; }
.wt-deckbar { margin: 0; padding: 8px 16px; border-bottom: 1px solid var(--line); background: var(--surface-2); font-size: 12.5px; color: var(--text-2); }
.wt-deckbar b { color: var(--text); }
#impPaneWant .want-step button { width: 30px; height: 30px; font-size: 16px; }
#impPaneWant .want-step .want-c { min-width: 34px; font-size: 13px; }
#impPaneWant .wt-sub { padding: 0 0 8px; }
#impPaneWant .wt-foot { margin-top: 10px; border: 1px solid var(--line); border-radius: 10px; }
.mk-tag { position: fixed; left: 8px; bottom: 8px; z-index: 999; padding: 4px 10px; border-radius: 6px; background: #c2185b; color: #fff; font: 700 12px system-ui; pointer-events: none; }
"""
MOCK_JS = r"""
(() => {
  const st = document.createElement('style'); st.textContent = %s; document.head.appendChild(st);
  const tag = document.createElement('div'); tag.className = 'mk-tag'; tag.textContent = %s; document.body.appendChild(tag);
  const btn = (part, n, text) => `<button type="button" class="imp-add${part === 'side' ? ' sb' : part === 'maybe' ? ' mb' : ''}${n ? ' on' : ''}">${text}${n ? `<span class="imp-add-n">${n}</span>` : ''}</button>`;
  // a row of the want list gets a second line: how many are in this deck, and ＋ / SB / 考慮 into it
  window.mkDeckLines = (root) => {
    const counts = impCounts(); if (!counts) return;
    const byKey = new Map(wantData().list.map(x => [x.k, x]));
    root.querySelectorAll('.wt-row').forEach(li => {
      const x = byKey.get(li.dataset.wantRow); if (!x || li.classList.contains('mk')) return;
      const nm = exportName(x.name), m = counts.main.get(nm) || 0, s = counts.side.get(nm) || 0, mb = counts.maybe.get(nm) || 0;
      li.classList.add('mk');
      li.insertAdjacentHTML('beforeend', `<span class="wt-deck"><span>${m + s ? `<b>${esc(t('imp.w.in', { n: m + s }))}</b>` : esc(t('imp.w.out'))}</span>`
        + `<span class="wt-deck-btns">${btn('main', m, '＋')}${deckFmt() === 'commander' ? '' : btn('side', s, 'SB')}${btn('maybe', mb, esc(t('imp.q.maybe.short')))}</span></span>`);
    });
  };
  const deckTitle = () => (document.getElementById('impName') || {}).value || '';
  if (%s === 'B') {
    // B: one tray everywhere; on a deck page its rows also put cards into the deck; the panel loses its ☆ tab
    document.querySelectorAll('#impTabs [data-pane=want]').forEach(b => b.remove());
    const orig = drawTray;
    window.drawTray = function () {
      orig();
      const tray = document.getElementById('wantTray');
      if (!impCounts()) return;
      mkDeckLines(tray);
      const sub = tray.querySelector('.wt-sub');
      if (sub && !tray.querySelector('.wt-deckbar')) sub.insertAdjacentHTML('afterend', `<p class="wt-deckbar">＋ SB 考慮 で <b>${esc(deckTitle())}</b> に入れる（ウォントからは消えません）</p>`);
    };
  } else {
    // A: the panel's ☆ tab becomes the whole want list (the tray's − n ＋, trash, total, export, 晴れる屋)
    window.drawImpWant = function () {
      const el = document.getElementById('impPaneWant');
      if (el.hidden) return;
      const d = wantData(), items = trayItems(d);
      el.innerHTML = `<div class="wt-sub"><span class="wt-count"><b>${esc(tn('want.f.cards', d.total))}</b> <span class="sep">·</span> ${esc(t('want.f.kinds', { n: fmtNum(d.list.length) }))}</span></div>`
        + `<p class="imp-q-note">${esc(t('imp.w.lead'))}</p><ul class="wt-list">${items.map(trayRowHtml).join('')}</ul>`
        + `<div class="wt-foot">${trayTotalHtml(items)}<div class="wt-foot-btns">${trayExportHtml()}<a class="adv-btn wt-buy" href="#">${t('imp.hareruya')} ↗</a></div></div>`;
      mkDeckLines(el);
    };
  }
})();
"""


def mock(page, which):
    label = {"A": "案A（イメージ）: ☆タブが全部入り", "B": "案B（イメージ）: 右のトレイ1つ"}[which]
    page.evaluate(MOCK_JS % (json.dumps(MOCK_CSS), json.dumps(label), json.dumps(which)))


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
        def a():
            page.goto(SITE + "?view=import&d=burn1"); builder_ready(page); mock(page, "A")
            if tag == "phone": page.click("#impPbarWant")
            else: page.click("#impTabs [data-pane=want]")
            page.wait_for_selector("#impPaneWant .wt-deck", timeout=60000); page.wait_for_timeout(3500)
            page.evaluate("drawImpWant()"); page.wait_for_timeout(800)
            page.screenshot(path=f"{OUT}A1-tab-is-the-want-list-{tag}.png")
            page.evaluate("document.querySelector('#impPaneWant .wt-foot') && document.querySelector('#impPaneWant .wt-foot').scrollIntoView({block:'end'})"); page.wait_for_timeout(600)
            page.screenshot(path=f"{OUT}A2-tab-bottom-total-export-{tag}.png")
        step("A", a)
        def bb():
            page.goto(SITE + "?view=import&d=burn1"); builder_ready(page); mock(page, "B")
            page.screenshot(path=f"{OUT}B1-builder-without-want-tab-{tag}.png")
            page.evaluate("openTray()")
            page.wait_for_selector("#wantTray .wt-deck", timeout=60000); page.wait_for_timeout(3500)
            page.evaluate("drawTray()"); page.wait_for_timeout(800)
            page.screenshot(path=f"{OUT}B2-tray-adds-to-deck-{tag}.png")
        step("B", bb)
        print(tag, "errors:", errs, file=log, flush=True)
        ctx.close()
    b.close()


if __name__ == "__main__":
    with sync_playwright() as p:
        run(p)
