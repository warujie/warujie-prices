"""PullVault (pullvault.gg): a US shop's singles, in dollars, for warujie.jp's US tab.

PullVault's owner gave permission on 2026-10-25 (the site owner's word). We still read
gently: once a day, only pages pullvault.gg's robots.txt allows (it disallows /api/, .json
and sort/filter/page links, so we never call those ourselves), PAGE_GAP seconds between
pages, with a User-Agent naming warujie.jp and our contact address, and every listing links
back to its product page. Stop at once if PullVault asks.

The shop is a JavaScript page on top of Shopify: opening https://pullvault.gg/singles makes
the visitor's browser ask Shopify for the shop's product list (every product, 100 at a time).
So the reader opens that one page in a headless browser and keeps the product list the page
itself received (`read_shop()`); it sends no requests of its own to the shop.

Titles look like "The Tenth Doctor (Serial) - Universes Beyond: Doctor Who (WHO)" or
"Cloud, Midgar Mercenary - Pro Tour Promos (PTP) (Japanese)": the card's name, the kind of
printing in brackets, the set and its code, the language (`parse_title()`). A title alone is
not trusted. Each listing's own photos are compared with Scryfall's picture of every printing
of that card (`picture_scores()`): the artwork is found in the photo (SIFT features, a
perspective fit) and the photo, straightened, is compared with each printing's whole card, so
a borderless or showcase copy isn't taken for the plain one. A listing goes on the site only
when a printing fits both the title and the photos (`choose()`); for a Japanese copy the
photo's text must also look more like the Japanese card than the English one. Everything
else is held back, with the reason, in the run's notes and in the file.

    read_shop(...)       -> the shop's products (the Shopify product list the page loaded)
    listings(...)        -> the in-stock single cards among them, by variant
    match_listing(...)   -> the printing a listing is, or why it was held back
    nightly(...)         -> one day's reading and matching (pullvault.json.gz)
    add_offers(...)      -> the matched listings as build_prices.py's offer rows

Run by .github/workflows/update-prices.yml before the price build:
    python3 shop_pullvault.py --out pullvault/pullvault.json.gz
The picture check needs numpy and opencv-python-headless, the page reading Playwright.
"""
import argparse
import difflib
import gzip
import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SHOP = "https://pullvault.gg"
SHOP_PAGES = (SHOP + "/singles",)      # loading this page brings the whole product list
PRODUCT_URL = SHOP + "/product/{}"
CONTACT = "warujie.mtg" + "@" + "gmail.com"
USER_AGENT = f"WarujieShopPrices/1.0 (+https://warujie.jp; {CONTACT})"
PAGE_GAP = 4.0          # seconds between pages (robots.txt asks for 1)
MORE_PAGES = 10         # scrolls for more products when the shop has more than one list's worth
SCRYFALL_SEARCH = "https://api.scryfall.com/cards/search"
SCRYFALL_PAUSE = 0.15   # seconds between Scryfall requests (Scryfall asks for at least 0.1)
PHOTOS_PER_LISTING = 10  # the listing's first photos that are compared
PHOTO_WIDTH = 1000      # the photos are downloaded at this width (Shopify resizes them)
MIN_INLIERS = 25        # a photo shows a printing when this many features fit one perspective ...
MIN_LIKENESS = 0.6      # ... and the straightened photo is at least this like its whole picture
LOOK_MARGIN = 0.06      # printings whose whole-card likeness is within this of the best look alike
SURE_INLIERS, SURE_LIKENESS, SURE_GAP = 100, 0.85, 0.15   # photos that overrule the title (decisive())
KEEP_DAYS = 3           # build_prices.py keeps the published PullVault offers this long if a day's reading fails
FORMAT = 1
LANGS = {"japanese": "JA", "jp": "JA", "japan": "JA", "english": "EN", "en": "EN", "french": "FR", "german": "DE",
         "italian": "IT", "spanish": "ES", "portuguese": "PT", "russian": "RU", "korean": "KO",
         "chinese": "CS", "simplified chinese": "CS", "traditional chinese": "CT", "phyrexian": "PH"}
SCRYFALL_LANGS = {"JA": "ja", "FR": "fr", "DE": "de", "IT": "it", "ES": "es", "PT": "pt", "RU": "ru", "KO": "ko",
                  "CS": "zhs", "CT": "zht", "PH": "ph"}
