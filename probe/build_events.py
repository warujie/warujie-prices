"""Local Magic tournaments in Japan for warujie.jp's 大会 calendar (events.json).

The owner's decision (2026-10-24): the calendar shows the shops' own event lists,
read once a night, with every event linking back to the shop's page. We read only
pages the shops' robots.txt allows, one page at a time, PAGE_GAP seconds apart,
with a User-Agent naming warujie.jp and our contact address, and stop at once if a
shop asks. Wizards' Store & Event Locator (robots.txt disallows its /api/) and
Facebook (no automated collection without written permission) are never read.

Sources:
  Hareruya       each store's month calendar, /ja/events/?shop=<n>&date=<YYYYMM>, this
                 month and next; every event has its own page and format icons
  Amenity Dream  every store's MTG list, /matches/?type=2, then one page per day it offers
                 (about a month; its server sends an out-of-date certificate chain, so the
                 missing intermediate is fetched from the certificate's own AIA link)
  Yellow Submarine  each store's schedule, /tmt_list/<store>/ (Shift_JIS), only the
                 rows whose game is マジック; the format is in the notes column
  Tonamel        the MTG events in Japan that stores and players list on tonamel.com
                 (KAYAC's tournament site; the owner's request of 2026-10-25): its event-search
                 page opened in a headless browser (Playwright), keeping the lists the page
                 itself loads; offline events only
  Pictures       shops' event calendars posted as pictures, read by hand (the owner's choice,
                 2026-10-25: by hand first, automatic later) and kept in manual_events.json:
                 shops' posts on X, from a picture the owner hands over (x.com itself is never
                 read: its robots.txt forbids it), and MINT's monthly schedule pages
                 (mint-web.jp, the owner's request); each event links to its post or page

    python3 build_events.py --out site/events.json [--days 35]
    python3 build_events.py --out site/events.json --manual-only published.json

Writes { "updated", "sources": {shop: events}, "events": [{ "d", "t", "p", "c",
"shop", "store", "name", "url", "f" }] } (docs/README.md), or exits non-zero
without writing if every shop's source failed, so yesterday's file stays published.
--manual-only puts manual_events.json's events into an already published file without
reading any shop (a change to manual_events.json goes out without a second crawl).
"""
import argparse
import html as htmllib
import json
import os
import re
import ssl
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

CONTACT = "warujie.mtg" + "@" + "gmail.com"
USER_AGENT = f"WarujieEvents/1.0 (+https://warujie.jp; {CONTACT})"
PAGE_GAP = 4.0
JST = timezone(timedelta(hours=9))

# Hareruya: [calendar shop number, store, prefecture (JIS), city]
HARERUYA = [
    (1, "トーナメントセンター東京", 13, "千代田区"), (8, "秋葉原店", 13, "千代田区"), (27, "渋谷店", 13, "渋谷区"),
    (17, "吉祥寺店", 13, "武蔵野市"), (30, "町田店", 13, "町田市"), (12, "TCG BAR 飲める屋", 13, "千代田区"),
    (10, "横浜店", 14, "横浜市"), (21, "川崎店", 14, "川崎市"), (26, "千葉店", 12, "千葉市"), (2, "成田店", 12, "成田市"),
    (13, "大宮店", 11, "さいたま市"), (14, "宇都宮店", 9, "宇都宮市"), (22, "水戸店", 8, "水戸市"), (28, "高崎店", 10, "高崎市"),
    (4, "札幌店", 1, "札幌市"), (9, "仙台店", 4, "仙台市"), (16, "郡山店", 7, "郡山市"), (24, "新潟店", 15, "新潟市"),
    (25, "金沢店", 17, "金沢市"), (20, "甲府店", 19, "甲府市"), (31, "長野店", 20, "長野市"), (7, "静岡店", 22, "静岡市"),
    (6, "名古屋店", 23, "名古屋市"), (18, "大須店", 23, "名古屋市"), (33, "四日市店", 24, "四日市市"), (29, "京都店", 26, "京都市"),
    (5, "トーナメントセンター大阪", 27, "大阪市"), (23, "日本橋店", 27, "大阪市"), (19, "三宮店", 28, "神戸市"),
    (32, "岡山店", 33, "岡山市"), (15, "広島店", 34, "広島市"), (11, "高松店", 37, "高松市"), (3, "福岡店", 40, "福岡市"),
]
# Hareruya's format icons -> the site's formats (Dr draft, Se sealed; Ms middle school, ML
# Magic League and SP have no filter of their own)
HARERUYA_ICONS = {"St": "standard", "Pi": "pioneer", "Mo": "modern", "Le": "legacy", "Vi": "vintage",
                  "Pa": "pauper", "Co": "commander", "Pm": "premodern", "Dr": "limited", "Se": "limited"}
