#!/usr/bin/env python3
"""
build_precons.py - the Commander precon deck lists for warujie.jp.

WHERE THE LISTS COME FROM
-------------------------
MTGJSON (https://mtgjson.com/, MIT licence), which publishes every preconstructed
deck Wizards has sold: DeckList.json names them, and decks/<fileName>.json holds
each one's cards. Only the decks of type "Commander Deck" are kept. The site shows
them on Commander set pages and in the deck price page's precon menu, and prices
them the way it prices a pasted list.

WHAT IS WRITTEN
---------------
precons.json.gz (the shape is in docs/data-formats.md):
    {"version": 1, "generated": "...", "source": {...},
     "sets":  {"blc": {"name": "Bloomburrow Commander", "parent": "blb", "date": "2024-08-02"}, ...},
     "decks": [{"id": "AnimatedArmy_BLC", "name": "Animated Army", "set": "blc", "date": "2024-08-02",
                "commander": [[1, "Bello, Bard of the Brambles"]], "main": [[1, "Sol Ring"], ...]}, ...]}
Newest decks first. Cards are English names, as MTGJSON writes them ("Fire // Ice").

The decks change only when a new Commander set comes out, so the lists are
downloaded again once a week (--max-age); on the other days the published file is
copied over. One deck file is read every DECK_GAP seconds.

USAGE
-----
    python3 build_precons.py --out site --previous prev
Options: --force (rebuild even if the published file is recent), --limit N (first N decks, for a test).
"""

import argparse
import datetime
import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

MTGJSON_BASE = os.environ.get("WARUJIE_MTGJSON_BASE", "https://mtgjson.com/api/v5/")
HEADERS = {"User-Agent": "WarujiePreconBuilder/1.0 (+https://github.com/warujie/warujie-prices)", "Accept": "application/json"}
DECK_TYPES = {"Commander Deck"}
DECK_GAP = 0.5        # seconds between deck files
MAX_AGE_DAYS = 7      # download the lists again when the published file is older than this
MIN_DECKS = 100       # fewer than this means something went wrong: keep the published file
FILE = "precons.json.gz"


def log(msg=""):
    print(msg, flush=True)


def http_json(url, tries=4):
    last = None
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=120) as resp:
                raw = resp.read()
            if raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
            return json.loads(raw)
        except urllib.error.HTTPError as err:
            if err.code == 404:
                raise
            last = err
        except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError) as err:
            last = err
        time.sleep(5 * (attempt + 1))
    raise last


def load_previous(base):
    """The published precons.json.gz (folder or URL) as bytes; None if it isn't there."""
    if not base:
        return None
    if base.startswith(("http://", "https://")):
        try:
            with urllib.request.urlopen(urllib.request.Request(base.rstrip("/") + "/" + FILE, headers=HEADERS), timeout=60) as resp:
                return resp.read()
        except urllib.error.HTTPError:
            return None
    path = os.path.join(base, FILE)
    if not os.path.exists(path):
        return None
    with open(path, "rb") as fh:
        return fh.read()


def card_lines(cards):
    """MTGJSON's cards -> [[count, name], ...]; a card listed twice (foil and not) counts once, added up."""
    counts = {}
    for card in cards or []:
        name = (card.get("name") or "").strip()
        halves = name.split(" // ")
        # "Zndrsplt, Eye of Wisdom // Zndrsplt, Eye of Wisdom"; a meld card ("Bruna, the Fading
        # Light // Brisela, Voice of Nightmares") goes by its own face
        if len(halves) == 2 and (halves[0] == halves[1] or card.get("layout") == "meld"):
            name = card.get("faceName") or halves[0]
        if not name:
            continue
        counts[name] = counts.get(name, 0) + int(card.get("count") or 1)
    return [[n, name] for name, n in counts.items()]


def read_deck(entry, sets):
    data = http_json(MTGJSON_BASE + "decks/" + urllib.parse.quote(entry["fileName"]) + ".json").get("data") or {}
    commander = card_lines(data.get("commander"))
    if not commander:
        return None
    code = (data.get("code") or entry.get("code") or "").lower()
    info = sets.get(code) or {}
    return {
        "id": entry["fileName"],
        "name": data.get("name") or entry.get("name") or "",
        "set": code,
        "date": data.get("releaseDate") or entry.get("releaseDate") or info.get("date") or "",
        "commander": commander,
        "main": card_lines(data.get("mainBoard")),
    }