CONDITIONS = {"mint": "M", "near mint": "NM", "nm": "NM", "lightly played": "LP", "lp": "LP", "excellent": "EX",
              "moderately played": "MP", "mp": "MP", "heavily played": "HP", "hp": "HP", "damaged": "DMG", "dmg": "DMG"}
SEALED_TYPES = {"sealed", "event", "events", "accessories", "supplies"}
# words in a title's brackets and what a printing needs to fit them
VARIANT_WORDS = (
    ("serial", lambda c: "serialized" in c["promo_types"]),
    ("borderless", lambda c: c["border_color"] == "borderless"),
    ("extended", lambda c: "extendedart" in c["frame_effects"]),
    ("showcase", lambda c: "showcase" in c["frame_effects"]),
    ("full art", lambda c: c["full_art"]),
    ("retro", lambda c: c["frame"] in ("1993", "1997")),
    ("old frame", lambda c: c["frame"] in ("1993", "1997")),
    ("etched", lambda c: "etched" in c["finishes"]),
    ("poster", lambda c: "poster" in c["promo_types"]),
    ("surge", lambda c: "surgefoil" in c["promo_types"]),
    ("galaxy", lambda c: "galaxyfoil" in c["promo_types"]),
    ("textured", lambda c: "textured" in c["promo_types"]),
    ("prerelease", lambda c: "prerelease" in c["promo_types"]),
)
FOIL_WORDS = ("foil", "etched", "serial", "surge", "galaxy", "textured")
# treatments a plain title rules out (a serialized copy is always named so)
SPECIAL = lambda c: "serialized" in c["promo_types"]
NOT_A_CARD = "no card of that name on Scryfall"
DEBUG = []              # filled with each listing's scores when --debug is given


# ------------------------------------------------------------------ reading the shop
def read_shop(pages=SHOP_PAGES, log=print):
    """The shop's products: opens each page in a headless browser and keeps the
    product lists Shopify sent it ({product id: product}). Scrolls for more when a
    list says there are more."""
    from playwright.sync_api import sync_playwright   # only the reading needs it
    found, more = {}, [False]

    def on_response(resp):
        if "graphql" not in resp.url or resp.request.method != "POST":
            return
        try:
            body = resp.json()
        except Exception:
            return
        prods = ((body or {}).get("data") or {}).get("products") or {}
        for edge in prods.get("edges") or []:
            node = edge.get("node") or {}
            if node.get("id"):
                found[node["id"]] = node
        if "pageInfo" in prods:
            more[0] = bool((prods.get("pageInfo") or {}).get("hasNextPage"))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=USER_AGENT, viewport={"width": 1280, "height": 1600})
        page.on("response", on_response)
        for i, url in enumerate(pages):
            if i:
                time.sleep(PAGE_GAP)
            page.goto(url, wait_until="networkidle", timeout=90000)
            page.wait_for_timeout(2000)
            for _ in range(MORE_PAGES):
                if not more[0]:
                    break
                before = len(found)
                page.mouse.wheel(0, 20000)
                time.sleep(PAGE_GAP)
                page.wait_for_load_state("networkidle")
                if len(found) == before:
                    log(f"  note: PullVault says it has more products than the {before} read; scrolling found no more.")
                    break
        browser.close()
    log(f"  PullVault: {len(found)} products")
    return found


def _norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", s.replace("’", "'")).strip().lower()


def parse_title(title):
    """A product title as {name, words (the brackets after the name), set_name,
    set_code, lang, foil}. "Name (Kind) - Set Name (CODE) (Language)"."""
    title = re.sub(r"\s+", " ", title or "").strip()
    left, sep, right = title.partition(" - ")
    words, lang, code = [], "", ""

    def peel(text, on_set):
        nonlocal lang, code
        while True:
            m = re.search(r"\s*\(([^()]*)\)\s*$", text)
            if not m:
                return text.strip()
            inner = m.group(1).strip()
            low = _norm(inner)
            if low in LANGS:
                lang = lang or LANGS[low]
            elif on_set and re.fullmatch(r"[A-Z0-9]{2,6}", inner) and not code:
                code = inner.lower()
            else:
                words.append(low)
            text = text[:m.start()]
    name = peel(left, False)
    set_name = peel(right, True) if sep else ""
    joined = " ".join(words)
    foil = any(w in joined for w in FOIL_WORDS) and "non-foil" not in joined and "nonfoil" not in joined
    return {"name": name, "words": words, "set_name": set_name, "set_code": code, "lang": lang or "EN", "foil": foil}