# Amenity Dream: store name on its list -> [its shop number, prefecture, city]
AMENITY = {
    "立川店": (19, 13, "立川市"), "札幌店": (4, 1, "札幌市"), "吉祥寺店": (1, 13, "武蔵野市"), "池袋パワー9店": (8, 13, "豊島区"),
    "中野店": (16, 13, "中野区"), "新宿店": (10, 13, "新宿区"), "秋葉原店": (7, 13, "千代田区"), "蒲田店": (18, 13, "大田区"),
    "町田店": (12, 13, "町田市"), "大宮店": (6, 11, "さいたま市"), "横浜店": (9, 14, "横浜市"), "大須店": (13, 23, "名古屋市"),
    "京都店": (14, 26, "京都市"), "なんば2号店": (3, 27, "大阪市"),
}
AMENITY_MAX_PAGES = 5   # pages read per day at most, should a day's list ever run over several
# Yellow Submarine: [schedule page, prefecture, city]; the store's name comes from the page
YELLOWSUB = [
    ("akihabara_mnt", 13, "千代田区"), ("akihabara_rpg", 13, "千代田区"), ("shinjuku", 13, "新宿区"), ("ikebukuro_gs", 13, "豊島区"),
    ("machida", 13, "町田市"), ("tachikawa", 13, "立川市"), ("yokohama", 14, "横浜市"), ("yokohama_m", 14, "横浜市"),
    ("mizo", 14, "川崎市"), ("kawasaki", 14, "川崎市"), ("kashiwa_m", 12, "柏市"), ("chiba_gs", 12, "千葉市"),
    ("omiya_ps", 11, "さいたま市"), ("kawagoe_cs", 11, "川越市"), ("utsunomiya", 9, "宇都宮市"), ("sapporo_gs", 1, "札幌市"),
    ("nagoya_gs", 23, "名古屋市"), ("nanba_s", 27, "大阪市"), ("nanba_3", 27, "大阪市"), ("kyoto", 26, "京都市"),
    ("sannomiya", 28, "神戸市"), ("himeji", 28, "姫路市"), ("hiroshima", 34, "広島市"), ("fukuoka_mc", 40, "福岡市"),
]
# the formats an event's name or notes name: スタン is スタンダード, プレモダン isn't モダン, and a
# モダンホライゾン draft is limited, not modern
FORMAT_WORDS = [
    ("premodern", r"プレモダン|premodern"), ("pauper", r"パウパー|pauper"), ("commander", r"統率者|EDH|コマンダー|commander"),
    ("standard", r"スタン(?!プ)|standard"), ("pioneer", r"パイオニア|pioneer"),
    ("modern", r"(?<!プレ)モダン(?!ホライゾン)|(?<!pre)modern(?! horizons)"),
    ("legacy", r"レガシー|legacy"), ("vintage", r"ヴィンテージ|vintage"),
    ("limited", r"ドラフト|シールド|リミテッド|プレリリース|draft|sealed|limited|prerelease"),
]
FORMAT_JA = {"standard": "スタンダード", "pioneer": "パイオニア", "modern": "モダン", "legacy": "レガシー", "vintage": "ヴィンテージ",
             "pauper": "パウパー", "commander": "統率者戦", "premodern": "プレモダン", "limited": "リミテッド"}


def formats_in(text):
    text = unicodedata.normalize("NFKC", text)
    return [f for f, pat in FORMAT_WORDS if re.search(pat, text, re.I)]


# an entry fee in yen: ¥1,000 / 1000円 / 無料 (a pack to buy instead, 1パック購入 or 200円以上購入, is no fee)
YEN_RE = re.compile(r"[¥￥]\s*(\d{1,3}(?:,\d{3})+|\d{1,6})(?!\d)|(?<![\d,])(\d{1,3}(?:,\d{3})+|\d{1,6})\s*円(?!\s*(?:分|以上|の?購入|相当))")


def yen_of(text):
    """The first entry fee in yen a piece of text gives, as a whole number (0 when it says free),
    or None."""
    text = unicodedata.normalize("NFKC", text or "").replace("¥", "¥")
    m = YEN_RE.search(text.replace("￥", "¥"))
    if m and not re.search(r"購入", text[m.end():m.end() + 6]):
        return int((m.group(1) or m.group(2)).replace(",", ""))
    if re.search(r"無料|free", text, re.I) and not re.search(r"\d", text):
        return 0
    return None


