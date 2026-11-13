"""ENNDAL GAMES (enndalgames.com): yen prices and stock for warujie.jp's JP tab.

ENNDAL GAMES agreed on 2026-10-15 to low-frequency automated access, and we told
them how we read their shop: once a night (2-6am Japan time), one page at a
time, PAGE_GAP seconds apart, with a User-Agent naming warujie.jp and our
contact address. Keep it that way: never read pages in parallel, and stop at
once if they ask.

Their shop is EC-CUBE 2. Every set is a category; its list pages show 100
products each, and every product carries a code in its URL,
    <SET>-<rarity><colour>-<number>-<lang>-<condition>-<finish>
(e.g. BLB-MW-0002-JP-NM-normal), its name "(BLB-MW)English/日本語", and a
table with one row per language and condition: price in yen and copies left.

    parse_categories(html) -> [(category_id, name, items)]
    parse_list(html)       -> [{"set", "number", "finish", "name_en", "name_ja",
                                "url", "offers": [(lang, cond, yen, copies)]}]
    read_shop(...)         -> the in-stock offers of the categories asked for
    nightly(...)           -> one night's reading, kept per category (enndal.json.gz)
    add_offers(...)        -> those offers as build_prices.py's offer rows

Run nightly by .github/workflows/enndal-nightly.yml:
    python3 shop_enndal.py --previous last/enndal.json.gz --out out/enndal.json.gz --until 20:45
"""
import argparse
import gzip
import html as htmllib
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://www.enndalgames.com"
CONTACT = "warujie.mtg" + "@" + "gmail.com"
USER_AGENT = f"WarujieShopPrices/1.0 (+https://warujie.jp; {CONTACT})"
PAGE_GAP = 4.0          # seconds between pages (we promised 3-5)
PER_PAGE = 100          # the largest page size the shop offers
LANGS = {"日本語": "JA", "英語": "EN"}
MENU_URL = BASE + "/products/list.php?mode=search&name=%E7%A8%B2%E5%A6%BB"   # any list page shows the set menu
# menu entries that are not single cards (or repeat other categories)
SKIP_WORDS = ("特集", "Flesh and Blood", "サプライ", "書籍", "大会受付", "Dummy", "未開封", "セール", "ギフト",
              "予約", "コンプリートセット", "スペシャルアイテム", "オリジナルトークン", "他言語", "Sealed")
NIGHT_MINUTES = 200     # the most one night may read (the workflow also stops it before 6am Japan time)
MENU_RETRY_MINUTES = 15  # the shop not answering at all (its server down a while): wait this long, then try the menu once more
KEEP_DAYS = 7           # a set not read again within this long is dropped from the data
FORMAT = 1
FINISHES = {"normal": 0, "foil": 1, "etched": 1}
# ENNDAL set codes that differ from Scryfall's (M2R = the MH2 timeshifts in MH3 boosters)
SET_ALIASES = {"m2r": "h2r"}

CATEGORY_RE = re.compile(
    r'category_id=(\d+)&(?:amp;)?disp_number=\d+"[^>]*>([^<]+)<span>\((\d+)\)</span>')
PRODUCT_RE = re.compile(r'<div class="list_area[^"]*">(.*?)<div class="listcomment">', re.S)
NAME_RE = re.compile(r'<a href="([^"]+/product/([^/"]+)/)"\s+class="product_name"[^>]*>([^<]+)</a>')
# some sets' codes end in "_" (MH3-MC-0006-JP-NM-normal_)
CODE_RE = re.compile(r'^([A-Z0-9]+)-([A-Z])([A-Z])-([0-9A-Za-z]+)-([A-Z]+)-([A-Z]+)-([a-z]+)_*$')
ROW_RE = re.compile(r'<tr><th>\s*(\S+)\s+(\S+)\s*</th><td><span class="price">([\d,]+)円</span>'
                    r'<span class="quantity">\s*残り\s*(\d+)</span>')
TOTAL_RE = re.compile(r'<span class="attention">(\d+)件</span>')


def parse_categories(page):
    """The set categories in the shop's menu, with their item counts
    (out-of-stock items included)."""
    seen, out = set(), []
    for cid, name, n in CATEGORY_RE.findall(page):
        if cid not in seen:
            seen.add(cid)
            out.append((int(cid), htmllib.unescape(name).strip(), int(n)))
    return out


def parse_total(page):
    m = TOTAL_RE.search(page)
    return int(m.group(1)) if m else 0


def split_name(title):
    """'【拡張アート】(LCI-RA)Threefold Thunderhulk/三重の稲妻巨人【No.0390】'
    -> ('Threefold Thunderhulk', '三重の稲妻巨人')."""
    t = re.sub(r"【[^】]*】", "", htmllib.unescape(title))
    t = re.sub(r"^\([^)]*\)", "", t).strip()
    en, _, ja = t.partition("/")
    return en.strip(), ja.strip()


