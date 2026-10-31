#!/usr/bin/env python3
"""
build_prices.py - daily card price history for 悪知恵

Once a day this reads Scryfall's free 'default_cards' export (every printing,
with today's TCGplayer US-dollar and Cardmarket euro prices), adds today's
prices of every printing to the stored history, and writes:

    index.json         the list of dates in the history
    h/00.json.gz ...   the history itself, split into 256 files by card id
                       (the card page only loads the one file it needs):
                       US dollars (TCGplayer) and euros (Cardmarket),
                       non-foil and foil
    q/00.json.gz ...   today's prices at several shops - TCGplayer, Card
                       Kingdom (selling and buying), Cardsphere, Cardmarket -
                       from MTGJSON's daily price file; the lowest listings
                       (TCGCSV, Cardmarket's price guide); and offers by
                       condition with the copies in stock, from Card Kingdom's
                       and Mana Pool's public price lists and (with an API
                       token in CARDTRADER_TOKEN) CardTrader's sellers in Europe;
                       and ENNDAL GAMES' stock in yen (read once a night by
                       shop_enndal.py, given with --enndal); and PullVault's
                       singles in dollars (read and checked against their
                       photos by shop_pullvault.py, given with --pullvault)
    movers.json        biggest risers and fallers over 1, 7 and 30 days, for
                       the US market (dollars) and the European one (euros)
    ids.json.gz        MTGJSON's card ids matched to Scryfall's (kept for a week)

Scryfall only ever gives today's price. So that charts and price movers work
from the start, a young history (under 60 days) is filled in with the last
90 days of TCGplayer prices from MTGJSON's free price archive
(https://mtgjson.com/downloads/all-files/) - a one-off download of a few
hundred MB; once the history is long enough this step is skipped. Daily
values are kept for the last 120 days; older history keeps one value a week
(Mondays), so the files stay small for years.

Usage (normally run by GitHub Actions - see update-prices.yml):
    python3 build_prices.py --out site --previous https://warujie.github.io/warujie-prices/
    python3 build_prices.py --out site --previous <url> --allow-fresh   # very first run
    python3 build_prices.py --out site --previous site            # previous data in a folder
    python3 build_prices.py --out site --bulk cards.jsonl.gz      # test with a saved export
    python3 build_prices.py ... --backfill always    # fill in past prices from MTGJSON now
    python3 build_prices.py ... --backfill never     # never download MTGJSON's archive
    python3 build_prices.py ... --quotes never       # skip the shop prices of the day

Data: Scryfall (https://scryfall.com/docs/api/bulk-data). Prices are
TCGplayer market prices supplied through Scryfall; earlier days come from
MTGJSON's TCGplayer prices.
"""
import argparse
import concurrent.futures
import threading
import gzip, math
import io
import json
import lzma
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone

import shop_enndal
import shop_pullvault

BULK_DATA_ENDPOINT = "https://api.scryfall.com/bulk-data"
HEADERS = {"User-Agent": "WarujiePriceHistory/1.1 (+https://github.com/warujie/warujie-prices)", "Accept": "application/json"}
TCGCSV_BASE = "https://tcgcsv.com/"   # TCGplayer's prices, republished once a day (lowest listings too)
CARDMARKET_GUIDE = "https://downloads.s3.cardmarket.com/productCatalog/priceGuide/price_guide_1.json"   # Cardmarket's own daily price guide (Magic)
LOWS_SOURCE = "TCGCSV (TCGplayer lowest listings) and Cardmarket's price guide (lowest offers)"
CK_PRICELIST = "https://api.cardkingdom.com/api/v2/pricelist"          # Card Kingdom's public price list (stock by condition)
MANAPOOL_VARIANTS = "https://manapool.com/api/v1/prices/variants"      # Mana Pool's public prices (by language, condition, finish)
OFFERS_SOURCE = "Card Kingdom and Mana Pool (offers by condition, with stock; their public price lists)"
CK_CONDITIONS = (("nm", "NM"), ("ex", "EX"), ("vg", "VG"), ("g", "G"))
LISTINGS_PER_FINISH = 12    # offers kept per printing, market and finish (the cheapest)
CARDTRADER_API = "https://api.cardtrader.com/api/v2"                    # needs a CardTrader account's API token (CARDTRADER_TOKEN)
CARDTRADER_SOURCE = "CardTrader (offers by condition, with stock, from sellers in Europe; CardTrader API)"
CARDTRADER_MINUTES = 40     # time allowed for reading CardTrader's marketplace each day
CARDTRADER_WORKERS = 4      # sets read at the same time
CARDTRADER_PAUSE = 0.15     # seconds between marketplace requests (CardTrader allows 10 a second)
FX_TO_EUR = "https://api.frankfurter.dev/v2/rate/{cur}/EUR"           # the European Central Bank's rate, for CardTrader prices not in euros
CT_CONDITIONS = {"Mint": "M", "Near Mint": "NM", "Slightly Played": "SP", "Moderately Played": "MP",
                 "Played": "PL", "Heavily Played": "HP", "Poor": "PO"}
CT_LANGS = {"jp": "JA", "ja": "JA", "kr": "KO", "ko": "KO", "zh-cn": "CS", "zh-tw": "CT"}
EUROPE = set("AD AL AT BA BE BG BY CH CY CZ DE DK EE ES FI FO FR GB GI GR HR HU IE IS IT LI LT LU LV MC MD ME MK MT NL NO PL PT RO RS SE SI SK SM UA VA XK".split())
ENNDAL_SOURCE = "ENNDAL GAMES (offers in yen by language and condition, with stock; read once a night, with the shop's permission)"
PULLVAULT_SOURCE = "PullVault (singles in dollars, each checked against the listing's photos; read once a day, with the shop's permission)"
OFFER_MARKETS = {"ck": "us", "mp": "us", "pv": "us", "ct": "eu", "ed": "jp"}   # "ed" = ENNDAL GAMES: prices in yen, not cents

FORMAT_VERSION = 1
DAILY_DAYS = 120            # keep every day for this long, then weekly
WINDOWS = (1, 7, 30)        # movers: change over this many days
MOVERS_PER_LIST = 50
MIN_PRICE_CENTS = 200       # movers: the card must be worth at least $2 both then and now ...
MIN_CHANGE_CENTS = 50       # ... and have moved by at least $0.50 (cheap cards jump around)
SERIES = 4                  # per printing: US dollars non-foil, foil; euros non-foil, foil
SERIES_NAMES = ["usd", "usd_foil", "eur", "eur_foil"]
MARKETS = {"all": (0, 1), "eur": (2, 3)}   # movers.json: "all" = US market (dollars), "eur" = Cardmarket (euros)
HISTORY_PROVIDERS = {"tcgplayer": ("USD", 0), "cardmarket": ("EUR", 2)}   # MTGJSON shop -> currency, first series
IDS_MAX_AGE_DAYS = 7        # MTGJSON-to-Scryfall id list: downloaded again after a week
SCRYFALL_SOURCE = "Scryfall (TCGplayer market prices, USD; Cardmarket trend prices, EUR)"
QUOTES_SOURCE = "MTGJSON (today's prices at several shops)"
COLOR_ORDER = "WUBRG"

MTGJSON_BASE = os.environ.get("WARUJIE_MTGJSON_BASE", "https://mtgjson.com/api/v5/")
BACKFILL_IF_FEWER = 60      # auto: fill in past prices while the history has fewer dates than this
BACKFILL_DAYS = 90          # MTGJSON keeps 90 days
BACKFILL_RETRY_DAYS = 7     # auto: after a failed attempt, wait this long before downloading again

EXCLUDED_LAYOUTS = {"token", "double_faced_token", "emblem", "art_series", "vanguard", "planar", "scheme"}
EXCLUDED_SET_TYPES = {"token", "memorabilia", "minigame", "alchemy"}


# ------------------------------------------------------------------ download
def http_get(url, tries=4):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            return urllib.request.urlopen(req, timeout=120)
        except urllib.error.HTTPError as err:
            if err.code == 404:
                raise
            last = err
        except (urllib.error.URLError, TimeoutError, ConnectionError) as err:
            last = err
        time.sleep(5 * (attempt + 1))
    raise last