def tonamel_fee(description):
    """The fee on a Tonamel description's 参加費 line (【参加費】1,000円, 参加費：無料…)."""
    m = re.search(r"参加費[】\]）)]*[：:\s　]*([^\n<]{1,40})", description or "")
    return yen_of(m.group(1)) if m else None


def clean(s):
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", htmllib.unescape(s)).strip()


_last = [0.0]


def fetch(url, encoding=None, context=None, data=None):
    """One page (or, with data, one JSON POST), at least PAGE_GAP seconds after the last."""
    wait = _last[0] + PAGE_GAP - time.time()
    if wait > 0:
        time.sleep(wait)
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "ja"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60, context=context) as r:
            body = r.read()
            charset = encoding or r.headers.get_content_charset() or "utf-8"
            return body.decode(charset, "replace")
    finally:
        _last[0] = time.time()


def year_for(month, today):
    """A month/day list without a year: this year, or next year when the month is long past."""
    return today.year + 1 if month < today.month - 6 else today.year - 1 if month > today.month + 6 else today.year


# ---- Hareruya
DAY_RE = re.compile(r'<li id="(\d\d)" class="eventCalendar__calendarList__data">(.*?)(?=<li id="\d\d" class="eventCalendar__calendarList__data">|</ul>)', re.S)
EVENT_RE = re.compile(r'<a href="(https://www\.hareruyamtg\.com/ja/events/\d+/detail)">(.*?)</a>', re.S)


def parse_hareruya(html, year, month):
    out = []
    for day, block in DAY_RE.findall(html):
        for url, inner in EVENT_RE.findall(block):
            names = [clean(x) for x in re.findall(r'class="eventCalendar__calendarList__data__name">(.*?)</span>', inner, re.S)]
            if len(names) < 2:
                continue
            t, name = (names[0], " ".join(names[1:])) if re.fullmatch(r"\d{1,2}:\d{2}", names[0]) else ("", " ".join(names))
            icons = re.findall(r"format-icon-(\w+)", inner)
            fs = list(dict.fromkeys(HARERUYA_ICONS[i] for i in icons if i in HARERUYA_ICONS)) or formats_in(name)
            out.append({"d": f"{year:04d}-{month:02d}-{int(day):02d}", "t": t, "name": name, "url": url, "f": fs})
    return out


def read_hareruya(today, log):
    events = []
    months = [(today.year, today.month), (today.year + (today.month == 12), today.month % 12 + 1)]
    for shop, store, pref, city in HARERUYA:
        for y, m in months:
            url = f"https://www.hareruyamtg.com/ja/events/?shop={shop}&date={y:04d}{m:02d}"
            try:
                got = parse_hareruya(fetch(url), y, m)
            except Exception as e:
                log(f"  hareruya {store} {y}-{m:02d}: {e!r}"[:200])
                continue
            for e in got:
                e.update(p=pref, c=city, shop="hareruya", store=store)
            events += got
    return events


# Hareruya's calendar gives no fee; each event's own page does (■参加費 1,000円). A store's
# recurring event (the same name) costs the same each time, so one page is read per store and
# name, its fee kept in a small cache (hareruya_fees.json, beside events.json in R2) and re-read
# after HARERUYA_FEE_DAYS; at most HARERUYA_FEE_PAGES pages a night, the soonest events first.
HARERUYA_FEE_PAGES = 250          # about 17 minutes at PAGE_GAP
HARERUYA_FEE_DAYS = 30
HARERUYA_FEE_RE = re.compile(r'参加費</div>\s*<div class="event_detail_table_text">(.*?)</div>', re.S)


def hareruya_fee(html):
    """The fee on a Hareruya event page: its 参加費 row; None when the page gives none."""
    m = HARERUYA_FEE_RE.search(html)
    if m:
        return yen_of(clean(m.group(1)))
    m = re.search(r"■\s*参加費\s*([^■]{1,40})", clean(html))
    return yen_of(m.group(1)) if m else None