def parse_list(page):
    """The products on one list page, with an offer per language and
    condition that has copies left."""
    out = []
    for block in PRODUCT_RE.findall(page):
        m = NAME_RE.search(block)
        if not m:
            continue
        url, code, title = m.groups()
        c = CODE_RE.match(urllib.parse.unquote(code))
        if not c:
            continue
        set_code, _rarity, _colour, number, _lang, _cond, finish = c.groups()
        offers = []
        for lang, cond, yen, copies in ROW_RE.findall(block):
            copies = int(copies)
            if copies <= 0 or lang not in LANGS:
                continue
            offers.append((LANGS[lang], cond, int(yen.replace(",", "")), copies))
        en, ja = split_name(title)
        out.append({"set": SET_ALIASES.get(set_code.lower(), set_code.lower()), "number": number.lstrip("0") or "0",
                    "finish": finish, "name_en": en, "name_ja": ja,
                    "url": htmllib.unescape(url), "offers": offers})
    return out


def fetch(url, tries=3):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "ja"})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as err:
            if err.code in (403, 429, 503):   # the shop is pushing back: stop for tonight
                raise
            if attempt == tries - 1:
                raise
        except OSError:
            if attempt == tries - 1:
                raise
        time.sleep(PAGE_GAP * 5)


def list_url(category_id, page_no):
    # oos=0 leaves out products with no copies left, so fewer pages are read
    return f"{BASE}/products/list.php?category_id={category_id}&disp_number={PER_PAGE}&pageno={page_no}&oos=0"


def read_shop(categories, minutes, get=fetch, sleep=time.sleep, log=print, into=None, done=None, first=True):
    """Read the given categories' in-stock products, one page at a time,
    PAGE_GAP seconds apart, for at most `minutes`. Returns (products,
    finished category ids). With `into`, each category's products also go
    into into[category id], and `done` fills as categories finish, so a
    caller still has them if a page fails."""
    deadline = time.monotonic() + minutes * 60
    products = []
    done = [] if done is None else done
    for cid in categories:
        page_no = 1
        mine = [] if into is None else into.setdefault(cid, [])
        while True:
            if time.monotonic() > deadline:
                log(f"  ENNDAL: time is up after {len(done)} categories")
                return products, done
            if not first:
                sleep(PAGE_GAP)
            first = False
            page = get(list_url(cid, page_no))
            got = parse_list(page)
            if not got and PRODUCT_RE.search(page):
                log(f"  ENNDAL: category {cid} page {page_no} has products we could not read")
            products.extend(got)
            mine.extend(got)
            total = parse_total(page)
            if not got or page_no * PER_PAGE >= total:
                break
            page_no += 1
        done.append(cid)
    return products, done


# ------------------------------------------------------------------ one night
def _iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def nightly(previous, minutes, get=fetch, sleep=time.sleep, log=print, now=None):
    """One night's reading. The sets come from the shop's menu (SKIP_WORDS
    left out), those read longest ago first, so a night that runs out of
    time carries on with the rest the next night; sets not read tonight keep
    their previous products for up to KEEP_DAYS. Returns the new data:
    {"version", "updated", "cats": {id: {"name", "read", "p": [[set, number,
    finish, path, [[lang, cond, yen, copies], ...]], ...]}}}."""
    now = now or datetime.now(timezone.utc)
    old = (previous or {}).get("cats") or {}
    try:
        menu = get(MENU_URL)
    except urllib.error.HTTPError:   # the shop answered and refused (403/429/503) or the page is gone: not tonight
        raise
    except OSError as err:   # no answer at all (timed out twice on 2026-10-27 and 11-01): one more try a little later
        log(f"  ENNDAL: no answer ({err}); trying again in {MENU_RETRY_MINUTES} minutes")
        sleep(MENU_RETRY_MINUTES * 60)
        minutes = max(0, minutes - MENU_RETRY_MINUTES)   # still done by the stop time we promised (5:45 in Japan)
        menu = get(MENU_URL)
    cats = [(cid, name) for cid, name, _n in parse_categories(menu) if not any(w in name for w in SKIP_WORDS)]
    if not cats:
        raise ValueError("no sets in ENNDAL's menu")
    names = dict(cats)
    order = sorted((cid for cid, _ in cats), key=lambda c: (old.get(str(c)) or {}).get("read", ""))
    into, done = {}, []
    try:
        sleep(PAGE_GAP)
        read_shop(order, minutes, get, sleep, log, into=into, done=done, first=False)
    except Exception as err:   # pushback (403/429/503) or a page that keeps failing: stop for tonight, keep what was read
        log(f"  ENNDAL: stopped for tonight ({err})")
    stamp = _iso(now)
    cutoff = _iso(now - timedelta(days=KEEP_DAYS))
    out = {}
    for cid, name in cats:
        if cid in done:
            out[str(cid)] = {"name": name, "read": stamp,
                             "p": [[p["set"], p["number"], p["finish"], p["url"][len(BASE) + 1:] if p["url"].startswith(BASE + "/") else "",
                                    [list(o) for o in p["offers"]]] for p in into.get(cid, []) if p["offers"]]}
        elif (old.get(str(cid)) or {}).get("read", "") >= cutoff:
            out[str(cid)] = dict(old[str(cid)], name=names[cid])
    n = sum(len(c["p"]) for c in out.values())
    log(f"  ENNDAL: read {len(done)} of {len(order)} sets tonight; {len(out)} sets and {n} products in stock in the data")
    return {"version": FORMAT, "updated": stamp, "read_tonight": len(done), "sets": len(order), "cats": out}


