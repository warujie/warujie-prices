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
  Amenity Dream  one page lists every store's MTG events, /matches/?type=2 (its server
                 sends an out-of-date certificate chain, so the missing intermediate is
                 fetched from the certificate's own AIA link and checked normally)
  Yellow Submarine  each store's schedule, /tmt_list/<store>/ (Shift_JIS), only the
                 rows whose game is マジック; the format is in the notes column

    python3 build_events.py --out site/events.json [--days 35]

Writes { "updated", "sources": {shop: events}, "events": [{ "d", "t", "p", "c",
"shop", "store", "name", "url", "f" }] } (docs/data-formats.md), or exits non-zero
without writing if every source failed, so yesterday's file stays published.
"""
import argparse
import html as htmllib
import json
import os
import re
import ssl
import sys
import time
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
# Yellow Submarine: [schedule page, prefecture, city]; the store's name comes from the page
YELLOWSUB = [
    ("akihabara_mnt", 13, "千代田区"), ("akihabara_rpg", 13, "千代田区"), ("shinjuku", 13, "新宿区"), ("ikebukuro_gs", 13, "豊島区"),
    ("machida", 13, "町田市"), ("tachikawa", 13, "立川市"), ("yokohama", 14, "横浜市"), ("yokohama_m", 14, "横浜市"),
    ("mizo", 14, "川崎市"), ("kawasaki", 14, "川崎市"), ("kashiwa_m", 12, "柏市"), ("chiba_gs", 12, "千葉市"),
    ("omiya_ps", 11, "さいたま市"), ("kawagoe_cs", 11, "川越市"), ("utsunomiya", 9, "宇都宮市"), ("sapporo_gs", 1, "札幌市"),
    ("nagoya_gs", 23, "名古屋市"), ("nanba_s", 27, "大阪市"), ("nanba_3", 27, "大阪市"), ("kyoto", 26, "京都市"),
    ("sannomiya", 28, "神戸市"), ("himeji", 28, "姫路市"), ("hiroshima", 34, "広島市"), ("fukuoka_mc", 40, "福岡市"),
]
# a format from words in an event's name or notes (the order matters: プレモダン before モダン)
FORMAT_WORDS = [
    ("premodern", r"プレモダン|premodern"), ("pauper", r"パウパー|pauper"), ("commander", r"統率者|EDH|コマンダー|commander"),
    ("standard", r"スタンダード|standard"), ("pioneer", r"パイオニア|pioneer"), ("modern", r"モダン|modern"),
    ("legacy", r"レガシー|legacy"), ("vintage", r"ヴィンテージ|vintage"),
    ("limited", r"ドラフト|シールド|リミテッド|プレリリース|draft|sealed|limited|prerelease"),
]
FORMAT_JA = {"standard": "スタンダード", "pioneer": "パイオニア", "modern": "モダン", "legacy": "レガシー", "vintage": "ヴィンテージ",
             "pauper": "パウパー", "commander": "統率者戦", "premodern": "プレモダン", "limited": "リミテッド"}


def formats_in(text):
    return [f for f, pat in FORMAT_WORDS if re.search(pat, text, re.I)]


def clean(s):
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", htmllib.unescape(s)).strip()


_last = [0.0]


def fetch(url, encoding=None, context=None):
    wait = _last[0] + PAGE_GAP - time.time()
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "ja"})
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
        out.append({"d": f"{year_for(mo, today):04d}-{mo:02d}-{da:02d}", "t": m.group(3) or "", "p": pref, "c": city,
                    "shop": "amenity", "store": tds[1], "name": name,
                    "url": f"https://amenitydream.co.jp/matches/?type=2&shop={shop}", "f": fs})
    return out


def read_amenity(today, log):
    try:
        return parse_amenity(fetch("https://amenitydream.co.jp/matches/?type=2&shop=&date=", context=amenity_context()), today)
    except Exception as e:
        log(f"  amenity: {e!r}"[:300])
        return []


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
                    "shop": "yellowsub", "store": store, "name": name, "url": url, "f": fs})
    return out


def read_yellowsub(today, log):
    events = []
    for slug, pref, city in YELLOWSUB:
        try:
            events += parse_yellowsub(fetch(f"https://yellowsubmarine.co.jp/tmt_list/{slug}/", encoding="cp932"), slug, pref, city, today)
        except Exception as e:
            log(f"  yellowsub {slug}: {e!r}"[:200])
    return events


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
    args = ap.parse_args()
    log = lambda s: print(s, flush=True)
    today = datetime.now(JST).date()
    first, last = today.isoformat(), (today + timedelta(days=args.days)).isoformat()
    readers = {"hareruya": read_hareruya, "amenity": read_amenity, "yellowsub": read_yellowsub}
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
    if not events:
        log("No events from any source: nothing written, so the published file stays.")
        sys.exit(1)
    seen, unique = set(), []
    for e in sorted(events, key=lambda e: (e["d"], e["t"] or "99:99", e["p"], e["store"], e["name"])):
        k = (e["d"], e["t"], e["shop"], e["store"], e["name"])
        if k not in seen:
            seen.add(k)
            if not e["f"]:
                del e["f"]
            unique.append(e)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    data = {"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "sources": sources, "events": unique}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    log(f"Wrote {len(unique)} events to {args.out} ({os.path.getsize(args.out) // 1024} KB)")


if __name__ == "__main__":
    main()