def listings(products):
    """The in-stock single cards among the products, one per available variant:
    {handle, title, cents, qty, cond, lang, foil, photos, ...parse_title()}."""
    out = []
    for prod in products.values():
        if not prod.get("availableForSale") or _norm(prod.get("productType")) in SEALED_TYPES:
            continue
        title = parse_title(prod.get("title") or "")
        if not title["name"] or not title["set_name"]:   # not "Card - Set": a box, an event, a mystery box
            continue
        meta_lang = _norm(((prod.get("language") or {}) or {}).get("value"))
        if meta_lang in LANGS:
            title["lang"] = LANGS[meta_lang]
        meta_cond = CONDITIONS.get(_norm(((prod.get("condition") or {}) or {}).get("value")), "")
        photos = [e["node"]["url"] for e in ((prod.get("images") or {}).get("edges") or []) if (e.get("node") or {}).get("url")]
        for edge in (prod.get("variants") or {}).get("edges") or []:
            v = edge.get("node") or {}
            if not v.get("availableForSale"):
                continue
            try:
                cents = round(float((v.get("price") or {}).get("amount")) * 100)
            except (TypeError, ValueError):
                continue
            if (v.get("price") or {}).get("currencyCode", "USD") != "USD" or cents <= 0:
                continue
            opts = {_norm(o.get("name")): _norm(o.get("value")) for o in v.get("selectedOptions") or []}
            cond = CONDITIONS.get(opts.get("condition", ""), meta_cond)
            finish = opts.get("finish") or opts.get("printing") or opts.get("foil") or ""
            foil = title["foil"] or ("foil" in finish and "non" not in finish) or "etched" in finish
            qty = v.get("quantityAvailable")
            out.append(dict(title, handle=prod.get("handle") or "", title=prod.get("title") or "", cents=cents,
                            qty=qty if isinstance(qty, int) and qty > 0 else 1, cond=cond, foil=foil,
                            photos=photos[:PHOTOS_PER_LISTING]))
    return out


# ------------------------------------------------------------------ the printings (Scryfall)
def http_get(url, tries=3):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as err:
            if err.code == 404 or attempt == tries - 1:
                raise
        except OSError:
            if attempt == tries - 1:
                raise
        time.sleep(2 * (attempt + 1))


def _printing(card):
    face = (card.get("card_faces") or [{}])[0]
    pic = (card.get("image_uris") or face.get("image_uris") or {}).get("large", "")
    return {"id": card["id"], "name": card.get("name", ""), "set": card.get("set", ""), "set_name": card.get("set_name", ""),
            "number": card.get("collector_number", ""), "lang": card.get("lang", "en"),
            "promo_types": card.get("promo_types") or [], "frame_effects": card.get("frame_effects") or [],
            "border_color": card.get("border_color", ""), "frame": card.get("frame", ""), "full_art": bool(card.get("full_art")),
            "finishes": card.get("finishes") or [], "illustration": card.get("illustration_id") or face.get("illustration_id") or "",
            "picture": pic if pic and "/back/" not in pic and card.get("image_status") != "placeholder" else ""}


def printings(name, lang="en", get=http_get, sleep=time.sleep):
    """Every printing of the card with this name from Scryfall's search: in
    English where there is one ("en"), or only those in `lang`."""
    q = f'!"{name}" unique:prints include:extras' + (f" lang:{lang}" if lang != "en" else "")
    url = SCRYFALL_SEARCH + "?" + urllib.parse.urlencode({"q": q, "order": "released"})
    out = []
    while url:
        sleep(SCRYFALL_PAUSE)
        try:
            page = json.loads(get(url))
        except urllib.error.HTTPError as err:
            if err.code == 404:   # no such card (or none in that language)
                return out
            raise
        # the plain search gives each printing once, in English where it was printed in English
        out += [_printing(c) for c in page.get("data") or [] if lang == "en" or c.get("lang") == lang]
        url = page.get("next_page") if page.get("has_more") else None
    return out