def bulk_url():
    with http_get(BULK_DATA_ENDPOINT) as resp:
        manifest = json.load(resp)
    for entry in manifest.get("data", []):
        if entry.get("type") == "default_cards":
            if entry.get("jsonl_download_uri"):
                return entry["jsonl_download_uri"]
            if entry.get("download_uri"):
                return entry["download_uri"]
    raise RuntimeError("Scryfall's bulk-data list has no 'default_cards' download")


def iter_cards_from_stream(stream, name):
    """Cards from a JSON array or JSON Lines export, gzipped or not."""
    head = stream.peek(2)[:2] if hasattr(stream, "peek") else b""
    if head == b"\x1f\x8b" or name.endswith(".gz"):
        stream = gzip.GzipFile(fileobj=stream)
    text = io.TextIOWrapper(stream, encoding="utf-8")
    first = text.read(1)
    while first and first.isspace():
        first = text.read(1)
    if first == "[":
        for card in json.loads(first + text.read()):
            yield card
        return
    pending = first
    for line in text:
        line = (pending + line).strip()
        pending = ""
        if line:
            yield json.loads(line)


def iter_cards(source):
    if os.path.exists(source):
        with open(source, "rb") as fh:
            yield from iter_cards_from_stream(io.BufferedReader(fh), source)
    else:
        with http_get(source) as resp:
            yield from iter_cards_from_stream(io.BufferedReader(resp), source)


# ------------------------------------------------------------------ previous history
def load_published(source, rel):
    """A file of the currently published data (URL or folder); None if absent."""
    if not source:
        return None
    if source.startswith(("http://", "https://")):
        url = source.rstrip("/") + "/" + rel
        try:
            with http_get(url) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as err:
            if err.code == 404:
                return None
            raise
    else:
        path = os.path.join(source, rel)
        if not os.path.exists(path):
            return None
        with open(path, "rb") as fh:
            raw = fh.read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


def read_previous(source, allow_fresh):
    """Returns (dates, {shard: {id: [usd, usd foil, eur, eur foil]}}, index). An
    empty history when nothing has been published yet. Any other failure stops
    the run, so a network hiccup can never wipe out the collected history."""
    def load(rel):
        return load_published(source, rel)

    if not source:
        return [], {}, {}
    index = load("index.json")
    if index is None:
        if not allow_fresh:
            hint = ""
            if source.startswith("http") and "warujie-prices" not in source:
                hint = (" This address is not the warujie-prices site: the workflow seems to be running in the wrong"
                        " repository. It belongs in its own repository named warujie-prices.")
            raise SystemExit(f"No index.json at {source} - stopping so a published history is never replaced by an "
                             "empty one. On the very first run, pass --allow-fresh." + hint)
        print("No earlier history found - starting a new one.")
        return [], {}, {}
    dates = index.get("dates", [])
    shards = {}
    for key in index.get("shards") or [f"{i:02x}" for i in range(256)]:
        data = load(f"h/{key}.json.gz")
        if data is None:
            print(f"  warning: h/{key}.json.gz is missing - that part starts again")
            continue
        # line the series up with the index's dates (they always match unless
        # an upload was interrupted half-way)
        own = data.get("dates", dates)
        if own == dates:
            shards[key] = data.get("p", {})
        else:
            pos = {d: n for n, d in enumerate(own)}
            shards[key] = {
                cid: [[s[pos[d]] if d in pos and pos[d] < len(s) else None for d in dates] for s in series]
                for cid, series in data.get("p", {}).items()
            }
        for series in shards[key].values():   # older files only had the dollar series
            while len(series) < SERIES:
                series.append([None] * len(dates))
    print(f"Earlier history: {len(dates)} dates, {sum(len(s) for s in shards.values())} printings")
    return dates, shards, index


# ------------------------------------------------------------------ past prices from MTGJSON
class _JsonStream:
    """Reads a huge JSON file piece by piece: the MTGJSON files are gigabytes
    once unpacked, far too big to load at once."""

    def __init__(self, text):
        self.text, self.buf, self.pos, self.eof = text, "", 0, False
        self.dec = json.JSONDecoder()

    def more(self):
        chunk = self.text.read(1 << 20)
        if not chunk:
            self.eof = True
            return False
        self.buf = self.buf[self.pos:] + chunk
        self.pos = 0
        return True

    def peek(self):
        while True:
            while self.pos < len(self.buf) and self.buf[self.pos] in " \t\r\n":
                self.pos += 1
            if self.pos < len(self.buf):
                return self.buf[self.pos]
            if not self.more():
                return ""

    def expect(self, ch):
        if self.peek() != ch:
            raise ValueError(f"unexpected content in the MTGJSON file (wanted {ch!r})")
        self.pos += 1

    def value(self):
        self.peek()
        while True:
            try:
                val, end = self.dec.raw_decode(self.buf, self.pos)
            except json.JSONDecodeError:
                if self.eof or not self.more():
                    raise
                continue
            if end >= len(self.buf) and not self.eof and self.more():
                continue   # a number at the very end might continue in the next piece
            self.pos = end
            return val


def mtgjson_items(source):
    """(key, value) for every entry of the top-level "data" object of an
    MTGJSON file (.json, .json.gz or .json.xz; a path or a URL)."""
    if source.startswith(("http://", "https://")):
        raw = http_get(source)
    else:
        raw = open(source, "rb")
    with raw:
        if source.endswith(".xz"):
            stream = lzma.open(raw)
        elif source.endswith(".gz"):
            stream = gzip.GzipFile(fileobj=raw)
        else:
            stream = raw
        reader = _JsonStream(io.TextIOWrapper(stream, encoding="utf-8"))
        reader.expect("{")
        while True:
            ch = reader.peek()
            if ch in ("}", ""):
                return
            if ch == ",":
                reader.pos += 1
                continue
            key = reader.value()
            reader.expect(":")
            if key != "data":
                reader.value()   # "meta": not needed
                continue
            reader.expect("{")
            while True:
                ch = reader.peek()
                if ch == "}":
                    reader.pos += 1
                    break
                if ch == ",":
                    reader.pos += 1
                    continue
                if ch == "":
                    raise ValueError("the MTGJSON file ended early")
                k = reader.value()
                reader.expect(":")
                yield k, reader.value()


def scryfall_ids(ids_src, previous, today):
    """MTGJSON card id -> Scryfall id. The list published last time is reused
    for a week; after that (or without one) MTGJSON's identifier file is read."""
    old = None
    try:
        old = load_published(previous, "ids.json.gz")
    except Exception as err:
        print(f"  note: could not read the published id list ({err})")
    if old and old.get("map") and old.get("date"):
        age = (date.fromisoformat(today) - date.fromisoformat(old["date"])).days
        if 0 <= age < IDS_MAX_AGE_DAYS:
            return old["map"], old["date"]
    print("Reading MTGJSON's card ids...")
    found = {}
    for uuid, card in mtgjson_items(ids_src):
        sid = ((card or {}).get("identifiers") or {}).get("scryfallId")
        if sid:
            found[uuid] = sid
    print(f"  {len(found)} MTGJSON printings matched to Scryfall")
    if not found:
        raise ValueError("no Scryfall ids in MTGJSON's identifier file")
    return found, today


