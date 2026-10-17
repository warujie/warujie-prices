"""Card-scan probe: match real phone photos against the index, locally.

  python scan_probe/real_photos.py --out OUT PHOTO... [--truth truth.json] [--corners corners.json]

The photos are never committed (they are the owner's). Each photo is looked
for a card the way the phone will: a card-shaped guide, here tried at a few
sizes since the photos weren't taken with one. truth.json maps a photo's file
name to the right card's oracle id; corners.json can give a photo's corners
by hand (tl, tr, br, bl) to separate finding the card from matching it.
"""
import argparse
import json
import os
import sys

import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from matcher import Index, found_variants, guide_variants, centre_and_cross, FOUND_SHIFTS, FOUND_SCALES, GUIDE_SHIFTS, GUIDE_SCALES  # noqa: E402
from detect import detect_card, CARD_RATIO  # noqa: E402

FOUND_EMB = centre_and_cross(list(FOUND_SHIFTS), list(FOUND_SCALES))
GUIDE_EMB = centre_and_cross(list(GUIDE_SHIFTS), list(GUIDE_SCALES))


def read_photo(path):
    try:
        from PIL import Image, ImageOps
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:
            pass
        im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
        return np.array(im)
    except Exception:  # noqa: BLE001
        img = cv2.imread(path, cv2.IMREAD_COLOR)
        return None if img is None else cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def guides_for(photo):
    """Card-shaped guides centred in the frame, at a few sizes."""
    h, w = photo.shape[:2]
    out = []
    for frac in (0.82, 0.92, 0.72, 0.62):   # most likely first
        gw = frac * w
        gh = gw / CARD_RATIO
        if gh > 0.98 * h:
            gh = 0.98 * h
            gw = gh * CARD_RATIO
        out.append((w / 2 - gw / 2, h / 2 - gh / 2, w / 2 + gw / 2, h / 2 + gh / 2))
    return out


def shrink(photo, long_side=1440):
    h, w = photo.shape[:2]
    f = long_side / max(h, w)
    if f >= 1:
        return photo, 1.0
    return cv2.resize(photo, (int(w * f), int(h * f)), interpolation=cv2.INTER_AREA), f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--truth")
    ap.add_argument("--corners")
    ap.add_argument("--save-found", help="folder for pictures of the outline found")
    ap.add_argument("--report", default="real_photos_local.json")
    ap.add_argument("photos", nargs="+")
    args = ap.parse_args()
    idx = Index(args.out, models=True, threads=4)
    truth = json.load(open(args.truth)) if args.truth else {}
    manual = json.load(open(args.corners)) if args.corners else {}
    names = {i: idx.entries[r] for i, r in zip(idx.entry_oracle, idx.rows)}
    rows = []
    for path in args.photos:
        base = os.path.basename(path)
        photo = read_photo(path)
        if photo is None:
            print(base, "unreadable")
            continue
        photo, f = shrink(photo)
        true = idx.oracle_index(truth[base]) if base in truth else None
        found, how = None, "guide"
        if base in manual:
            found, how = np.float32(manual[base]) * f, "manual"
        else:
            for g in guides_for(photo):
                found = detect_card(photo, g)
                if found is not None:
                    how = "detect"
                    break
        if found is not None:
            d = idx.distances(photo, found_variants(found), FOUND_EMB)
        else:
            d = idx.distances(photo, guide_variants(guides_for(photo)[0]), GUIDE_EMB)
        if args.save_found and found is not None:
            os.makedirs(args.save_found, exist_ok=True)
            vis = photo.copy()
            cv2.polylines(vis, [found.astype(np.int32)], True, (255, 0, 0), 4)
            cv2.imwrite(os.path.join(args.save_found, base + ".jpg"), cv2.cvtColor(cv2.resize(vis, None, fx=0.4, fy=0.4), cv2.COLOR_RGB2BGR))
        res = {}
        for name, sc in Index.scorings(d).items():
            r = idx.rank(sc, true, top=5)
            res[name] = {"top": [names[o]["name"] for o in r["top"]], "s": [round(x, 3) for x in r["s"][:2]],
                         "true_rank": r.get("true_rank")}
        rows.append({"photo": base, "how": how, "res": res})
        best = res.get("h256+col", res.get("h256"))
        print(f"{base}: {how}; h256+col -> {best['top'][:3]} s={best['s']} true_rank={best['true_rank']}", flush=True)
    with open(args.report, "w", encoding="utf-8") as fo:
        json.dump(rows, fo, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