def title_fits(listing, cands):
    """The printings the title allows: its set (by code, else by name) and the
    words in its brackets. A plain title rules out serialized copies."""
    code, set_name = listing["set_code"], _norm(listing["set_name"])
    in_set = [c for c in cands if code and c["set"] == code]
    if not in_set and set_name:
        in_set = [c for c in cands if _norm(c["set_name"]) == set_name]
    if not in_set and set_name:
        best = max((difflib.SequenceMatcher(None, set_name, _norm(c["set_name"])).ratio() for c in cands), default=0)
        if best >= 0.75:
            in_set = [c for c in cands if difflib.SequenceMatcher(None, set_name, _norm(c["set_name"])).ratio() >= best - 0.02]
    joined = " ".join(listing["words"])
    fit = in_set
    for word, test in VARIANT_WORDS:
        if word in joined:
            fit = [c for c in fit if test(c)]
    if "serial" not in joined:
        fit = [c for c in fit if not SPECIAL(c)]
    if listing["foil"]:
        fit = [c for c in fit if any(f in c["finishes"] for f in ("foil", "etched"))]
    elif fit and any("nonfoil" in c["finishes"] for c in fit):
        fit = [c for c in fit if "nonfoil" in c["finishes"]]
    return fit


# ------------------------------------------------------------------ the picture check
CARD_W, CARD_H = 488, 680    # printings' pictures are compared at this size (Scryfall's "normal")


def _cv():
    import cv2
    import numpy as np
    return cv2, np


def decode(data, width=None):
    cv2, np = _cv()
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return None
    if width and img.shape[1] > width:
        img = cv2.resize(img, (width, round(img.shape[0] * width / img.shape[1])), interpolation=cv2.INTER_AREA)
    return img


class Features:
    """SIFT features of a picture (grey, light evened out)."""
    _sift = None

    def __init__(self, img):
        cv2, _ = _cv()
        if Features._sift is None:
            Features._sift = cv2.SIFT_create(nfeatures=4000)
        grey = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
        self.img, self.grey = img, grey
        self.kp, self.desc = Features._sift.detectAndCompute(grey, None)


def _likeness(a, b):
    """How alike two straightened cards look (0-1): the correlation of their edge
    pictures, which follows frames, borders and text boxes more than colours."""
    cv2, np = _cv()

    def edges(img):
        g = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (3, 3), 0)
        e = cv2.magnitude(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))
        e = cv2.GaussianBlur(e, (9, 9), 0)
        return (e - e.mean()) / (e.std() + 1e-6)
    ea, eb = edges(a), edges(b)
    return float((ea * eb).mean())