def main():
    ap = argparse.ArgumentParser(description="Commander precon deck lists for warujie.jp.")
    ap.add_argument("--out", required=True, help="folder to write precons.json.gz in (e.g. site)")
    ap.add_argument("--previous", default="", help="folder or URL of the published data (its precons.json.gz is reused)")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--max-age", type=int, default=MAX_AGE_DAYS)
    ap.add_argument("--limit", type=int, default=0, help=argparse.SUPPRESS)
    args = ap.parse_args()
    today = datetime.datetime.now(datetime.timezone.utc).date()
    os.makedirs(args.out, exist_ok=True)
    dest = os.path.join(args.out, FILE)

    previous = None
    try:
        previous = load_previous(args.previous)
        built = json.loads(gzip.decompress(previous)).get("generated", "")[:10] if previous else ""
    except Exception as err:
        log(f"  note: the published precon file could not be read ({err})")
        previous, built = None, ""
    if previous and built and not args.force:
        try:
            age = (today - datetime.date.fromisoformat(built)).days
        except ValueError:
            age = None
        if age is not None and 0 <= age < args.max_age:
            with open(dest, "wb") as fh:
                fh.write(previous)
            log(f"Precon lists from {built} are recent - published again unchanged.")
            return 0

    def keep_previous(why):
        log(f"  note: precon lists not rebuilt ({why}).")
        if previous:
            with open(dest, "wb") as fh:
                fh.write(previous)
            log("  the previously published file is kept.")
        else:
            log("  no precon file this time.")
        return 0

    try:
        log("Reading MTGJSON's deck and set lists...")
        decklist = http_json(MTGJSON_BASE + "DeckList.json").get("data") or []
        setlist = http_json(MTGJSON_BASE + "SetList.json").get("data") or []
        sets = {s["code"].lower(): {"name": s.get("name") or "", "parent": (s.get("parentCode") or "").lower(), "date": s.get("releaseDate") or ""}
                for s in setlist if s.get("code")}
        types = {}
        for d in decklist:
            types[d.get("type")] = types.get(d.get("type"), 0) + 1
        log("  deck types: " + ", ".join(f"{k} {v}" for k, v in sorted(types.items(), key=lambda kv: -kv[1])))
        wanted = [d for d in decklist if d.get("type") in DECK_TYPES and d.get("fileName")]
        if args.limit:
            wanted = wanted[:args.limit]
        log(f"Reading {len(wanted)} Commander decks, one every {DECK_GAP} s...")
        decks, failed, odd = [], 0, []
        for i, entry in enumerate(wanted):
            if i:
                time.sleep(DECK_GAP)
            try:
                deck = read_deck(entry, sets)
            except Exception as err:
                failed += 1
                log(f"  {entry['fileName']}: {err}")
                continue
            if not deck:
                odd.append(f"{entry['fileName']} (no commander)")
                continue
            total = sum(n for n, _ in deck["commander"]) + sum(n for n, _ in deck["main"])
            if total != 100:
                odd.append(f"{entry['fileName']} ({total} cards)")
            decks.append(deck)
        if odd:
            log(f"  {len(odd)} decks are not 100 cards with a commander: " + ", ".join(odd[:30]))
        if failed > len(wanted) // 5:
            return keep_previous(f"{failed} of {len(wanted)} deck files could not be read")
        if len(decks) < (1 if args.limit else MIN_DECKS):
            return keep_previous(f"only {len(decks)} decks")
        decks.sort(key=lambda d: d["name"])
        decks.sort(key=lambda d: (d["date"], d["set"]), reverse=True)   # newest first, A-Z in a set
        used = {d["set"] for d in decks}
        out = {
            "version": 1,
            "generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": {"name": "MTGJSON", "url": "https://mtgjson.com/", "license": "MIT"},
            "sets": {c: sets[c] for c in sorted(used) if c in sets},
            "decks": decks,
        }
        raw = gzip.compress(json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), 9)
        with open(dest, "wb") as fh:
            fh.write(raw)
        log(f"Wrote {len(decks)} decks from {len(used)} sets ({len(raw) / 1e3:.0f} kB).")
        return 0
    except Exception as err:   # the price update must not fail because of the precons
        return keep_previous(str(err))


if __name__ == "__main__":
    sys.exit(main())