def backfill(dates, shards, today, prices_src, scryfall_id):
    """Adds the days before the stored history (up to BACKFILL_DAYS back) from
    MTGJSON's TCGplayer (dollars) and Cardmarket (euros) prices. Stored values
    are never replaced."""
    print("Filling in past prices from MTGJSON...")

    have = set(dates)
    first = (date.fromisoformat(today) - timedelta(days=BACKFILL_DAYS)).isoformat()
    col = {}          # date -> column in the arrays below
    past = {}         # scryfall id -> [prices by column] for each of the SERIES
    for uuid, formats in mtgjson_items(prices_src):
        sid = scryfall_id.get(uuid)
        if not sid:
            continue
        paper = (formats or {}).get("paper") or {}
        wanted = []
        for shop, (currency, first_series) in HISTORY_PROVIDERS.items():
            prov = paper.get(shop) or {}
            if prov.get("currency", currency) != currency:
                continue
            retail = prov.get("retail") or {}
            wanted.append((first_series, retail.get("normal")))
            wanted.append((first_series + 1, retail.get("foil") or retail.get("etched")))
        for which, points in wanted:
            for d, price in (points or {}).items():
                if d in have or d >= today or d < first:
                    continue
                c = cents(price)
                if c is None:
                    continue
                k = col.get(d)
                if k is None:
                    k = col[d] = len(col)
                series = past.get(sid)
                if series is None:
                    series = past[sid] = [[] for _ in range(SERIES)]
                row = series[which]
                if len(row) <= k:
                    row.extend([None] * (k + 1 - len(row)))
                if row[k] is None:
                    row[k] = c
    if not col:
        print("  MTGJSON had no earlier days to add.")
        return dates, shards

    merged = sorted(have | set(col))
    old_pos = {d: i for i, d in enumerate(dates)}
    n = len(merged)
    for shard in shards.values():
        for cid, series in shard.items():
            shard[cid] = [[s[old_pos[d]] if d in old_pos and old_pos[d] < len(s) else None for d in merged] for s in series]
    where = [(merged.index(d), k) for d, k in col.items()]
    added = 0
    for sid, got in past.items():
        shard = shards.setdefault(sid[:2], {})
        series = shard.get(sid)
        if series is None:
            series = shard[sid] = [[None] * n for _ in range(SERIES)]
            added += 1
        for which, values in enumerate(got):
            if not values:
                continue
            target = series[which]
            for m, k in where:
                if k < len(values) and values[k] is not None and target[m] is None:
                    target[m] = values[k]
    print(f"  added {len(col)} earlier days ({min(col)} - {max(col)}) for {len(past)} printings ({added} new)")
    return merged, shards


def shop_prices(today_src, scryfall_id):
    """Today's prices at every shop in MTGJSON's daily price file, by Scryfall
    id: {shop: [selling non-foil, selling foil, buying non-foil, buying foil]}
    in cents (trailing gaps left off), plus each shop's currency."""
    print("Reading today's shop prices from MTGJSON...")
    quotes, currencies = {}, {}
    latest = lambda points: (points[max(points)] if points else None)
    for uuid, formats in mtgjson_items(today_src):
        sid = scryfall_id.get(uuid)
        if not sid:
            continue
        for shop, prov in ((formats or {}).get("paper") or {}).items():
            if not isinstance(prov, dict):
                continue
            retail, buy = prov.get("retail") or {}, prov.get("buylist") or {}
            vals = [cents(latest(retail.get("normal") or {})), cents(latest(retail.get("foil") or retail.get("etched") or {})),
                    cents(latest(buy.get("normal") or {})), cents(latest(buy.get("foil") or buy.get("etched") or {}))]
            while vals and vals[-1] is None:
                vals.pop()
            if not vals:
                continue
            currencies[shop] = prov.get("currency") or currencies.get(shop) or ""
            quotes.setdefault(sid, {})[shop] = vals
    if not quotes:
        raise ValueError("no shop prices in MTGJSON's daily file")
    print(f"  {len(quotes)} printings with shop prices from {', '.join(sorted(currencies))}")
    return quotes, currencies


def previous_quotes(source, index):
    """Yesterday's shop prices, republished when today's can't be read."""
    if not index.get("quotes_date"):
        return None
    quotes = {}
    for key in index.get("shards") or [f"{i:02x}" for i in range(256)]:
        data = load_published(source, f"q/{key}.json.gz")
        if data:
            quotes.update(data.get("p") or {})
    return (quotes, index.get("providers") or {}, index["quotes_date"]) if quotes else None


# ------------------------------------------------------------------ cheapest listings
def fetch_json(source):
    """JSON from a URL or a local file/folder path."""
    if source.startswith(("http://", "https://")):
        with http_get(source) as resp:
            raw = resp.read()
    else:
        with open(source, "rb") as fh:
            raw = fh.read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


def tcgplayer_lows(base, wanted):
    """Lowest TCGplayer listing (any condition) by product id, from TCGCSV:
    {product id: [non-foil, foil]} in cents, for the products in `wanted`."""
    print("Reading TCGplayer's lowest listings from TCGCSV...")
    join = (lambda *p: base.rstrip("/") + "/" + "/".join(p)) if base.startswith("http") else (lambda *p: os.path.join(base, *p))
    groups = fetch_json(join("tcgplayer", "1", "groups")).get("results") or []
    lows, failed = {}, 0
    for g in groups:
        gid = str(g.get("groupId") or "")
        if not gid:
            continue
        try:
            rows = fetch_json(join("tcgplayer", "1", gid, "prices")).get("results") or []
        except Exception:   # one set missing is fine
            failed += 1
            continue
        for r in rows:
            pid = r.get("productId")
            if pid not in wanted:
                continue
            c = cents(r.get("lowPrice"))
            if c is None:
                continue
            slot = 1 if "foil" in str(r.get("subTypeName") or "").lower() else 0
            lows.setdefault(pid, [None, None])[slot] = c
        if base.startswith("http"):
            time.sleep(0.1)   # TCGCSV asks for a short pause between requests
    if not lows:
        raise ValueError("no TCGplayer prices found")
    print(f"  {len(lows)} products from {len(groups)} sets" + (f" ({failed} sets could not be read)" if failed else ""))
    return lows


def cardmarket_lows(source, wanted):
    """Lowest Cardmarket offer (any condition or language) by product id:
    {product id: [non-foil, foil]} in cents, from Cardmarket's price guide."""
    print("Reading Cardmarket's price guide...")
    lows = {}
    for r in fetch_json(source).get("priceGuides") or []:
        pid = r.get("idProduct")
        if pid not in wanted:
            continue
        vals = [cents(r.get("low")), cents(r.get("low-foil"))]
        if vals != [None, None]:
            lows[pid] = vals
    if not lows:
        raise ValueError("no Cardmarket prices found")
    print(f"  {len(lows)} products")
    return lows


def add_lows(quote_data, today, products, args):
    """Adds "tcgplayer_low" and "cardmarket_low" to today's shop prices."""
    quotes, currencies, qdate = quote_data or ({}, {}, today)
    found = False
    for shop, currency, read, src, slot in (
            ("tcgplayer_low", "USD", tcgplayer_lows, args.tcgcsv or TCGCSV_BASE, 0),
            ("cardmarket_low", "EUR", cardmarket_lows, args.cardmarket_guide or CARDMARKET_GUIDE, 1)):
        wanted = {}
        for cid, ids in products.items():
            for i, pid in enumerate(ids[slot] if slot == 0 else [ids[slot]]):
                if pid:
                    wanted.setdefault(pid, []).append((cid, i))
        try:
            lows = read(src, wanted)
        except Exception as err:   # the daily update goes on without them
            print(f"  note: {shop} prices could not be read ({err}).")
            continue
        for pid, vals in lows.items():
            for cid, etched in wanted[pid]:
                row = quotes.setdefault(cid, {}).setdefault(shop, [None, None])
                if etched:      # TCGplayer lists etched foils as their own product
                    if row[1] is None:
                        row[1] = vals[1] if vals[1] is not None else vals[0]
                else:
                    row[0] = vals[0] if vals[0] is not None else row[0]
                    if vals[1] is not None:
                        row[1] = vals[1]
        currencies[shop] = currency
        found = True
    if not found:
        return quote_data
    for shops in quotes.values():
        for shop in ("tcgplayer_low", "cardmarket_low"):
            row = shops.get(shop)
            if row is not None:
                while row and row[-1] is None:
                    row.pop()
                if not row:
                    del shops[shop]
    return quotes, currencies, qdate or today