def load(path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        data = json.load(fh)
    if data.get("version") != FORMAT:
        raise ValueError(f"unknown ENNDAL data version {data.get('version')}")
    return data


def save(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as fh:
        with gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
            gz.write(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


# ------------------------------------------------------------------ matching (for build_prices.py)
def number_key(n):
    return str(n).lower().lstrip("0") or "0"


def add_offers(data, by_number, by_name, rows, links):
    """Each in-stock product as offer rows ["ed", foil, condition, yen,
    copies, language ("" = English)] of the Scryfall printing with the same
    set and collector number (or, failing that, the only printing of that
    name in the set). `by_number`: {(set, number_key): (id, English name)};
    `by_name`: {(set, English name lower): [ids]}. A number whose name
    disagrees is only trusted when the name finds nothing better. Links are
    the products' paths on the shop, [non-foil, foil]. Returns (offers,
    products matched, products not matched)."""
    n = matched = missed = 0
    for cat in (data.get("cats") or {}).values():
        for set_code, number, finish, path, offers in cat.get("p") or []:
            foil = FINISHES.get(finish)
            if foil is None or not offers:
                continue
            got = by_number.get((set_code, number_key(number)))
            names = None
            if got:
                sid, name = got
                if name.lower() != _name_of(path).lower():
                    names = by_name.get((set_code, _name_of(path).lower())) or []
                    sid = names[0] if len(names) == 1 else (sid if not names else None)
            else:
                names = by_name.get((set_code, _name_of(path).lower())) or []
                sid = names[0] if len(names) == 1 else None
            if not sid:
                missed += 1
                continue
            matched += 1
            for lang, cond, yen, copies in offers:
                rows.setdefault(sid, []).append(["ed", foil, cond, int(yen), int(copies), "" if lang == "EN" else lang])
                n += 1
            if path:
                pair = links.setdefault(sid, {}).setdefault("ed", ["", ""])
                if not pair[foil]:
                    pair[foil] = path
    return n, matched, missed


def _name_of(path):
    """The English name in a product path ('%28BLB-MW%29Name%2F日本語/product/...')."""
    return split_name(urllib.parse.unquote_plus(path.split("/product/")[0]))[0]


def main():
    ap = argparse.ArgumentParser(description="Read ENNDAL GAMES' in-stock singles for one night.")
    ap.add_argument("--previous", default="", help="last night's enndal.json.gz (missing is fine)")
    ap.add_argument("--out", required=True, help="where to write tonight's enndal.json.gz")
    ap.add_argument("--minutes", type=float, default=NIGHT_MINUTES, help="the most this night may read")
    ap.add_argument("--until", default="", help="UTC time (HH:MM) to stop by, e.g. 20:45 = 5:45 in Japan")
    args = ap.parse_args()
    minutes = args.minutes
    if args.until:
        now = datetime.now(timezone.utc)
        h, m = map(int, args.until.split(":"))
        end = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if end <= now:
            end += timedelta(days=1)
        minutes = min(minutes, (end - now).total_seconds() / 60)
        if minutes > 230:   # not between 2am and the stop time in Japan (a late or by-hand run): don't read in the daytime
            raise SystemExit(f"Not night in Japan: it is {_iso(now)} and the stop time is {args.until} UTC.")
    previous = None
    if args.previous and os.path.exists(args.previous):
        try:
            previous = load(args.previous)
        except Exception as err:
            print(f"  note: last night's ENNDAL data could not be read ({err}); starting afresh.")
    data = nightly(previous, minutes)
    if not data["cats"]:
        raise SystemExit("Nothing was read from ENNDAL GAMES tonight and nothing is kept: not saving.")
    save(args.out, data)
    n = sum(len(c["p"]) for c in data["cats"].values())
    print(f"::notice title=ENNDAL GAMES::read {data['read_tonight']} of {data['sets']} sets tonight; {n} products in stock in the data")


if __name__ == "__main__":
    main()