def hareruya_fees(events, cache, today, log, deadline):
    """Puts the cached fee on each Hareruya event, after reading the pages of the store-and-name
    pairs not in the cache yet (then the stalest), soonest event first, within the night's budget."""
    key = lambda e: f"{e['store']}|{e['name']}"
    first = {}
    for e in sorted((e for e in events if e.get("shop") == "hareruya"), key=lambda e: (e["d"], e["t"] or "99:99")):
        first.setdefault(key(e), e)
    stale = (today - timedelta(days=HARERUYA_FEE_DAYS)).isoformat()
    todo = [k for k in first if k not in cache] + sorted((k for k in first if k in cache and cache[k].get("read", "") < stale),
                                                          key=lambda k: cache[k].get("read", ""))
    read = 0
    for k in todo[:HARERUYA_FEE_PAGES]:
        if time.time() > deadline:
            log("  hareruya fees: out of time for tonight")
            break
        try:
            fee = hareruya_fee(fetch(first[k]["url"]))
        except Exception as e:
            log(f"  hareruya fee {first[k]['url']}: {e!r}"[:200])
            continue
        cache[k] = {"fee": fee, "read": today.isoformat(), "url": first[k]["url"]}
        read += 1
    for e in events:
        if e.get("shop") == "hareruya" and cache.get(key(e), {}).get("fee") is not None:
            e["fee"] = cache[key(e)]["fee"]
    known = sum(1 for k in first if k in cache)
    log(f"  hareruya fees: {read} pages read; {known} of {len(first)} store-and-name pairs known, {len(todo) - read} still to read")
    return cache


# ---- Amenity Dream
def amenity_context(host="amenitydream.co.jp"):
    """A normal, verifying TLS context that also knows the intermediate certificate the
    server leaves out, fetched from the AIA link in the server's own certificate."""
    ctx = ssl.create_default_context()
    try:
        urllib.request.urlopen(f"https://{host}/robots.txt", timeout=30, context=ctx).read()
        return ctx
    except Exception:
        pass
    from cryptography import x509
    from cryptography.hazmat.primitives.serialization import Encoding
    leaf = x509.load_pem_x509_certificate(ssl.get_server_certificate((host, 443)).encode())
    pems, cert = [], leaf
    for _ in range(3):
        try:
            aia = cert.extensions.get_extension_for_class(x509.AuthorityInformationAccess).value
        except x509.ExtensionNotFound:
            break
        urls = [a.access_location.value for a in aia if a.access_method == x509.oid.AuthorityInformationAccessOID.CA_ISSUERS]
        if not urls:
            break
        der = urllib.request.urlopen(urls[0], timeout=30).read()
        cert = x509.load_der_x509_certificate(der)
        pems.append(cert.public_bytes(Encoding.PEM).decode())
        if cert.issuer == cert.subject:
            break
    ctx.load_verify_locations(cadata="".join(pems))
    return ctx