# ------------------------------------------------------------------ offers with condition and stock
def json_list(source, key="data", meta=None):
    """The items of the list under `key` in a JSON object (a URL or a file),
    read piece by piece - Mana Pool's list is about 200 MB. The object's other
    top-level values go into `meta`. Card Kingdom sends its JSON inside an
    HTML page; the wrapping is skipped."""
    raw = http_get(source) if source.startswith(("http://", "https://")) else open(source, "rb")
    with raw:
        stream = gzip.GzipFile(fileobj=raw) if source.endswith(".gz") else raw
        reader = _JsonStream(io.TextIOWrapper(stream, encoding="utf-8"))
        while "{" not in reader.buf[reader.pos:]:
            if not reader.more():
                raise ValueError(f"no JSON object in {source}")
        reader.pos = reader.buf.index("{", reader.pos)
        reader.expect("{")
        while True:
            ch = reader.peek()
            if ch in ("}", ""):
                return
            if ch == ",":
                reader.pos += 1
                continue
            k = reader.value()
            reader.expect(":")
            if k != key:
                v = reader.value()
                if meta is not None:
                    meta[k] = v
                continue
            reader.expect("[")
            while True:
                ch = reader.peek()
                if ch == "]":
                    reader.pos += 1
                    break
                if ch == ",":
                    reader.pos += 1
                    continue
                if ch == "":
                    raise ValueError(f"the list in {source} ended early")
                yield reader.value()


def cardkingdom_offers(source, rows, links):
    """Card Kingdom's own stock: a row per condition with copies in stock -
    ["ck", foil, condition, cents, copies, ""]. Card Kingdom grades NM, EX, VG
    and G."""
    print("Reading Card Kingdom's price list...")
    meta, n = {}, 0
    for r in json_list(source, meta=meta):
        sid = r.get("scryfall_id")
        if not sid:
            continue
        foil = 1 if str(r.get("is_foil")).lower() == "true" else 0
        cv = r.get("condition_values") or {}
        for key, grade in CK_CONDITIONS:
            c, qty = cents(cv.get(key + "_price")), cv.get(key + "_qty") or 0
            if c and qty > 0:
                rows.setdefault(sid, []).append(["ck", foil, grade, c, int(qty), ""])
                n += 1
        if r.get("url"):
            pair = links.setdefault(sid, {}).setdefault("ck", ["", ""])
            if not pair[foil]:
                pair[foil] = r["url"]
    if not n:
        raise ValueError("no Card Kingdom stock found")
    print(f"  {n} offers")
    return str((meta.get("meta") or {}).get("created_at") or "")


def manapool_offers(source, rows, links):
    """Mana Pool's marketplace: the cheapest offer and the copies available for
    every language, condition and finish - ["mp", foil, condition, cents,
    copies, language ("" = English)]. Conditions NM, LP, MP, HP, DMG."""
    print("Reading Mana Pool's price list...")
    meta, n = {}, 0
    for r in json_list(source, meta=meta):
        sid = r.get("scryfall_id")
        c, qty = r.get("low_price"), r.get("available_quantity") or 0
        if not sid or not isinstance(c, int) or c <= 0 or qty <= 0:
            continue
        foil = 0 if (r.get("finish_id") or "NF") == "NF" else 1     # FO and etched (EF) count as foil
        lang = str(r.get("language_id") or "EN").upper()
        rows.setdefault(sid, []).append(["mp", foil, str(r.get("condition_id") or ""), c, int(qty), "" if lang == "EN" else lang])
        n += 1
        if r.get("url") and "mp" not in links.get(sid, {}):
            links.setdefault(sid, {})["mp"] = r["url"]
    if not n:
        raise ValueError("no Mana Pool offers found")
    print(f"  {n} offers")
    return str((meta.get("meta") or {}).get("as_of") or "")


def cardtrader_offers(source, token, rows, links, minutes=CARDTRADER_MINUTES, resume=0, seen=None):
    """CardTrader's marketplace (the cheapest 25 copies of every card, foil and
    non-foil asked for separately), keeping sellers in Europe and prices in
    euros: ["ct", foil, condition, cents, copies, language, seller's country].
    `source` is the API, or a folder of saved answers for testing.

    The sets are read in order of their CardTrader number, starting after
    `resume` (where the previous day stopped) and going round; reading stops
    after `minutes`. Returns (time, the last set read). The Scryfall ids of
    every card in the sets read go into `seen`."""
    print("Reading CardTrader's marketplace...")
    remote = source.startswith(("http://", "https://"))
    pace = threading.Lock()
    calls = {"t": 0.0}

    def get(path, pause=0.06):
        if not remote:
            name = path.replace("?", "_").replace("&", "_").replace("=", "-").replace("/", "_") + ".json"
            with open(os.path.join(source, name), encoding="utf-8") as fh:
                return json.load(fh)
        for attempt in range(4):
            with pace:   # requests are started at most every `pause` seconds, whatever the threads
                wait = calls["t"] + pause - time.time()
                if wait > 0:
                    time.sleep(wait)
                calls["t"] = time.time()
            req = urllib.request.Request(source.rstrip("/") + "/" + path, headers=dict(HEADERS, Authorization="Bearer " + token))
            try:
                with urllib.request.urlopen(req, timeout=180) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as err:
                if err.code == 429 and attempt < 3:
                    time.sleep(10 * (attempt + 1))
                    continue
                raise

    start, n, skipped, failed, other_cur = time.time(), 0, {}, 0, set()
    to_eur = {"EUR": 1.0}   # CardTrader gives prices in the account's currency: others are converted at the ECB rate

    def eur_rate(cur):
        if cur not in to_eur:
            try:
                if not remote:
                    raise ValueError("no rates when testing")
                with http_get(FX_TO_EUR.format(cur=cur)) as resp:
                    to_eur[cur] = float(json.load(resp)["rate"])
                print(f"  CardTrader prices are in {cur}: converted to euros at {to_eur[cur]}")
            except Exception as err:
                print(f"  note: no {cur}-to-euro rate ({err})")
                to_eur[cur] = None
        return to_eur[cur]

    def read_set(eid):
        """(Scryfall id by blueprint, [non-foil answer, foil answer]) of one set."""
        bps = get(f"blueprints/export?expansion_id={eid}")
        sid_of = {b["id"]: b["scryfall_id"] for b in bps if b.get("scryfall_id") and b.get("id")}
        if not sid_of:
            return sid_of, []
        return sid_of, [get(f"marketplace/products?expansion_id={eid}&foil={'true' if foil else 'false'}", pause=CARDTRADER_PAUSE)
                         for foil in (0, 1)]

    def add(sid_of, answers):
        nonlocal n
        for foil, data in enumerate(answers):
            for bp_id, products in (data or {}).items():
                sid = sid_of.get(int(bp_id))
                if not sid:
                    continue
                for prod in products or []:
                    props = prod.get("properties_hash") or {}
                    if prod.get("on_vacation") or prod.get("graded") or props.get("altered") or props.get("signed"):
                        continue
                    country = str((prod.get("user") or {}).get("country_code") or "").upper()
                    if country not in EUROPE:
                        skipped[country or "?"] = skipped.get(country or "?", 0) + 1
                        continue
                    price = prod.get("price") or {}
                    cur = str(price.get("currency") or "").upper()
                    rate = eur_rate(cur) if cur else None
                    if not rate:
                        other_cur.add(cur or "?")
                        continue
                    c, qty = price.get("cents"), prod.get("quantity") or 0
                    if isinstance(c, int) and cur != "EUR":
                        c = int(round(c * rate))
                    if not isinstance(c, int) or c <= 0 or qty <= 0:
                        continue
                    lang = str(props.get("mtg_language") or "en").lower()
                    lang = "" if lang == "en" else CT_LANGS.get(lang, lang.upper())
                    is_foil = 1 if props.get("mtg_foil") in (True, "true") else 0 if props.get("mtg_foil") in (False, "false") else foil
                    cond = CT_CONDITIONS.get(str(props.get("condition") or ""), "")
                    rows.setdefault(sid, []).append(["ct", is_foil, cond, c, int(qty), lang, country])
                    links.setdefault(sid, {})["ct"] = int(bp_id)
                    n += 1

    expansions = sorted((e for e in get("expansions") if e.get("game_id") == 1 and isinstance(e.get("id"), int)), key=lambda e: e["id"])
    k = next((i for i, e in enumerate(expansions) if e["id"] > resume), 0)
    order = expansions[k:] + expansions[:k]
    done, last = 0, resume
    workers = CARDTRADER_WORKERS if remote else 1
    with concurrent.futures.ThreadPoolExecutor(workers) as pool:
        for i in range(0, len(order), workers):
            if time.time() - start > minutes * 60:
                print(f"  stopped after {minutes} minutes ({done} of {len(order)} sets read; the next run carries on from there)")
                break
            batch = order[i:i + workers]
            futures = [(e["id"], pool.submit(read_set, e["id"])) for e in batch]
            for eid, fut in futures:
                try:
                    sid_of, answers = fut.result()
                    add(sid_of, answers)
                    if seen is not None:
                        seen.update(sid_of.values())
                except Exception as err:   # one set going wrong is fine
                    failed += 1
                    print(f"  note: CardTrader set {eid} could not be read ({err})")
                done += 1
                last = eid
    if other_cur:
        print(f"  note: prices in {', '.join(sorted(other_cur))} were left out (no rate to euros)")
    top = sorted(skipped.items(), key=lambda kv: -kv[1])[:8]
    print(f"  {n} offers from sellers in Europe ({done} of {len(expansions)} sets{f', {failed} failed' if failed else ''}); "
          f"left out, by seller country: {dict(top)}")
    if not n:
        raise ValueError("no CardTrader offers found")
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), (0 if done >= len(order) else last)


