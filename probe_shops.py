"""One-off check for warujie.jp's Japanese shop links (thread "Clean up and complete Japanese shop
list", 2026-11-09). For each shop: robots.txt, then its own product search for two well-known cards,
opened in a headless browser (some shops build results in JavaScript). Records whether the search
page loads and how often the card's names appear on it. Shops with no known search URL get their
home page's search form found and used. Nothing is kept but counts and a few product titles.
Pages are opened one at a time, 4 s apart; robots.txt is respected. Remove after the check."""
import json, re, sys, time, urllib.parse, urllib.robotparser, urllib.request
from playwright.sync_api import sync_playwright

UA = "Mozilla/5.0 (compatible; warujie.jp link check; +https://warujie.jp/)"
GAP = 4
CARDS = [("稲妻", "Lightning Bolt"), ("太陽の指輪", "Sol Ring")]

# (key, name, home, search url with {q} or None, 'ja'/'en' = which name the site's link searches by)
SHOPS = [
    ("hareruya", "晴れる屋", "https://www.hareruyamtg.com/ja/", "https://www.hareruyamtg.com/ja/products/search?product={q}", "ja"),
    ("bigmagic", "BIG MAGIC", "https://www.bigweb.co.jp/", "https://www.bigweb.co.jp/ja/products/mtg/list?name={q}", "en"),
    ("cardrush", "カードラッシュ", "https://www.cardrush-mtg.jp/", "https://www.cardrush-mtg.jp/product-list?keyword={q}", "ja"),
    ("tokyomtg", "Tokyo MTG", "https://tokyomtg.com/", "https://tokyomtg.com/cardpage.html?p=q&query={q}", "en"),
    ("singlestar", "シングルスター", "https://www.singlestar.jp/", "https://www.singlestar.jp/product-list?keyword={q}", "ja"),
    ("serra", "セラ", "https://cardshop-serra.com/", "https://cardshop-serra.com/search?q={q}", "ja"),
    ("enndal", "ENNDAL", "https://www.enndalgames.com/", "https://www.enndalgames.com/products/list.php?mode=search&name={q}", "ja"),
    ("amenity", "アメニティードリーム", "https://www.amenitydream.com/", "https://www.amenitydream.com/product-list?keyword={q}", "ja"),
    ("eternalblue", "エターナルブルー", "https://www.eternal-blue.jp/", "https://www.eternal-blue.jp/product-list?keyword={q}", "ja"),
    ("bigred", "BIGRED", "https://www.bigredmtg.com/", "https://www.bigredmtg.com/product-list?keyword={q}", "ja"),
    ("hamaya", "はま屋", "https://www.cardshophamaya.com/", "https://www.cardshophamaya.com/product-list?keyword={q}", "ja"),
    ("cantrip", "CANTRIP", "https://cantripmtg.com/", "https://cantripmtg.com/search?q={q}", "ja"),
    ("masters", "マスターズスクウェア", "https://www.square-3rd.jp/", "https://www.square-3rd.jp/product-list?keyword={q}", "ja"),
    ("guild", "MTG Guild", "https://mtg-guild.com/", "https://mtg-guild.com/?mode=srh&keyword={q}", "en"),
    ("guild_ja", "MTG Guild (ja)", "https://mtg-guild.com/", "https://mtg-guild.com/?mode=srh&keyword={q}", "ja"),
    ("hasuya", "蓮屋", "https://www.hasuya.jp/", "https://www.hasuya.jp/products/list?name={q}", "ja"),
    ("azumaya", "あずまや", "https://azumayamtg.com/", "https://azumayamtg.com/products/list?name={q}", "ja"),
    ("advantage", "アドバンテージ", "https://www.advantagemtg.jp/", "https://www.advantagemtg.jp/product-list?keyword={q}", "ja"),
    ("satopin", "サトPin", "https://www.cardshopsatopin.net/", "https://www.cardshopsatopin.net/product-list?keyword={q}", "ja"),
    ("blackfrog", "BLACK FROG", "https://blackfrog.jp/", "https://blackfrog.jp/shop/shopbrand.html?search={q}", "ja"),
    ("clabo", "カードラボ", "https://www.c-labo-online.jp/", "https://www.c-labo-online.jp/product-list?keyword={q}", "ja"),
    ("surugaya", "駿河屋", "https://www.suruga-ya.jp/", "https://www.suruga-ya.jp/search?search_word={q}", "ja"),
    # candidates
    ("nukenin", "抜忍", "https://nukeninmtg.com/", "https://nukeninmtg.com/products/list?name={q}", "ja"),
    ("todo", "ゲームショップとど", "https://todo.ocnk.net/", "https://todo.ocnk.net/product-list?keyword={q}", "ja"),
    ("mint", "MINT", "https://mint-web.jp/", "https://mint-web.jp/?mode=srh&keyword={q}", "ja"),
    ("dorasuta", "ドラゴンスター", "https://dorasuta.jp/", None, "ja"),
    ("johnny", "ジョニーのお店", "https://www.johnnymagic.jp/", None, "ja"),
    ("arcana", "アルカナ", "https://mtg.arcana-tcg.com/", None, "ja"),
    ("salon", "MTG SALON TOKYO", "https://mtgsalon.com/", "https://mtgsalon.com/search?q={q}", "ja"),
    ("azkimi", "あずきみ", "https://azkimi.com/", None, "ja"),
    ("fconclave", "Fの集会場", "https://www.f-conclave.net/", None, "ja"),
    ("pinocchio", "PINOCCHIO", "https://www.pinocchio-mtg.jp/", None, "ja"),
    ("shikanotsuno", "しかのつの", "https://www.shikanotsunomtg.com/", None, "ja"),
    ("nageya", "Nageya", "https://www.mtgnage.jp/", None, "ja"),
    ("playfirst", "Play First Games", "https://www.playfirstgames.jp/", None, "ja"),
    ("manawave", "MANAWAVE", "https://shopping.manawave.jp/", None, "ja"),
    ("hbst", "ホビーステーション", "https://www.hbst.net/", None, "ja"),
    ("pricebase", "PRICE BASE", "https://shop.price-base.com/", None, "ja"),
    ("fullahead", "フルアヘッド", "https://fullahead-tcg.com/", None, "ja"),
    ("cardwings", "CARDWINGS", "https://card-wings.com/", None, "ja"),
    ("yellowsub", "イエローサブマリン", "https://yellowsubmarine.co.jp/", None, "ja"),
    ("toyaju", "toyaju", "https://shop.toyaju.net/shop3/", None, "ja"),
    ("manzokuya", "まんぞく屋", "https://shopmanzokuya.com/", None, "ja"),
    ("ouchi", "カードショップおうち", "https://www.cardshop-ouchi.com/", None, "ja"),
    ("batoloco", "バトロコ", "https://batoloco.com/", None, "ja"),
]
if len(sys.argv) > 1:
    SHOPS = [s for s in SHOPS if s[0] in sys.argv[1:]]