def parse_amenity(html, today):
    out = []
    for row in re.findall(r"<tr>\s*(.*?)</tr>", html, re.S):
        tds = [clean(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(tds) < 5:
            continue
        m = re.match(r"(\d{1,2})/(\d{1,2})\D*?(\d{1,2}:\d{2})?$", tds[0])
        if not m or tds[1] not in AMENITY:
            continue
        mo, da = int(m.group(1)), int(m.group(2))
        shop, pref, city = AMENITY[tds[1]]
        name, style = tds[3], tds[4]
        fs = formats_in(name) or formats_in(style)
        # a fee column, should the table have one: a later cell that is only a sum (1,000円, ¥500, 無料)
        fee = next((yen_of(x) for x in tds[5:] if re.fullmatch(r"(参加費[：:]?\s*)?([¥￥]\s*[\d,]+|[\d,]+\s*円|無料)", x)), None)
        out.append({"d": f"{year_for(mo, today):04d}-{mo:02d}-{da:02d}", "t": m.group(3) or "", "p": pref, "c": city,
                    "shop": "amenity", "store": tds[1], "name": name,
                    "url": f"https://amenitydream.co.jp/matches/?type=2&shop={shop}&date={year_for(mo, today):04d}-{mo:02d}-{da:02d}", "f": fs,
                    "fee": fee})
    return out


def amenity_pages(html):
    """The further pages of a list, from its page links (<p class="pagination">), if it has any."""
    m = re.search(r'<p class="pagination">(.*?)</p>', html, re.S)
    links = re.findall(r'href="([^"]+)"', m.group(1)) if m else []
    urls = [urllib.parse.urljoin("https://amenitydream.co.jp/matches/", htmllib.unescape(u)) for u in links]
    return [u for u in dict.fromkeys(urls) if u.startswith("https://amenitydream.co.jp/matches/")]


def amenity_dates(html):
    """The days the list's 開催日 drop-down offers (about a month ahead)."""
    m = re.search(r'<select name="date">(.*?)</select>', html, re.S)
    return re.findall(r'value="(\d{4}-\d{2}-\d{2})"', m.group(1)) if m else []


def read_amenity(today, log):
    """Every store's MTG events, one day at a time (?type=2&shop=&date=<day>) for each day the
    page's date drop-down offers: the list without a day shows only the coming week."""
    try:
        ctx = amenity_context()
        first = fetch("https://amenitydream.co.jp/matches/?type=2&shop=&date=", context=ctx)
    except Exception as e:
        log(f"  amenity: {e!r}"[:300])
        return []
    events = parse_amenity(first, today)
    for day in amenity_dates(first):
        todo, done = [f"https://amenitydream.co.jp/matches/?type=2&shop=&date={day}"], set()
        while todo and len(done) < AMENITY_MAX_PAGES:
            url = todo.pop(0)
            done.add(url)
            try:
                html = fetch(url, context=ctx)
            except Exception as e:
                log(f"  amenity {day}: {e!r}"[:200])
                break
            events += parse_amenity(html, today)
            todo += [u for u in amenity_pages(html) if u not in done and u not in todo]
    return events


# ---- Tonamel (tonamel.com, KAYAC): stores and players list their events there
TONAMEL_LIST = "https://tonamel.com/competitions?game=mtg&region=JP"
TONAMEL_API = "https://tonamel.com/graphql/competition_management"
TONAMEL_MAX_PAGES = 30   # lists of 32 events
# shops read from their own pages: their Tonamel listings would only repeat them
TONAMEL_SKIP = re.compile(r"晴れる屋|イエローサブマリン|イエサブ|アメニティ")
# MINT's stores that list on Tonamel (MINTGAMESMTG店) join MINT's own entry, as 'GAMES MTG店'
TONAMEL_MINT = re.compile(r"^(?:MINT|ミント)\s*(GAMES\s*\S.*?|[^\x00-\x7f].*?)\s*(?:[(（].*)?$", re.I)
# Tonamel listings that aren't events: a store's play room for hire (【ルーム予約】貸切プレイルーム)
TONAMEL_NOT_EVENT = re.compile(r"ルーム予約|貸切")
PREF_NAMES = ["北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県", "茨城県", "栃木県", "群馬県", "埼玉県",
              "千葉県", "東京都", "神奈川県", "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県", "静岡県",
              "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県",
              "広島県", "山口県", "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県", "熊本県", "大分県",
              "宮崎県", "鹿児島県", "沖縄県"]
# the prefecture from a postal code's first two digits (〒100-0001 → 東京都)
POSTAL_PREF = {}
for _pref, _ranges in {13: "10-20", 14: "21-25", 12: "26-29", 8: "30-31", 9: "32", 11: "33-36", 10: "37", 20: "38-39",
                       19: "40", 22: "41-43", 23: "44-49", 21: "50", 24: "51", 25: "52", 27: "53-59", 26: "60-62", 29: "63",
                       30: "64", 28: "65-67", 31: "68", 32: "69", 33: "70-71", 34: "72-73", 35: "74-75", 37: "76", 36: "77",
                       39: "78", 38: "79", 40: "80-83", 41: "84", 42: "85", 43: "86", 44: "87", 45: "88", 46: "89", 47: "90",
                       18: "91", 17: "92", 16: "93", 15: "94-95", 7: "96-97", 4: "98", 6: "99", 5: "01", 3: "02", 2: "03",
                       1: "04-09"}.items():
    _a, _b = (_ranges.split("-") + [_ranges])[:2]
    for _n in range(int(_a), int(_b) + 1):
        POSTAL_PREF[f"{_n:02d}"] = _pref
# big cities often written without their prefecture
CITY_PREF = {"札幌市": 1, "仙台市": 4, "さいたま市": 11, "千葉市": 12, "横浜市": 14, "川崎市": 14, "相模原市": 14, "新潟市": 15,
             "静岡市": 22, "浜松市": 22, "名古屋市": 23, "京都市": 26, "大阪市": 27, "堺市": 27, "神戸市": 28, "岡山市": 33,
             "広島市": 34, "北九州市": 40, "福岡市": 40, "熊本市": 43, "那覇市": 47}


def place_of(address):
    """(prefecture number, city or ward) from a free-text Japanese address, or (0, "")."""
    a = unicodedata.normalize("NFKC", address or "").replace(" ", "")
    pref, rest = 0, a
    for i, name in enumerate(PREF_NAMES, 1):
        k = a.find(name)
        if k >= 0:
            pref, rest = i, a[k + len(name):]
            break
    if not pref:
        m = re.search(r"〒?(\d{3})-?\d{4}", a)
        if m:
            pref = POSTAL_PREF.get(m.group(1)[:2], 0)
    rest = re.sub(r"^〒?\d{3}-?\d{4}", "", rest)
    if pref == 13:
        m = re.match(r"(.+?区|.+?市(?!市)|.+?郡.+?[町村])", rest)
    else:
        m = re.match(r"(.+?郡.+?[町村]|.+?市(?!市)|.+?[町村])", rest)
    city = m.group(1) if m and len(m.group(1)) <= 10 else ""
    if not pref:
        pref = CITY_PREF.get(city, 0)
    return pref, city


def tonamel_time(v):
    """displayStartAt (Unix seconds, as a number or text, or an ISO time) as a date and HH:MM in Japan."""
    try:
        t = datetime.fromtimestamp(int(float(v)), timezone.utc)
    except (TypeError, ValueError):
        try:
            t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except ValueError:
            return "", ""
    t = t.astimezone(JST)
    return t.date().isoformat(), t.strftime("%H:%M")


def parse_tonamel(nodes):
    out = []
    for n in nodes:
        org = clean((n.get("organization") or {}).get("name") or "")
        if TONAMEL_SKIP.search(org) or str(n.get("status", "")).upper() in ("CANCELED", "CANCELLED"):
            continue
        for tm in (n.get("tournaments") or [])[:1]:
            if tm.get("isOnline"):
                continue
            loc = tm.get("location") or {}
            pref, city = place_of(((loc.get("address") or {}).get("input") or "") + " " + (loc.get("venueName") or ""))
            d, t = tonamel_time(tm.get("displayStartAt"))
            if not pref or not d:
                continue
            title = clean(n.get("title") or "")
            if TONAMEL_NOT_EVENT.search(title):
                continue
            shop, store = "tonamel", org or clean(loc.get("venueName") or "")
            m = TONAMEL_MINT.match(unicodedata.normalize("NFKC", org))
            if m:
                shop, store = "mint", re.sub(r"^GAMES(?=\S)", "GAMES ", m.group(1), flags=re.I)
            # the format: from the title, else the description's 【フォーマット】 line
            m = re.search(r"フォーマット[】\]：:\s　]*([^<\n]{1,40})", n.get("description") or "")
            fs = formats_in(title) or (formats_in(clean(m.group(1))) if m else [])
            out.append({"d": d, "t": t, "p": pref, "c": city, "shop": shop, "store": store, "name": title,
                        "url": f"https://tonamel.com/competition/{n['id']}", "f": fs, "fee": tonamel_fee(n.get("description"))})
    return out


def read_tonamel(today, log):
    """Tonamel's event-search page for MTG in Japan, opened in a headless browser as a visitor
    would (its API answers only its own page), keeping the event lists the page itself fetches
    (getPublicCompetitions, 32 at a time) and scrolling for more, PAGE_GAP seconds apart. Ads,
    trackers and pictures are not loaded."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("  tonamel: playwright is not installed")
        return []
    pages, horizon = [], (today + timedelta(days=40)).isoformat()

    def on_response(r):
        if r.url.startswith(TONAMEL_API) and "getPublicCompetitions" in (r.request.post_data_buffer or b"").decode("utf-8", "replace"):
            try:
                pages.append(r.json()["data"]["publicCompetitions"])
            except Exception as e:
                log(f"  tonamel: {e!r}"[:200])

    def allowed(route):
        u = urllib.parse.urlparse(route.request.url)
        if route.request.resource_type in ("image", "media", "font") or not (
                u.hostname == "tonamel.com" or (u.hostname or "").endswith((".googleapis.com", ".gstatic.com"))):
            return route.abort()
        return route.continue_()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(user_agent=USER_AGENT, locale="ja-JP", timezone_id="Asia/Tokyo")
            page.route("**/*", allowed)
            page.on("response", on_response)
            page.goto(TONAMEL_LIST, wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(PAGE_GAP * 2000)
            stop = "no list came"
            while pages:
                last = max((tonamel_time(tm.get("displayStartAt"))[0] for e in pages[-1].get("edges") or []
                            for tm in (e["node"].get("tournaments") or [])[:1]), default="")
                if not (pages[-1].get("pageInfo") or {}).get("hasNextPage"):
                    stop = "the end of the list"
                elif last > horizon:
                    stop = f"past {horizon}"
                elif len(pages) >= TONAMEL_MAX_PAGES:
                    stop = f"{TONAMEL_MAX_PAGES} lists"
                else:
                    n = len(pages)
                    for _ in range(3):   # scroll to the bottom, where the page asks for the next 32
                        page.mouse.wheel(0, 20000)
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        page.wait_for_timeout(PAGE_GAP * 1000)
                        if len(pages) > n:
                            break
                    if len(pages) > n:
                        continue
                    stop = "no more came on scrolling"
                break
            log(f"  tonamel: stopped at {stop} (last date {last if pages else '-'})")
            browser.close()
    except Exception as e:
        log(f"  tonamel: {e!r}"[:300])
    events = parse_tonamel([e["node"] for c in pages for e in c.get("edges") or []])
    log(f"  tonamel: {len(events)} offline events from {len(pages)} lists")
    return events


# ---- Yellow Submarine
def parse_yellowsub(html, slug, pref, city, today):
    title = re.search(r"<title>(.*?)</title>", html, re.S)
    store = clean(title.group(1)).split("|")[0].replace("イベント開催予定表", "").strip() if title else slug
    url = f"https://yellowsubmarine.co.jp/tmt_list/{slug}/"
    out = []
    for row in re.findall(r"<tr>(.*?)</tr>", html, re.S):
        tds = [clean(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(tds) < 7 or "マジック" not in tds[1]:
            continue
        m = re.match(r"(\d{1,2})/(\d{1,2})", tds[0])
        if not m:
            continue
        mo, da = int(m.group(1)), int(m.group(2))
        name, notes = tds[2], tds[6]
        fs = formats_in(name) or formats_in(notes.split("、")[0])
        if fs and not formats_in(name):
            name = f"{name}（{'・'.join(FORMAT_JA[f] for f in fs)}）"
        t = tds[3] if re.fullmatch(r"\d{1,2}:\d{2}", tds[3]) else ""
        out.append({"d": f"{year_for(mo, today):04d}-{mo:02d}-{da:02d}", "t": t, "p": pref, "c": city,
                    "shop": "yellowsub", "store": store, "name": name, "url": url, "f": fs, "fee": yen_of(tds[4])})
    return out


def read_yellowsub(today, log):
    events = []
    for slug, pref, city in YELLOWSUB:
        try:
            events += parse_yellowsub(fetch(f"https://yellowsubmarine.co.jp/tmt_list/{slug}/", encoding="cp932"), slug, pref, city, today)
        except Exception as e:
            log(f"  yellowsub {slug}: {e!r}"[:200])
    return events


# ---- calendar pictures (by hand): shops' X posts and MINT's schedule pages
MANUAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manual_events.json")
# what each hand-kept event may link to: for X, the post, or the shop's X account (where its
# calendars are) when the post's own link isn't known; for MINT, the store's schedule page
MANUAL_LINKS = {
    "x": re.compile(r"https://(?:x|twitter)\.com/[A-Za-z0-9_]{1,15}(?:/status/\d{1,20})?"),
    "mint": re.compile(r"https://mint-web\.jp/\?pid=\d{1,12}"),
}


def read_manual(today, log):
    """The events read by hand from shops' calendar pictures (manual_events.json): posts on X
    (shop "x") and MINT's monthly schedule pages (shop "mint"). An entry that doesn't hold
    together (a date, a time, a prefecture, a link of its kind) is left out."""
    try:
        with open(MANUAL, encoding="utf-8") as f:
            rows = json.load(f).get("events", [])
    except FileNotFoundError:
        return []
    out = []
    for r in rows:
        shop = r.get("shop") or "x"
        url = str(r.get("url") or "").replace("https://twitter.com/", "https://x.com/")
        url = url if shop == "mint" else url.split("?")[0]
        ok = (shop in MANUAL_LINKS and MANUAL_LINKS[shop].fullmatch(url)
              and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(r.get("d") or "")) and re.fullmatch(r"(\d{1,2}:\d{2})?", str(r.get("t") or ""))
              and isinstance(r.get("p"), int) and 1 <= r["p"] <= 47 and r.get("store") and r.get("name"))
        if not ok:
            log(f"  manual: left out {json.dumps(r, ensure_ascii=False)[:160]}")
            continue
        fs = [f for f in (r.get("f") or []) if f in FORMAT_JA] or formats_in(r["name"])
        fee = r.get("fee") if isinstance(r.get("fee"), int) and r["fee"] >= 0 else None
        fee_to = r.get("fee_to") if fee is not None and isinstance(r.get("fee_to"), int) and r["fee_to"] > fee else None
        out.append({"d": r["d"], "t": r.get("t") or "", "p": r["p"], "c": r.get("c") or "", "shop": shop,
                    "store": r["store"], "name": r["name"], "url": url, "f": fs, "fee": fee, "fee_to": fee_to})
    return out


def hand_kept(e):
    return any(link.fullmatch(e.get("url", "")) for link in MANUAL_LINKS.values())


def store_key(name):
    """A store's name for matching across sources: 'MINTGAMESMTG店' and 'GAMES MTG店' alike."""
    k = re.sub(r"\s+", "", unicodedata.normalize("NFKC", name)).lower()
    return re.sub(r"店$", "", re.sub(r"^(mint|ミント)", "", k))


def minutes(t):
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def same_event(a, b):
    """The same store's event on the same day: the same start, or starts within 30 minutes and a
    format in common (a shop's picture may give the start where Tonamel gives the doors)."""
    if a["d"] != b["d"] or store_key(a["store"]) != store_key(b["store"]):
        return False
    if a["t"] == b["t"]:
        return True
    return bool(a["t"] and b["t"] and abs(minutes(a["t"]) - minutes(b["t"])) <= 30 and set(a.get("f") or []) & set(b.get("f") or []))


def tidy(events):
    """One entry per event, sorted by day and start time. An event read by hand from a picture
    that a shop also lists on Tonamel (or another read source) keeps that entry instead: its own
    page, with the details (the owner's request, 2026-10-25)."""
    read = {}
    for e in events:
        if not hand_kept(e):
            read.setdefault((e["d"], store_key(e["store"])), []).append(e)
    seen, unique = set(), []
    for e in sorted(events, key=lambda e: (e["d"], e["t"] or "99:99", e["p"], e["store"], e["name"])):
        k = (e["d"], e["t"], e["shop"], e["store"], e["name"])
        twin = hand_kept(e) and next((o for o in read.get((e["d"], store_key(e["store"])), []) if same_event(e, o)), None)
        if twin and twin.get("fee") is None and e.get("fee") is not None:
            twin["fee"], twin["fee_to"] = e["fee"], e.get("fee_to")   # the picture's fee, where Tonamel gives none
        if k in seen or twin:
            continue
        seen.add(k)
        unique.append(e)
    for e in unique:   # no empty fields in the file
        for x in ("f", "fee", "fee_to"):
            if e.get(x) is None or e.get(x) == []:
                e.pop(x, None)
    return unique


def write(path, data, log):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    log(f"Wrote {len(data['events'])} events to {path} ({os.path.getsize(path) // 1024} KB)")


def keep(e, first, last):
    if not (first <= e["d"] <= last) or not e["name"]:
        return False
    if "[毎日開催]" in e["name"]:      # Hareruya's standing daily league, on every day of every store
        return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--days", type=int, default=35)
    ap.add_argument("--only", default="", help="comma-separated shops (for testing)")
    ap.add_argument("--manual-only", metavar="PUBLISHED", help="put manual_events.json into this published file; no shop is read")
    ap.add_argument("--fees", metavar="CACHE", help="Hareruya's fees: read and update this cache (hareruya_fees.json)")
    ap.add_argument("--fee-minutes", type=float, default=25, help="stop reading Hareruya's event pages this long after the start")
    args = ap.parse_args()
    log = lambda s: print(s, flush=True)
    started = time.time()
    today = datetime.now(JST).date()
    first, last = today.isoformat(), (today + timedelta(days=args.days)).isoformat()
    if args.manual_only:
        with open(args.manual_only, encoding="utf-8") as f:
            data = json.load(f)
        shops = [e for e in data.get("events", []) if not hand_kept(e) and keep(e, first, last)]
        if not shops:
            log("The published file has no shop events: nothing written.")
            sys.exit(1)
        got = [e for e in read_manual(today, log) if keep(e, first, last)]
        log(f"manual: {len(got)} events")
        write(args.out, {"updated": data.get("updated", ""), "sources": {**data.get("sources", {}), "manual": len(got)},
                         "events": tidy(shops + got)}, log)
        return
    readers = {"hareruya": read_hareruya, "amenity": read_amenity, "yellowsub": read_yellowsub, "tonamel": read_tonamel,
               "manual": read_manual}
    only = [s for s in args.only.split(",") if s]
    events, sources = [], {}
    for shop, reader in readers.items():
        if only and shop not in only:
            continue
        t0 = time.time()
        got = [e for e in reader(today, log) if keep(e, first, last)]
        sources[shop] = len(got)
        log(f"{shop}: {len(got)} events ({time.time() - t0:.0f} s)")
        events += got
    # the hand-kept events alone would replace every shop's: only with --only manual (testing)
    if not events or not any(n for shop, n in sources.items() if shop != "manual") and only != ["manual"]:
        log("No events from any shop's source: nothing written, so the published file stays.")
        sys.exit(1)
    if args.fees and sources.get("hareruya"):
        try:
            with open(args.fees, encoding="utf-8") as f:
                cache = json.load(f).get("fees", {})
        except (FileNotFoundError, ValueError):
            cache = {}
        cache = hareruya_fees(events, cache, today, log, started + args.fee_minutes * 60)
        with open(args.fees, "w", encoding="utf-8") as f:
            json.dump({"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "fees": cache}, f, ensure_ascii=False, separators=(",", ":"))
    write(args.out, {"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "sources": sources,
                     "events": tidy(events)}, log)


if __name__ == "__main__":
    main()