def shop_offers(args, products, printings=({}, {})):
    """Offers with condition and stock from the shops' public price lists, by
    Scryfall id: ({id: rows}, {id: links}, {shop: as-of time}). Each printing
    keeps its cheapest LISTINGS_PER_FINISH offers per market and finish. Links:
    Card Kingdom's product pages, Mana Pool's card page, ENNDAL GAMES' product
    paths, and TCGplayer's and Cardmarket's product numbers (for the lowest
    listings in the shop prices). `printings` ({(set, number): (id, name)},
    {(set, name): [ids]}) matches ENNDAL's products to Scryfall's printings."""
    rows, links, when = {}, {}, {}
    for shop, read, src in (("cardkingdom", cardkingdom_offers, args.ck_pricelist or CK_PRICELIST),
                            ("manapool", manapool_offers, args.manapool_variants or MANAPOOL_VARIANTS)):
        try:
            when[shop] = read(src, rows, links) or "?"
        except Exception as err:   # the daily update goes on without them
            print(f"  note: {shop}'s offers could not be read ({err}).")
    prev_index = {}
    try:
        prev_index = load_published(args.previous, "index.json") or {}
    except Exception:
        pass
    prev_when = prev_index.get("offers") or {}
    # ENNDAL GAMES: the products read last night (shop_enndal.py), matched to printings here
    if args.enndal:
        try:
            data = shop_enndal.load(args.enndal)
            n, ok, missed = shop_enndal.add_offers(data, printings[0], printings[1], rows, links)
            if not n:
                raise ValueError("no ENNDAL product matched a printing")
            when["enndal"] = data.get("updated") or "?"
            print(f"  ENNDAL GAMES: {n} offers of {ok} products ({missed} products matched no printing), read {when['enndal']}")
            print(f"::notice title=ENNDAL GAMES::{ok} products matched, {missed} not; {n} offers; read {when['enndal']}")
        except Exception as err:
            print(f"  note: ENNDAL GAMES' offers could not be read ({err}); keeping the earlier ones.")
    # (the earlier ones are kept for up to shop_enndal.KEEP_DAYS, so offers stop showing if the nightly reading stops)
    # PullVault: today's singles that shop_pullvault.py matched and checked against their photos
    if args.pullvault:
        try:
            data = shop_pullvault.load(args.pullvault)
            n, held = shop_pullvault.add_offers(data, rows, links)
            when["pullvault"] = data.get("updated") or "?"
            print(f"  PullVault: {n} offers ({held} listings held back or not cards), read {when['pullvault']}")
        except Exception as err:
            print(f"  note: PullVault's offers could not be read ({err}); keeping the earlier ones.")
    run_day = datetime.fromisoformat(args.date).replace(tzinfo=timezone.utc) if args.date else datetime.now(timezone.utc)
    ed_cutoff = (run_day - timedelta(days=shop_enndal.KEEP_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    keep_ed = "enndal" not in when and str(prev_when.get("enndal") or "") >= ed_cutoff
    pv_cutoff = (run_day - timedelta(days=shop_pullvault.KEEP_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    keep_pv = "pullvault" not in when and str(prev_when.get("pullvault") or "") >= pv_cutoff
    token = os.environ.get("CARDTRADER_TOKEN", "").strip()
    resume = 0
    seen = set()
    keep_ct = bool(args.cardtrader or token)
    if keep_ct:
        try:
            when["cardtrader"], resume = cardtrader_offers(args.cardtrader or CARDTRADER_API, token, rows, links, args.cardtrader_minutes,
                                                           int(prev_index.get("ct_resume") or 0), seen)
        except Exception as err:
            print(f"  note: CardTrader's offers could not be read ({err}).")
            resume = int(prev_index.get("ct_resume") or 0)
    # CardTrader's sets not read today, and ENNDAL GAMES and PullVault when
    # their reading is missing, keep the offers published last time
    keep_ct = keep_ct and bool(prev_when.get("cardtrader"))
    kept = {"ct": 0, "ed": 0, "pv": 0}
    try:
        for key in (prev_index.get("shards") or []) if keep_ct or keep_ed or keep_pv else []:
            old = load_published(args.previous, f"q/{key}.json.gz") or {}
            for sid, old_rows in (old.get("l") or {}).items():
                for shop, wanted in (("ct", keep_ct and sid not in seen), ("ed", keep_ed), ("pv", keep_pv)):
                    got = [r for r in old_rows if r and r[0] == shop] if wanted else []
                    if got and not any(r[0] == shop for r in rows.get(sid, [])):
                        rows.setdefault(sid, []).extend(got)
                        if ((old.get("lk") or {}).get(sid) or {}).get(shop):
                            links.setdefault(sid, {})[shop] = old["lk"][sid][shop]
                        kept[shop] += 1
        if kept["ct"]:
            print(f"  kept the earlier CardTrader offers of {kept['ct']} printings from sets not read today")
            when.setdefault("cardtrader", prev_when["cardtrader"])
        if kept["ed"]:
            print(f"  kept the earlier ENNDAL GAMES offers of {kept['ed']} printings")
            when.setdefault("enndal", prev_when["enndal"])
        if kept["pv"]:
            print(f"  kept the earlier PullVault offers of {kept['pv']} printings")
            when.setdefault("pullvault", prev_when["pullvault"])
    except Exception as err:
        print(f"  note: the earlier offers could not be read ({err}).")
    for sid, got in rows.items():
        got.sort(key=lambda r: (OFFER_MARKETS.get(r[0], ""), r[1], r[3], -r[4]))
        kept, per = [], {}
        for r in got:
            key = (OFFER_MARKETS.get(r[0], ""), r[1])
            if per.get(key, 0) < LISTINGS_PER_FINISH:
                kept.append(r)
                per[key] = per.get(key, 0) + 1
        rows[sid] = kept
    for sid, (tcg, cm) in products.items():
        pid = tcg[0] or tcg[1]
        if pid:
            links.setdefault(sid, {})["tcg"] = pid
        if cm:
            links.setdefault(sid, {})["cm"] = cm
    return rows, links, when, resume


# ------------------------------------------------------------------ cards
def faces(card):
    return card.get("card_faces") or []


def excluded(card):
    if card.get("layout") in EXCLUDED_LAYOUTS or card.get("set_type") in EXCLUDED_SET_TYPES:
        return True
    if card.get("digital") or "paper" not in (card.get("games") or ["paper"]):
        return True
    return card.get("type_line", "").startswith("Token")


RARITY_ORDER = {"common": 0, "uncommon": 1, "rare": 2, "mythic": 3}


def note_cheapest(cheap, card):
    """Keeps, for each card name, the lowest non-foil price of any paper printing
    (TCGplayer USD and Cardmarket EUR, in cents; a foil price only when a card
    has no non-foil price at all), the card's MTG Arena rarity (c/u/r/m, the
    lowest among its Arena printings) and its lowest MTGO price (Scryfall's
    `tix`, from Cardhoarder, in hundredths of a ticket; any MTGO printing,
    MTGO-only ones too). Deck pages add these up."""
    if card.get("layout") in EXCLUDED_LAYOUTS or card.get("type_line", "").startswith("Token"):
        return
    name = card.get("name")
    if not name:
        return
    row = cheap.get(name)
    if row is None:
        row = cheap[name] = [None, None, "", None, None, None]   # usd, eur, arena; foil-only usd, eur; tix
    if "arena" in (card.get("games") or []) and card.get("rarity") in RARITY_ORDER:
        r = card["rarity"][0]
        if not row[2] or RARITY_ORDER[card["rarity"]] < "curm".index(row[2]):
            row[2] = r
    if "mtgo" in (card.get("games") or []):
        tix = cents((card.get("prices") or {}).get("tix"))
        if tix is not None and tix > 0:
            row[5] = tix if row[5] is None else min(row[5], tix)
    if excluded(card):
        return
    p = card.get("prices") or {}
    for i, key, foil_keys in ((0, "usd", ("usd_foil", "usd_etched")), (1, "eur", ("eur_foil",))):
        v = cents(p.get(key))
        if v is not None and v > 0:
            row[i] = v if row[i] is None else min(row[i], v)
        for fk in foil_keys:
            f = cents(p.get(fk))
            if f is not None and f > 0:
                row[3 + i] = f if row[3 + i] is None else min(row[3 + i], f)


def finish_cheapest(cheap):
    for row in cheap.values():
        if row[0] is None:
            row[0] = row[3]
        if row[1] is None:
            row[1] = row[4]
        row[3] = row[5]   # tix
        del row[4:]


def cents(value):
    try:
        return int(round(float(value) * 100)) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def colors_of(card):
    cols = set(card.get("colors") or [])
    for f in faces(card):
        cols.update(f.get("colors") or [])
    return "".join(c for c in COLOR_ORDER if c in cols)


def small_image(card):
    if card.get("image_uris"):
        return card["image_uris"].get("small", "")
    for f in faces(card):
        if f.get("image_uris"):
            return f["image_uris"].get("small", "")
    return ""


# ------------------------------------------------------------------ main work
def build(args):
    today = args.date or datetime.now(timezone.utc).date().isoformat()
    dates, shards, index = read_previous(args.previous, args.allow_fresh)

    # a young history (or one from before the euro prices): fill in the days
    # before it from MTGJSON, once
    old_format = index.get("series", 2) < SERIES and bool(dates)
    tried = "" if old_format else index.get("backfill_tried", "")
    sources = [SCRYFALL_SOURCE if x.startswith("Scryfall") else x for x in (index.get("sources") or [SCRYFALL_SOURCE])]
    wait_over = not tried or (date.fromisoformat(today) - date.fromisoformat(tried)).days >= BACKFILL_RETRY_DAYS
    want_backfill = args.backfill == "always" or (
        args.backfill == "auto" and (len(dates) < BACKFILL_IF_FEWER or old_format) and wait_over)
    want_quotes = args.quotes != "never"
    ids, ids_date = None, ""
    if want_backfill or want_quotes:
        try:
            ids, ids_date = scryfall_ids(args.mtgjson_ids or MTGJSON_BASE + "AllIdentifiers.json.xz", args.previous, today)
        except Exception as err:
            print(f"  note: MTGJSON's card ids could not be read ({err}); carrying on without MTGJSON.")
    if want_backfill:
        tried = today
        try:
            if not ids:
                raise ValueError("no card id list")
            dates, shards = backfill(dates, shards, today, args.mtgjson_prices or MTGJSON_BASE + "AllPrices.json.xz", ids)
            mtgjson = "MTGJSON (TCGplayer and Cardmarket prices; earlier days)"
            sources = [x for x in sources if not x.startswith("MTGJSON (TCGplayer prices")]
            if mtgjson not in sources:
                sources.append(mtgjson)
        except Exception as err:   # the daily update must go on without it
            print(f"  note: past prices could not be added from MTGJSON ({err}); carrying on without them.")
    quote_data = None
    if want_quotes:
        try:
            if not ids:
                raise ValueError("no card id list")
            quote_data = shop_prices(args.mtgjson_today or MTGJSON_BASE + "AllPricesToday.json.xz", ids) + (today,)
            if QUOTES_SOURCE not in sources:
                sources.append(QUOTES_SOURCE)
        except Exception as err:
            print(f"  note: today's shop prices could not be read from MTGJSON ({err}).")
            try:
                quote_data = previous_quotes(args.previous, index)
                if quote_data:
                    print(f"  keeping the shop prices of {quote_data[2]}")
            except Exception as err2:
                print(f"  note: the earlier shop prices could not be read either ({err2}).")

    if today in dates:
        idx = dates.index(today)
        print(f"{today} is already in the history - replacing that day's prices.")
    else:
        if dates and today < dates[-1]:
            raise SystemExit(f"Today ({today}) is earlier than the newest stored date ({dates[-1]}).")
        dates.append(today)
        idx = len(dates) - 1
        for shard in shards.values():
            for series in shard.values():
                for s in series:
                    s.append(None)
    n_dates = len(dates)
    for shard in shards.values():   # every series exactly as long as the date list
        for series in shard.values():
            for s in series:
                del s[n_dates:]
                s.extend([None] * (n_dates - len(s)))

    source = args.bulk or bulk_url()
    print("Reading", source)
    info = {}
    products = {}   # Scryfall id -> ([TCGplayer product, etched product], Cardmarket product)
    cheap = {}      # card name -> [cheapest USD, cheapest EUR, MTG Arena rarity, cheapest MTGO tix] (for deck prices)
    by_number, by_name = {}, {}   # for matching ENNDAL GAMES' products: (set, number) and (set, name) -> printing
    seen = priced = 0
    for card in iter_cards(source):
        seen += 1
        if card.get("lang", "en") != "en":
            continue
        note_cheapest(cheap, card)
        number_key = (card.get("set", ""), shop_enndal.number_key(card.get("collector_number", "")))
        first_name = card.get("name", "").split(" // ")[0]
        by_number[number_key] = (card["id"], first_name)
        by_name.setdefault((card.get("set", ""), first_name.lower()), []).append(card["id"])
        if card.get("tcgplayer_id") or card.get("tcgplayer_etched_id") or card.get("cardmarket_id"):
            products[card["id"]] = ([card.get("tcgplayer_id"), card.get("tcgplayer_etched_id")], card.get("cardmarket_id"))
        p = card.get("prices") or {}
        usd = cents(p.get("usd"))
        foil = cents(p.get("usd_foil"))
        if foil is None:
            foil = cents(p.get("usd_etched"))
        eur, eur_foil = cents(p.get("eur")), cents(p.get("eur_foil"))
        if usd is None and foil is None and eur is None and eur_foil is None:
            continue
        cid = card["id"]
        shard = shards.setdefault(cid[:2], {})
        series = shard.get(cid)
        if series is None:
            series = shard[cid] = [[None] * n_dates for _ in range(SERIES)]
        series[0][idx], series[1][idx], series[2][idx], series[3][idx] = usd, foil, eur, eur_foil
        priced += 1
        if not excluded(card):
            info[cid] = {
                "o": card.get("oracle_id") or (faces(card)[0].get("oracle_id") if faces(card) else ""),
                "n": card.get("name", ""),
                "s": card.get("set", ""),
                "sn": card.get("set_name", ""),
                "c": card.get("collector_number", ""),
                "r": card.get("rarity", ""),
                "col": colors_of(card),
                "img": small_image(card),
            }
    print(f"{seen} printings read, {priced} with a price")
    if priced < args.min_cards:
        raise SystemExit(f"Only {priced} priced printings - Scryfall's export looks incomplete, so nothing was changed.")

    # older than DAILY_DAYS: keep Mondays only
    cutoff = (date.fromisoformat(today) - timedelta(days=DAILY_DAYS)).isoformat()
    keep = [i for i, d in enumerate(dates) if d >= cutoff or date.fromisoformat(d).weekday() == 0]
    if len(keep) < len(dates):
        dates = [dates[i] for i in keep]
        for shard in shards.values():
            for cid, series in shard.items():
                shard[cid] = [[s[i] for i in keep] for s in series]
        idx = len(dates) - 1
    # printings with no price on any stored date are dropped
    for shard in shards.values():
        for cid in [cid for cid, series in shard.items() if all(v is None for s in series for v in s)]:
            del shard[cid]

    if args.lows != "never" and products:
        quote_data = add_lows(quote_data, today, products, args)
        if quote_data and any(k in quote_data[1] for k in ("tcgplayer_low", "cardmarket_low")) and LOWS_SOURCE not in sources:
            sources.append(LOWS_SOURCE)
    offers = None
    if args.offers != "never":
        offers = shop_offers(args, products, (by_number, by_name))
        if set(offers[2]) & {"cardkingdom", "manapool"} and OFFERS_SOURCE not in sources:
            sources.append(OFFERS_SOURCE)
        if "cardtrader" in offers[2] and CARDTRADER_SOURCE not in sources:
            sources.append(CARDTRADER_SOURCE)
        if "enndal" in offers[2] and ENNDAL_SOURCE not in sources:
            sources.append(ENNDAL_SOURCE)
        if "pullvault" in offers[2] and PULLVAULT_SOURCE not in sources:
            sources.append(PULLVAULT_SOURCE)
    check = source_check(dates, idx, shards, info, quote_data, ids)
    if offers:
        check["offers"] = {"as_of": offers[2], "printings": len(offers[0]), "rows": sum(len(r) for r in offers[0].values()),
                           "cardtrader_printings": sum(1 for r in offers[0].values() if any(x[0] == "ct" for x in r)),
                           "enndal_printings": sum(1 for r in offers[0].values() if any(x[0] == "ed" for x in r)),
                           "pullvault_printings": sum(1 for r in offers[0].values() if any(x[0] == "pv" for x in r)), "ct_resume": offers[3]}
    mover_data = movers(today, dates, shards, info, (quote_data or ({},))[0])
    check["movers_top"] = {w: {m: {d: [f"{e['n']} ({e['s']}) {e['then']}->{e['now']} {e['pct']}%" for e in blk[m][d][:5]]
                                   for d in ("up", "down")} for m in MARKETS} for w, blk in mover_data.items()}
    write_output(args.out, today, dates, shards, mover_data, sources, tried, quote_data, ids, ids_date, offers)
    finish_cheapest(cheap)
    cheap_rows = {n: v for n, v in cheap.items() if v[0] is not None or v[1] is not None or v[2] or v[3] is not None}
    size = write_gz(os.path.join(args.out, "cheap.json.gz"), {"version": 1, "date": today, "fields": ["usd", "eur", "arena", "tix"], "cards": cheap_rows})
    check["cheapest"] = {"cards": len(cheap_rows), "bytes": size,
                         "sample": {n: cheap_rows.get(n) for n in ("Lightning Bolt", "Island", "Sleight of Hand", "Steam Vents")}}
    print(f"Wrote the cheapest printing's price of {len(cheap_rows)} cards ({size / 1e3:.0f} kB)")
    with open(os.path.join(args.out, "check.json"), "w", encoding="utf-8") as fh:
        json.dump(check, fh, ensure_ascii=False, indent=1)


def steady(values, lo, hi):
    """The middle value of values[lo..hi] (inclusive; gaps skipped)."""
    got = sorted(v for v in values[max(lo, 0):hi + 1] if v is not None)
    return got[len(got) // 2] if got else None


def movers(today, dates, shards, info, quotes=None):
    idx = len(dates) - 1
    t = date.fromisoformat(today)
    result = {}
    for days in WINDOWS:
        target = t - timedelta(days=days)
        slack = timedelta(days=days // 2 + 2)
        j = None
        for k in range(idx - 1, -1, -1):
            d = date.fromisoformat(dates[k])
            if d <= target:
                if d >= target - slack:
                    j = k
                break
        if j is None:
            continue
        block = {"from": dates[j]}
        for market, (a, b) in MARKETS.items():
            shop = "cardmarket" if market == "eur" else "tcgplayer"
            best = {}   # oracle id -> entry (one printing per card: the biggest move)
            for shard in shards.values():
                for cid, series in shard.items():
                    meta = info.get(cid)
                    if not meta:
                        continue
                    normal, foil = series[a], series[b]
                    values, is_foil = (normal, 0) if normal[idx] is not None else (foil, 1)
                    now, then = values[idx], values[j]
                    if now is None or then is None or then <= 0:
                        continue
                    if min(now, then) < MIN_PRICE_CENTS or abs(now - then) < MIN_CHANGE_CENTS:
                        continue
                    # one day's odd price (thinly traded cards jump around) shouldn't
                    # make a mover: the move must also show in the middle of a few
                    # days at each end
                    s_now = now if days == 1 else steady(values, idx - 2, idx)
                    s_then = steady(values, j - 2, j) if days == 1 else steady(values, j - 1, j + 1)
                    if (s_now - s_then) * (now - then) <= 0 or abs(s_now - s_then) < MIN_CHANGE_CENTS \
                            or min(s_now, s_then) < MIN_PRICE_CENTS:
                        continue
                    # today's price is doubtful when MTGJSON's figure for the same shop
                    # disagrees a lot (the older days of a new history come from MTGJSON)
                    q = ((quotes or {}).get(cid) or {}).get(shop) or []
                    other = q[is_foil] if len(q) > is_foil else None
                    if other and not (0.8 <= other / now <= 1.25):
                        continue
                    pct = (now - then) / then * 100
                    key = meta["o"] or cid
                    old = best.get(key)
                    if old is None or abs(pct) > abs(old["pct"]):
                        best[key] = dict(meta, id=cid, f=is_foil, now=now, then=then, pct=round(pct, 1))
            entries = list(best.values())
            up = sorted((e for e in entries if e["pct"] > 0), key=lambda e: (-e["pct"], -e["now"]))[:MOVERS_PER_LIST]
            down = sorted((e for e in entries if e["pct"] < 0), key=lambda e: (e["pct"], -e["then"]))[:MOVERS_PER_LIST]
            block[market] = {"up": up, "down": down}
        result[str(days)] = block
    return result


def source_check(dates, idx, shards, info, quote_data, ids):
    """How well today's Scryfall prices agree with MTGJSON's (today's shop
    prices and the previous day in the history): written to check.json."""
    quotes = (quote_data or ({}, {}, ""))[0]
    per_sid = {}
    for uuid, sid in (ids or {}).items():
        per_sid.setdefault(sid, []).append(uuid)
    out = {"date": dates[idx] if dates else "", "prev": dates[idx - 1] if idx > 0 else ""}
    for label, series_i, shop, qi in (("usd", 0, "tcgplayer", 0), ("eur", 2, "cardmarket", 0)):
        vs_today, vs_prev = [], []
        for shard in shards.values():
            for cid, series in shard.items():
                now = series[series_i][idx]
                if not now or now < 100:
                    continue
                q = ((quotes.get(cid) or {}).get(shop) or [])
                if len(q) > qi and q[qi]:
                    vs_today.append((q[qi] / now, cid, now, q[qi]))
                if idx > 0 and series[series_i][idx - 1]:
                    vs_prev.append((series[series_i][idx - 1] / now, cid, now, series[series_i][idx - 1]))
        def summary(rows):
            if not rows:
                return {"n": 0}
            r = sorted(x[0] for x in rows)
            close = sum(1 for x in r if 0.85 <= x <= 1.15) / len(r)
            worst = sorted(rows, key=lambda x: -abs(math.log(x[0])))[:15]
            return {"n": len(r), "median_ratio": round(r[len(r) // 2], 3), "within_15pct": round(close, 3),
                    "worst": [{"id": c, "name": (info.get(c) or {}).get("n", ""), "set": (info.get(c) or {}).get("s", ""),
                               "num": (info.get(c) or {}).get("c", ""), "scryfall": now, "mtgjson": other,
                               "mtgjson_uuids": len(per_sid.get(c, []))} for _, c, now, other in worst]}
        lows = []
        low_key = "tcgplayer_low" if label == "usd" else "cardmarket_low"
        for shard in shards.values():
            for cid, series in shard.items():
                now = series[series_i][idx]
                low = ((quotes.get(cid) or {}).get(low_key) or [None])[0]
                if now and now >= 100 and low:
                    lows.append((low / now, cid, now, low))
        r = sorted(x[0] for x in lows)
        out[label] = {"mtgjson_today": summary(vs_today), "previous_day": summary(vs_prev),
                      "lowest_listing": {"n": len(r), "median_low_to_market": round(r[len(r) // 2], 3) if r else None,
                                         "share_above_market": round(sum(1 for x in r if x > 1.05) / len(r), 3) if r else None,
                                         "examples": [f"{(info.get(c) or {}).get('n', c)} ({(info.get(c) or {}).get('s', '')}) market {now} low {low}"
                                                      for _, c, now, low in sorted(lows, key=lambda x: -x[2])[:8]]}}
    return out


def write_gz(path, obj):
    payload = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    with open(path, "wb") as fh:
        with gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
            gz.write(payload)
    return os.path.getsize(path)


def write_output(out, today, dates, shards, mover_data, sources=None, backfill_tried="", quote_data=None, ids=None, ids_date="", offers=None):
    os.makedirs(os.path.join(out, "h"), exist_ok=True)
    total = 0
    keys = sorted(set(f"{i:02x}" for i in range(256)) | set(shards))   # Scryfall ids are hex, so normally just the 256
    for key in keys:
        payload = json.dumps({"dates": dates, "p": shards.get(key, {})}, separators=(",", ":")).encode("utf-8")
        with open(os.path.join(out, "h", f"{key}.json.gz"), "wb") as fh:
            with gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
                gz.write(payload)
        total += os.path.getsize(os.path.join(out, "h", f"{key}.json.gz"))
    quotes_date, providers = "", {}
    rows, links, offers_when, ct_resume = offers or ({}, {}, {}, 0)
    if quote_data or rows:
        quotes, providers, quotes_date = quote_data or ({}, {}, today)
        os.makedirs(os.path.join(out, "q"), exist_ok=True)
        by_shard = {}
        for part, data in (("p", quotes), ("l", rows), ("lk", links if rows or quote_data else {})):
            for sid, value in data.items():
                by_shard.setdefault(sid[:2], {}).setdefault(part, {})[sid] = value
        def shard_file(key):
            got = by_shard.get(key, {})
            obj = {"date": quotes_date, "p": got.get("p", {})}
            if rows:
                obj["l"] = got.get("l", {})
            if "lk" in got:
                obj["lk"] = got["lk"]
            return obj
        qsize = sum(write_gz(os.path.join(out, "q", f"{key}.json.gz"), shard_file(key)) for key in keys)
        print(f"Wrote shop prices of {quotes_date} for {len(quotes)} printings and offers for {len(rows)} ({qsize / 1e6:.1f} MB)")
    if ids:
        write_gz(os.path.join(out, "ids.json.gz"), {"date": ids_date, "map": ids})
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(os.path.join(out, "index.json"), "w", encoding="utf-8") as fh:
        meta = {"version": FORMAT_VERSION, "updated": stamp, "today": today, "dates": dates, "shards": keys,
                "series": SERIES, "series_names": SERIES_NAMES,
                "source": "Scryfall (TCGplayer market prices, USD; Cardmarket, EUR)",
                "sources": sources or [SCRYFALL_SOURCE]}
        if quotes_date:
            meta["quotes_date"] = quotes_date
            meta["providers"] = providers
        if rows:
            meta["offers"] = offers_when
        if ct_resume:
            meta["ct_resume"] = ct_resume
        if backfill_tried:
            meta["backfill_tried"] = backfill_tried
        json.dump(meta, fh, separators=(",", ":"))
    with open(os.path.join(out, "movers.json"), "w", encoding="utf-8") as fh:
        json.dump({"version": FORMAT_VERSION, "updated": stamp, "today": today, "windows": mover_data},
                  fh, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(out, ".nojekyll"), "w") as fh:
        fh.write("")
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as fh:
        fh.write("<!doctype html><meta charset='utf-8'><title>悪知恵 price data</title>"
                 "<p>Price history data for 悪知恵. Prices: TCGplayer and Cardmarket via "
                 "<a href='https://scryfall.com'>Scryfall</a>; earlier days and shop prices via "
                 "<a href='https://mtgjson.com'>MTGJSON</a>; lowest listings via "
                 "<a href='https://tcgcsv.com'>TCGCSV</a> and Cardmarket's price guide; offers with stock via "
                 "Card Kingdom's and Mana Pool's public price lists, and CardTrader; Japanese shop stock from "
                 "ENNDAL GAMES, with the shop's permission.</p>")
    print(f"Wrote {len(dates)} dates, {sum(len(s) for s in shards.values())} printings, "
          f"{total / 1e6:.1f} MB of history; movers for {', '.join(mover_data) or 'no windows yet'} day(s)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="folder to write the published files into")
    ap.add_argument("--previous", default="", help="URL or folder of the currently published data")
    ap.add_argument("--bulk", default="", help="a saved Scryfall export to read instead of downloading")
    ap.add_argument("--date", default="", help="the date to store prices under (YYYY-MM-DD, default today UTC)")
    ap.add_argument("--allow-fresh", action="store_true", help="start a new history if none is published yet (first run)")
    ap.add_argument("--min-cards", type=int, default=20000, help="refuse to save if fewer priced printings than this")
    ap.add_argument("--backfill", choices=("auto", "always", "never"), default="auto",
                    help="fill in past prices from MTGJSON: auto = while the history is under 60 days")
    ap.add_argument("--mtgjson-prices", default="", help="a saved AllPrices.json(.xz/.gz) to use instead of downloading")
    ap.add_argument("--mtgjson-ids", default="", help="a saved AllIdentifiers.json(.xz/.gz) to use instead of downloading")
    ap.add_argument("--mtgjson-today", default="", help="a saved AllPricesToday.json(.xz/.gz) to use instead of downloading")
    ap.add_argument("--quotes", choices=("auto", "never"), default="auto", help="today's prices at several shops, from MTGJSON")
    ap.add_argument("--lows", choices=("auto", "never"), default="auto", help="lowest listings from TCGCSV and Cardmarket's price guide")
    ap.add_argument("--tcgcsv", default="", help="a folder laid out like tcgcsv.com to use instead of downloading")
    ap.add_argument("--cardmarket-guide", default="", help="a saved Cardmarket price guide to use instead of downloading")
    ap.add_argument("--offers", choices=("auto", "never"), default="auto", help="offers by condition with stock (Card Kingdom, Mana Pool)")
    ap.add_argument("--ck-pricelist", default="", help="a saved Card Kingdom price list to use instead of downloading")
    ap.add_argument("--manapool-variants", default="", help="a saved Mana Pool variant price list to use instead of downloading")
    ap.add_argument("--cardtrader", default="", help="a folder of saved CardTrader answers (normally the API, used when CARDTRADER_TOKEN is set)")
    ap.add_argument("--enndal", default="", help="last night's enndal.json.gz from shop_enndal.py (without it, the published ENNDAL offers are kept)")
    ap.add_argument("--pullvault", default="", help="today's pullvault.json.gz from shop_pullvault.py (without it, the published PullVault offers are kept for a few days)")
    ap.add_argument("--cardtrader-minutes", type=float, default=CARDTRADER_MINUTES, help="time allowed for reading CardTrader")
    build(ap.parse_args())


if __name__ == "__main__":
    main()
