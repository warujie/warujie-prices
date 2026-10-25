#!/usr/bin/env python3
"""Offline checks of shop_pullvault.py: titles, which products are single cards,
the printings a title allows, the picture check on made-up cards and photos, the
decision between title and photos, and the offer rows build_prices.py gets.

usage: python3 dev/test_pullvault.py      (needs numpy and opencv-python-headless)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import cv2
import shop_pullvault as pv

failed = 0


def check(what, ok, detail=""):
    global failed
    print(("ok   " if ok else "FAIL ") + what + ("" if ok else f"  -> {detail}"))
    failed += 0 if ok else 1


# ---- titles
t = pv.parse_title("The Tenth Doctor (Serial) - Universes Beyond: Doctor Who (WHO)")
check("title: name, kind, set name and code; a serialized copy is foil",
      (t["name"], t["words"], t["set_name"], t["set_code"], t["lang"], t["foil"])
      == ("The Tenth Doctor", ["serial"], "Universes Beyond: Doctor Who", "who", "EN", True), t)
t = pv.parse_title("Cloud, Midgar Mercenary - Pro Tour Promos (PTP) (Japanese)")
check("title: a comma in the name, the language last", (t["name"], t["set_code"], t["lang"], t["foil"]) == ("Cloud, Midgar Mercenary", "ptp", "JA", False), t)
t = pv.parse_title("The One Ring (Borderless Foil Poster) - The Lord of the Rings: Tales of Middle-earth")
check("title: several words in one bracket, no set code", (t["words"], t["set_code"], t["foil"]) == (["borderless foil poster"], "", True), t)
t = pv.parse_title("Lightning Bolt (Non-Foil) - Magic 2010 (M10)")
check("title: non-foil is not foil", t["foil"] is False, t)

# ---- products: only in-stock single cards, one listing per available variant
def product(title, ptype="singles", avail=True, variants=None, lang=None, images=("https://cdn.shopify.com/a.jpg",)):
    return {"id": title, "handle": title.lower().replace(" ", "-"), "title": title, "productType": ptype, "availableForSale": avail,
            "language": {"value": lang} if lang else None, "condition": None,
            "images": {"edges": [{"node": {"url": u}} for u in images]},
            "variants": {"edges": [{"node": v} for v in (variants or [
                {"availableForSale": True, "quantityAvailable": 1, "price": {"amount": "10.5", "currencyCode": "USD"}, "selectedOptions": []}])]}}

prods = {p["id"]: p for p in [
    product("Lightning Bolt - Magic 2010 (M10)", variants=[
        {"availableForSale": True, "quantityAvailable": 3, "price": {"amount": "2.0", "currencyCode": "USD"},
         "selectedOptions": [{"name": "Condition", "value": "Near Mint"}, {"name": "Finish", "value": "Non-Foil"}]},
        {"availableForSale": True, "quantityAvailable": 1, "price": {"amount": "1.5", "currencyCode": "USD"},
         "selectedOptions": [{"name": "Condition", "value": "Lightly Played"}, {"name": "Finish", "value": "Foil"}]},
        {"availableForSale": False, "quantityAvailable": 0, "price": {"amount": "1.0", "currencyCode": "USD"}, "selectedOptions": []}]),
    product("Modern Horizons 3 - Collector Booster Box", ptype="sealed"),
    product("Sold Out Card - Alpha (LEA)", avail=False),
    product("Mystery Box", ptype=""),
    product("Cloud, Midgar Mercenary - Pro Tour Promos (PTP)", ptype="", lang="Japanese")]}
ls = sorted(pv.listings(prods), key=lambda x: (x["name"], x["cents"]))
check("products: sealed, sold-out and non-card products left out; one listing per available variant",
      [(x["name"], x["cents"], x["qty"], x["cond"], x["foil"], x["lang"]) for x in ls]
      == [("Cloud, Midgar Mercenary", 1050, 1, "", False, "JA"), ("Lightning Bolt", 150, 1, "LP", True, "EN"), ("Lightning Bolt", 200, 3, "NM", False, "EN")],
      [(x["name"], x["cents"], x["qty"], x["cond"], x["foil"], x["lang"]) for x in ls])

# ---- the printings a title allows
def printing(id, set, number, lang="en", **kw):
    c = {"id": id, "name": "X", "set": set, "set_name": kw.pop("set_name", set.upper() + " set"), "number": number, "lang": lang,
         "promo_types": [], "frame_effects": [], "border_color": "black", "frame": "2015", "full_art": False,
         "finishes": ["nonfoil", "foil"], "illustration": "art1", "picture": f"https://img/{id}.jpg"}
    c.update(kw)
    return c

who = [printing("plain", "who", "194", finishes=["etched"]),
       printing("show", "who", "561", border_color="borderless", frame_effects=["showcase"]),
       printing("serial", "who", "561z", border_color="borderless", frame_effects=["showcase"], promo_types=["serialized"], finishes=["foil"]),
       printing("other", "pip", "1", set_name="Fallout")]
fit = lambda title: [c["id"] for c in pv.title_fits(pv.parse_title(title), who)]
check("title fits: a serialized copy only fits the serialized printing", fit("X (Serial) - Doctor Who (WHO)") == ["serial"], fit("X (Serial) - Doctor Who (WHO)"))
check("title fits: a plain title rules the serialized one out", fit("X - Doctor Who (WHO)") == ["show"], fit("X - Doctor Who (WHO)"))
check("title fits: the set by its name when the code is unknown", fit("X - Fallout (PIPX)") == ["other"], fit("X - Fallout (PIPX)"))
check("title fits: a set nobody has fits nothing", fit("X - Nowhere (NOPE)") == [], fit("X - Nowhere (NOPE)"))

# ---- the picture check, on made-up cards and photos
rng = np.random.default_rng(7)


def made_up_card(seed):
    r = np.random.default_rng(seed)
    img = np.full((pv.CARD_H, pv.CARD_W, 3), 235, np.uint8)
    cv2.rectangle(img, (20, 20), (pv.CARD_W - 20, pv.CARD_H - 20), (30, 30, 30), 14)
    for _ in range(140):   # the "artwork" and "text": random shapes
        x, y = int(r.integers(40, pv.CARD_W - 40)), int(r.integers(40, pv.CARD_H - 40))
        col = tuple(int(v) for v in r.integers(0, 255, 3))
        if r.random() < 0.5:
            cv2.circle(img, (x, y), int(r.integers(4, 30)), col, -1)
        else:
            cv2.rectangle(img, (x, y), (x + int(r.integers(5, 50)), y + int(r.integers(5, 30))), col, -1)
    cv2.putText(img, f"CARD {seed}", (40, 70), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 3)
    return img


def photo_of(card, angle=0.08):
    bg = rng.integers(60, 120, (1100, 900, 3)).astype(np.uint8)
    bg = cv2.GaussianBlur(bg, (31, 31), 0)
    h, w = card.shape[:2]
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = np.float32([[230, 210], [650 + 900 * angle, 240], [690, 820], [200, 790]])
    H = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(card, H, (900, 1100))
    mask = cv2.warpPerspective(np.full((h, w), 255, np.uint8), H, (900, 1100))
    bg[mask > 0] = warped[mask > 0]
    return cv2.GaussianBlur(bg, (3, 3), 0)


card_a, card_b = made_up_card(1), made_up_card(2)
photo = pv.Features(photo_of(card_a))
inl_a, like_a, flat = pv.match_photo(photo, pv.Features(card_a))
inl_b, like_b, _ = pv.match_photo(photo, pv.Features(card_b))
check("picture: a photo of the card fits it (many features, very alike once straightened)",
      inl_a >= 100 and like_a >= 0.8 and flat is not None and flat.shape[:2] == (pv.CARD_H, pv.CARD_W), (inl_a, like_a))
check("picture: …and doesn't fit another card", inl_b < pv.MIN_INLIERS or like_b < pv.MIN_LIKENESS, (inl_b, like_b))

# the language: the same card with other "text" in its name bar and text box
card_ja = card_a.copy()
h = pv.CARD_H
r = np.random.default_rng(99)
for y0, y1 in ((int(h * 0.03), int(h * 0.11)), (int(h * 0.55), int(h * 0.95))):
    card_ja[y0:y1, 30:pv.CARD_W - 30] = 235
    for _ in range(40):
        x, y = int(r.integers(40, pv.CARD_W - 60)), int(r.integers(y0 + 4, y1 - 10))
        cv2.rectangle(card_ja, (x, y), (x + int(r.integers(6, 30)), y + 6), (0, 0, 0), -1)
t_same, t_other = pv.text_likeness(flat, card_a), pv.text_likeness(flat, card_ja)
check("language: the photo's text is more like its own language's picture", t_same > t_other + 0.2, (t_same, t_other))

# ---- title and photos: who decides
L = lambda title: pv.parse_title(title)
sc = lambda **kw: {k: (v[0], v[1], 0, None) for k, v in kw.items()}
base = {"plain": (30, 0.2), "other": (0, 0.0)}
c, why, note = pv.choose(L("X (Serial) - Doctor Who (WHO)"), who, pv.title_fits(L("X (Serial) - Doctor Who (WHO)"), who),
                         sc(**base, show=(330, 0.87), serial=(420, 0.87)))
check("choose: title and photos agree (the serialized look matches both showcase printings; the title picks)", c and c["id"] == "serial" and not why, (c, why))
c, why, note = pv.choose(L("X - Doctor Who (WHO)"), who, pv.title_fits(L("X - Doctor Who (WHO)"), who),
                         sc(plain=(300, 0.9), show=(60, 0.4), serial=(60, 0.4), other=(0, 0.0)))
check("choose: a plain title and photos of the plain card", c and c["id"] == "plain", (c, why))
c, why, note = pv.choose(L("X (Showcase) - Doctor Who (WHO)"), who, pv.title_fits(L("X (Showcase) - Doctor Who (WHO)"), who),
                         sc(plain=(80, 0.7), show=(60, 0.62), serial=(60, 0.62), other=(0, 0.0)))
check("choose: photos that look more like another printing, not beyond doubt: held back", c is None and "photos look like WHO #194" in why, (c, why))
c, why, note = pv.choose(L("X (Showcase) - Doctor Who (WHO)"), who, pv.title_fits(L("X (Showcase) - Doctor Who (WHO)"), who),
                         sc(plain=(400, 0.93), show=(60, 0.5), serial=(60, 0.5), other=(0, 0.0)))
check("choose: photos that clearly show another printing win, with a note", c and c["id"] == "plain" and "clearly show WHO #194" in note, (c, why, note))
c, why, note = pv.choose(L("X - Doctor Who (WHO)"), who, pv.title_fits(L("X - Doctor Who (WHO)"), who), sc(plain=(10, 0.1), show=(12, 0.2), serial=(9, 0.1), other=(0, 0)))
check("choose: photos that show none of the printings: held back", c is None and "don't clearly show" in why, why)
ja = [printing("jaonly", "pspl", "4", lang="ja"), printing("ppro", "ppro", "2025-1", set_name="Pro Tour Promos")]
c, why, note = pv.choose(L("X - Pro Tour Promos (PTP) (Japanese)"), ja, pv.title_fits(L("X - Pro Tour Promos (PTP) (Japanese)"), ja),
                         sc(jaonly=(430, 0.96), ppro=(220, 0.68)))
check("choose: a Japanese copy under the wrong set: the Japanese printing the photos show", c and c["id"] == "jaonly" and note, (c, why, note))
c, why, note = pv.choose(L("X - Pro Tour Promos (PTP)"), ja, pv.title_fits(L("X - Pro Tour Promos (PTP)"), ja),
                         sc(jaonly=(430, 0.96), ppro=(220, 0.68)))
check("choose: …but not for a listing that says English", c is None, (c, note))

# ---- offer rows for build_prices.py
rows, links = {}, {}
data = {"listings": [{"handle": "bolt-m10", "cents": 200, "qty": 3, "cond": "NM", "lang": "EN", "foil": False, "id": "b1"},
                     {"handle": "cloud-ptp", "cents": 72999, "qty": 1, "cond": "", "lang": "JA", "foil": True, "id": "c1", "note": "…"},
                     {"handle": "held", "cents": 100, "qty": 1, "cond": "", "lang": "EN", "foil": False, "held": "the photos …"},
                     {"handle": "event", "title": "Draft night", "held": pv.NOT_A_CARD}]}
n, held = pv.add_offers(data, rows, links)
check("offers: matched listings as rows, held-back ones left out", (n, held) == (2, 2)
      and rows == {"b1": [["pv", 0, "NM", 200, 3, ""]], "c1": [["pv", 1, "", 72999, 1, "JA"]]}
      and links == {"b1": {"pv": "bolt-m10"}, "c1": {"pv": "cloud-ptp"}}, (n, held, rows, links))

print(f"\n{'All checks passed' if not failed else str(failed) + ' failed'}")
sys.exit(1 if failed else 0)