def match_photo(photo, card):
    """How well a photo (Features) shows a printing's picture (Features):
    (inliers, likeness, straightened photo or None)."""
    cv2, np = _cv()
    if photo.desc is None or card.desc is None or len(photo.kp) < 8 or len(card.kp) < 8:
        return 0, 0.0, None
    pairs = cv2.BFMatcher(cv2.NORM_L2).knnMatch(card.desc, photo.desc, k=2)
    good = [m for m, *rest in pairs if rest and m.distance < 0.75 * rest[0].distance]
    if len(good) < 8:
        return 0, 0.0, None
    src = np.float32([card.kp[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst = np.float32([photo.kp[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 6.0)
    if H is None:
        return 0, 0.0, None
    inliers = int(mask.sum())
    # the card's outline in the photo must be a sensible, convex shape of a fair size
    h, w = card.grey.shape
    quad = cv2.perspectiveTransform(np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2), H).reshape(4, 2)
    area = cv2.contourArea(quad)
    ph, pw = photo.grey.shape
    if not cv2.isContourConvex(quad.astype(np.float32)) or area < 0.02 * pw * ph or area > 4 * pw * ph:
        return 0, 0.0, None
    flat = cv2.warpPerspective(photo.img, np.linalg.inv(H), (w, h))
    return inliers, _likeness(flat, card.img), flat


def text_likeness(flat, img):
    """Likeness of the lower half (type line and rules text) and the name bar."""
    h = img.shape[0]
    return (_likeness(flat[int(h * 0.55):int(h * 0.95)], img[int(h * 0.55):int(h * 0.95)])
            + _likeness(flat[int(h * 0.03):int(h * 0.11)], img[int(h * 0.03):int(h * 0.11)])) / 2


def picture_scores(photos, cands, picture):
    """For each printing (by id): the best (inliers, likeness, photo number,
    straightened photo) over the listing's photos. `photos`: [Features];
    `picture(url)`: a printing's picture as Features (or None)."""
    scores = {}
    for c in cands:
        feats = picture(c["picture"]) if c["picture"] else None
        best = (0, 0.0, -1, None)
        for i, ph in enumerate(photos):
            if feats is None:
                break
            inl, like, flat = match_photo(ph, feats)
            if inl >= MIN_INLIERS and (best[0] < MIN_INLIERS or like > best[1]):
                best = (inl, like, i, flat)
            elif best[0] < MIN_INLIERS and inl > best[0]:
                best = (inl, like, i, flat)
        scores[c["id"]] = best
    return scores


def choose(listing, cands, fit, scores):
    """(printing, reason, note): the printing (a cands entry) the photos and
    the title agree on; or, when they disagree, the one the photos show if they
    show it beyond doubt (`decisive()`), with a note; otherwise (None, reason)."""
    shown = [c for c in cands if scores.get(c["id"], (0,))[0] >= MIN_INLIERS and scores[c["id"]][1] >= MIN_LIKENESS]
    if not shown:
        return None, "the photos don't clearly show any printing of this card", ""
    top = max(scores[c["id"]][1] for c in shown)
    looks = [c for c in shown if scores[c["id"]][1] >= top - LOOK_MARGIN]
    # printings whose picture is the same artwork and frame as a top one look alike too
    keys = {(c["illustration"], c["border_color"], c["frame"], tuple(sorted(c["frame_effects"])), c["full_art"]) for c in looks}
    looks += [c for c in cands if c not in looks and not c["picture"]
              and (c["illustration"], c["border_color"], c["frame"], tuple(sorted(c["frame_effects"])), c["full_art"]) in keys]
    both = [c for c in fit if c in looks]
    if not both:
        best = max(looks, key=lambda c: scores[c["id"]][1])
        said = (f"the title fits {', '.join(c['set'].upper() + ' #' + c['number'] for c in fit[:4])}" if fit
                else "no printing fits the title")
        if decisive(listing, best, looks, cands, scores):
            return best, "", f"{said}, but the photos clearly show {best['set'].upper()} #{best['number']}"
        return None, f"the photos look like {best['set'].upper()} #{best['number']}, but {said}", ""
    if len({(c["set"], c["number"]) for c in both}) > 1:
        return None, "several printings fit the title and the photos: " + ", ".join(
            c["set"].upper() + " #" + c["number"] for c in both[:4]), ""
    return both[0], "", ""


def decisive(listing, best, looks, cands, scores):
    """The photos show `best` beyond doubt: many features fit, the straightened
    photo is very like its picture and clearly less like every other look, only
    one printing has that look, and its language is the listing's."""
    inl, like = scores[best["id"]][:2]
    others = [scores[c["id"]][1] for c in cands if c not in looks and scores[c["id"]][0] >= MIN_INLIERS]
    lang_ok = (best["lang"] == "ja") == (listing["lang"] == "JA") and (listing["lang"] in ("EN", "JA"))
    return (inl >= SURE_INLIERS and like >= SURE_LIKENESS and all(o <= like - SURE_GAP for o in others)
            and len({(c["set"], c["number"]) for c in looks}) == 1 and lang_ok)


def match_listing(listing, cands, foreign, photos, picture):
    """{id, set, number, inliers, likeness, photo, text} for a listing, or
    {held: reason}. `cands`: the printings (English where there is one),
    `foreign`: those in the listing's language, or Japanese for an English
    listing (for the language check), `photos`: [Features] of its photos."""
    if not cands:
        return {"held": NOT_A_CARD}
    fit = title_fits(listing, cands)
    if not photos:
        return {"held": "the listing has no photos to check"}
    scores = picture_scores(photos, cands, picture)
    chosen, why, note = choose(listing, cands, fit, scores)
    if not chosen:
        if DEBUG:
            DEBUG.append((listing, cands, scores, None))
        return {"held": why}
    inl, like, i, flat = scores[chosen["id"]]
    out = {"id": chosen["id"], "set": chosen["set"], "number": chosen["number"], "inliers": inl,
           "likeness": round(like, 3), "photo": i}
    if note:
        out["note"] = note
    if "nonfoil" not in chosen["finishes"]:   # a foil-only printing: the copy is foil whatever the title says
        out["foil"] = True
    elif not any(f in chosen["finishes"] for f in ("foil", "etched")):
        out["foil"] = False
    if DEBUG:
        DEBUG.append((listing, cands, scores, chosen))
    # the language: the photo's name bar and text compared with the English and the
    # other-language picture of the same printing (a printing only made in Japanese
    # was compared as it is already)
    same = [f for f in foreign if f["set"] == chosen["set"] and f["number"] == chosen["number"] and f["picture"]]
    if chosen["lang"] == "en" and same and flat is not None:
        en_img, fo = picture(chosen["picture"]), picture(same[0]["picture"])
        if en_img is not None and fo is not None:
            t_en, t_fo = text_likeness(flat, en_img.img), text_likeness(flat, fo.img)
            out["text"] = [round(t_en, 3), round(t_fo, 3)]
            if listing["lang"] != "EN" and t_fo <= t_en:
                return {"held": f"the title says {listing['lang']}, but the photo's text looks like the English card"}
            if listing["lang"] == "EN" and t_fo > t_en:
                return {"held": f"the title says English, but the photo's text looks like the {same[0]['lang']} card"}
    elif listing["lang"] != "EN" and chosen["lang"] == "en" and not same:
        return {"held": f"Scryfall has no {listing['lang']} picture of {chosen['set'].upper()} #{chosen['number']} to check the language"}
    return out


# ------------------------------------------------------------------ one day
def nightly(products, get=http_get, sleep=time.sleep, log=print, now=None):
    """Match every in-stock single to its printing and check its photos."""
    items = listings(products)
    log(f"  PullVault: {len(items)} single cards in stock among {len(products)} products")
    pictures = {}

    def picture(url):
        if url not in pictures:
            try:
                img = decode(get(url))
                pictures[url] = Features(cv_resize(img)) if img is not None else None
            except Exception as err:
                log(f"  note: picture {url} could not be read ({err})")
                pictures[url] = None
            sleep(SCRYFALL_PAUSE)
        return pictures[url]

    by_name, out = {}, []
    for it in items:
        key = (_norm(it["name"]), it["lang"])
        if key not in by_name:
            try:
                en = printings(it["name"], "en", get, sleep)
                # the listing's language, or Japanese for an English listing (the likeliest mix-up)
                fo = printings(it["name"], SCRYFALL_LANGS.get(it["lang"], "ja"), get, sleep)
                by_name[key] = (en, fo)
            except Exception as err:
                log(f"  note: Scryfall could not be asked about {it['name']} ({err})")
                by_name[key] = None
        found = by_name[key]
        if found is None:
            res = {"held": "Scryfall could not be asked"}
        else:
            photos = []
            for url in it["photos"]:
                try:
                    img = decode(get(_sized(url)), PHOTO_WIDTH)
                    if img is not None:
                        photos.append(Features(img))
                except Exception as err:
                    log(f"  note: photo {url} could not be read ({err})")
                sleep(0.5)
            res = match_listing(it, found[0], found[1], photos, picture)
        row = {k: it[k] for k in ("handle", "title", "cents", "qty", "cond", "lang", "foil")}
        row.update(res)
        if res.get("held") == NOT_A_CARD:   # a mystery box or an event night that looks like "Card - Set"
            row = {k: row[k] for k in ("handle", "title", "held")}
        out.append(row)
        if "held" in res:
            log(f"  held back: {it['title']} — {res['held']}")
        else:
            log(f"  matched: {it['title']} -> {res['set'].upper()} #{res['number']} ({res['inliers']} features, likeness {res['likeness']})"
                + (f"; note: {res['note']}" if res.get("note") else ""))
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"version": FORMAT, "updated": stamp, "products": len(products), "listings": out}


def cv_resize(img):
    cv2, _ = _cv()
    return cv2.resize(img, (CARD_W, CARD_H), interpolation=cv2.INTER_AREA)


def _sized(url):
    """A Shopify photo at PHOTO_WIDTH (the shop's CDN resizes on request)."""
    if "cdn.shopify.com" not in url:
        return url
    return url + ("&" if "?" in url else "?") + f"width={PHOTO_WIDTH}"


def load(path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        data = json.load(fh)
    if data.get("version") != FORMAT:
        raise ValueError(f"unknown PullVault data version {data.get('version')}")
    return data


def save(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as fh:
        with gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
            gz.write(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


# ------------------------------------------------------------------ for build_prices.py
def add_offers(data, rows, links):
    """The matched listings as offer rows ["pv", foil, condition ("" = not
    stated), cents, copies, language ("" = English)], and each product's handle
    as the printing's "pv" link. Returns (offers, listings held back)."""
    n = held = 0
    for it in data.get("listings") or []:
        sid = it.get("id")
        if not sid or it.get("held"):
            held += 1
            continue
        lang = it.get("lang") or "EN"
        rows.setdefault(sid, []).append(["pv", 1 if it.get("foil") else 0, it.get("cond") or "", int(it["cents"]),
                                         int(it.get("qty") or 1), "" if lang == "EN" else lang])
        if re.fullmatch(r"[\w-]+", it.get("handle") or "") and "pv" not in links.get(sid, {}):
            links.setdefault(sid, {})["pv"] = it["handle"]
        n += 1
    return n, held


def write_debug(folder):
    """Every listing's scores per printing, and the straightened best photo
    beside each printing's picture, for checking the picture check by eye."""
    cv2, np = _cv()
    os.makedirs(folder, exist_ok=True)
    lines = []
    for n, entry in enumerate(DEBUG[1:]):
        listing, cands, scores, chosen = entry
        lines.append(f"== {listing['title']} -> {chosen['set'] + ' #' + chosen['number'] if chosen else 'held back'}")
        for c in sorted(cands, key=lambda c: (scores[c['id']][0] < MIN_INLIERS, -scores[c['id']][1])):
            inl, like, i, flat = scores[c["id"]]
            lines.append(f"   {c['set']:>6} #{c['number']:<8} {c['lang']} inliers {inl:4d} likeness {like:6.3f} photo {i:2d} "
                         f"{c['border_color']} {c['frame']} {','.join(c['frame_effects'])} {','.join(c['promo_types'])} {','.join(c['finishes'])}")
            if flat is not None and inl >= MIN_INLIERS:
                cv2.imwrite(os.path.join(folder, f"{n:02d}_{c['set']}_{c['number']}.jpg"), cv2.resize(flat, (CARD_W // 2, CARD_H // 2)))
    with open(os.path.join(folder, "scores.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser(description="Read PullVault's in-stock singles and match them to printings.")
    ap.add_argument("--out", required=True, help="where to write pullvault.json.gz")
    ap.add_argument("--products", default="", help="a saved product list (JSON) instead of reading the shop")
    ap.add_argument("--debug", default="", help="a folder for every listing's scores and straightened photos")
    args = ap.parse_args()
    if args.debug:
        DEBUG.append(None)
    if args.products:
        with open(args.products, encoding="utf-8") as fh:
            raw = json.load(fh)
        edges = (((raw.get("data") or {}).get("products") or {}).get("edges")) if isinstance(raw, dict) else None
        products = {e["node"]["id"]: e["node"] for e in edges} if edges else raw
    else:
        products = read_shop()
    if not products:
        raise SystemExit("Nothing was read from PullVault: not saving (the published offers are kept).")
    data = nightly(products)
    save(args.out, data)
    if args.debug:
        write_debug(args.debug)
    ok = sum(1 for x in data["listings"] if not x.get("held"))
    print(f"::notice title=PullVault::{ok} of {len(data['listings'])} singles matched and checked against their photos")
    for x in data["listings"]:
        if x.get("note"):
            print(f"::warning title=PullVault title and photos disagree::{x['title']}: {x['note']}")
        if x.get("held") and x["held"] != NOT_A_CARD:
            print(f"::warning title=PullVault listing held back::{x['title']}: {x['held']}")


if __name__ == "__main__":
    main()