robots = {}


def allowed(url):
    p = urllib.parse.urlsplit(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            req = urllib.request.Request(base + "/robots.txt", headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                rp.parse(r.read().decode("utf-8", "replace").splitlines())
        except Exception as e:
            rp.parse([])   # no robots.txt: allowed
        robots[base] = rp
        time.sleep(1)
    return robots[base].can_fetch(UA, url)


def count_hits(text, ja, en):
    t = text.replace("　", " ")
    return {"ja": t.count(ja), "en": len(re.findall(re.escape(en), t, re.I))}


def titles(page, ja, en):
    """A few short lines of the result that name the card (product titles), to see what matched."""
    try:
        body = page.inner_text("body")
    except Exception:
        return []
    out = []
    for line in body.splitlines():
        line = line.strip()
        if 4 < len(line) < 90 and (ja in line or en.lower() in line.lower()):
            if line not in out:
                out.append(line)
        if len(out) >= 4:
            break
    return out


def find_form(page):
    """The home page's product search: (action url, field name, extra fields), or None."""
    return page.evaluate("""() => {
      const inputs = [...document.querySelectorAll('form input')].filter(i =>
        /^(search|text|)$/.test(i.type) && /key|word|search|^q$|query|name|kw|srh/i.test(i.name || ''));
      for (const i of inputs) {
        const f = i.form; if (!f) continue;
        const extra = {};
        [...f.querySelectorAll('input[type=hidden]')].forEach(h => { if (h.name) extra[h.name] = h.value; });
        return { action: new URL(f.getAttribute('action') || location.href, location.href).href,
                 method: (f.method || 'get').toLowerCase(), name: i.name, extra };
      }
      return null;
    }""")


def main():
    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(user_agent=UA, locale="ja-JP")
        page = ctx.new_page()
        for key, name, home, search, by in SHOPS:
            r = {"key": key, "name": name, "home": home, "search": search, "tests": []}
            print("==", key, flush=True)
            try:
                if not search:
                    if not allowed(home):
                        r["note"] = "robots.txt forbids the home page"
                        results.append(r); continue
                    resp = page.goto(home, timeout=45000, wait_until="domcontentloaded")
                    page.wait_for_timeout(2500)
                    r["home_status"] = resp.status if resp else None
                    r["home_title"] = page.title()[:120]
                    body = page.inner_text("body")
                    r["home_mtg_words"] = len(re.findall(r"MTG|マジック[：:・]?ザ[・ ]?ギャザリング|Magic: The Gathering", body))
                    form = find_form(page)
                    r["form"] = form
                    time.sleep(GAP)
                    if form and form["method"] == "get":
                        qs = dict(form["extra"]); qs[form["name"]] = "{q}"
                        search = form["action"].split("?")[0] + "?" + urllib.parse.urlencode(qs).replace("%7Bq%7D", "{q}")
                        r["search"] = search
                    else:
                        results.append(r); continue
                for ja, en in CARDS:
                    q = ja if by == "ja" else en
                    url = search.replace("{q}", urllib.parse.quote(q))
                    t = {"q": q, "url": url}
                    if not allowed(url):
                        t["note"] = "robots.txt forbids this search page"
                        r["tests"].append(t); continue
                    resp = page.goto(url, timeout=45000, wait_until="domcontentloaded")
                    page.wait_for_timeout(3500)
                    t["status"] = resp.status if resp else None
                    t["final"] = page.url
                    t["hits"] = count_hits(page.inner_text("body"), ja, en)
                    m = re.search(r"(?:全\s*)?([\d,]+)\s*(?:件|items?|results?)", page.inner_text("body"))
                    t["count_text"] = m.group(0) if m else ""
                    t["titles"] = titles(page, ja, en)
                    r["tests"].append(t)
                    time.sleep(GAP)
            except Exception as e:
                r["error"] = repr(e)[:300]
                time.sleep(GAP)
            results.append(r)
            print(json.dumps(r, ensure_ascii=False), flush=True)
        browser.close()
    json.dump(results, open("probe_out/shops.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
