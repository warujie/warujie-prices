"""Card-scan probe: match real phone photos against the index, locally.

  python scan_probe/real_photos.py --out OUT PHOTO... [--truth truth.json] [--corners corners.json]

The photos are never committed (they are the owner's). Each photo is looked
for a card the way the phone will (round 2's "detect3": a few outlines near a
card-shaped guide, each tried with small shifts). The photos weren't taken
with the guide on screen, so guides of a few sizes are tried and every
outline they give is matched. truth.json maps a photo's file name to the right
card's oracle id; corners.json can give a photo's corners by hand (tl, tr, br,
bl) to separate finding the card from matching it. "Sure" uses the thresholds
the made-up photos calibrated (results_summary.json, at most 0.5% wrong).
"""
import argparse
import json
import os
import sys

import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import warp_region  # noqa: E402
from matcher import (Index, found_variants, guide_variants, near_variants, outline_hypotheses,  # noqa: E402
                     centre_and_cross, FOUND_SHIFTS, FOUND_SCALES, GUIDE_SHIFTS, GUIDE_SCALES,
                     NEAR_SHIFTS, NEAR_SCALES)
from detect import detect_cards, CARD_RATIO  # noqa: E402

FOUND_EMB = centre_and_cross(list(FOUND_SHIFTS), list(FOUND_SCALES))
GUIDE_EMB = centre_and_cross(list(GUIDE_SHIFTS), list(GUIDE_SCALES))
NEAR_EMB = centre_and_cross(list(NEAR_SHIFTS), list(NEAR_SCALES))
SHOWN = ("h256", "dhv", "h256+dhv", "dhv+mnv3sb")
MAX_OUTLINES = 6


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
    for frac in (0.82, 0.92, 0.72, 0.62, 0.52):   # most likely first
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


def outlines(photo):
    """Every distinct outline the guides give, best first within each guide."""
    w = photo.shape[1]
    hyps = []
    for g in guides_for(photo):
        for q in outline_hypotheses(detect_cards(photo, g, np.random.default_rng(0), k=2)):
            if all(np.abs(q - p).max() > 0.015 * w for p in hyps):
                hyps.append(q)
    return hyps[:MAX_OUTLINES]


def thresholds(out_dir):
    try:
        table = json.load(open(os.path.join(out_dir, "results_summary.json")))["table"]
    except (OSError, KeyError, ValueError):
        return {}
    return {s: table[f"detect3/{s}"]["sure@0.005"] for s in SHOWN if f"detect3/{s}" in table}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--truth")
    ap.add_argument("--corners")
    ap.add_argument("--save-found", help="folder for pictures of the outlines tried and the art matched")
    ap.add_argument("--report", default="real_photos_local.json")
    ap.add_argument("photos", nargs="+")
    args = ap.parse_args()
    idx = Index(args.out, models=True, threads=4)
    sure_at = thresholds(args.out)
    truth = json.load(open(args.truth)) if args.truth else {}
    manual = json.load(open(args.corners)) if args.corners else {}
    names = {}
    for o, r in zip(idx.entry_oracle, idx.rows):
        names.setdefault(int(o), idx.entries[r]["name"])
    rows = []
    for path in args.photos:
        base = os.path.basename(path)
        photo = read_photo(path)
        if photo is None:
            print(base, "unreadable")
            continue
        photo, f = shrink(photo)
        true = idx.oracle_index(truth[base]) if base in truth else None
        if base in manual:
            hyps, how = [np.float32(manual[base]) * f], "manual"
            var, emb = found_variants(hyps[0]), FOUND_EMB
        else:
            hyps = outlines(photo)
            how = f"detect ({len(hyps)} outlines)" if hyps else "guide"
            if hyps:
                n1 = len(NEAR_SHIFTS) ** 2 * len(NEAR_SCALES)
                var, emb = near_variants(hyps), [h * n1 + NEAR_EMB[0] for h in range(len(hyps))]
            else:
                var, emb = guide_variants(guides_for(photo)[0]), GUIDE_EMB
        d = idx.distances(photo, var, emb)
        if args.save_found:
            os.makedirs(args.save_found, exist_ok=True)
            vis = photo.copy()
            for k, q in enumerate(hyps):
                cv2.polylines(vis, [q.astype(np.int32)], True, (255, 0, 0) if k == 0 else (0, 160, 255), 3)
            small = cv2.resize(vis, None, fx=0.4, fy=0.4)
            cv2.imwrite(os.path.join(args.save_found, base + ".jpg"), cv2.cvtColor(small, cv2.COLOR_RGB2BGR))
            if hyps:
                art = warp_region(photo, hyps[0])
                cv2.imwrite(os.path.join(args.save_found, base + ".art.jpg"), cv2.cvtColor(art, cv2.COLOR_RGB2BGR))
        res = {}
        for name, sc in Index.scorings(d).items():
            r = idx.rank(sc, true, top=5)
            s1, s2 = r["s"][0], r["s"][1]
            t = sure_at.get(name)
            sure = bool(t) and s1 <= t["best_max"] and s1 / max(s2, 1e-9) <= t["ratio"]
            res[name] = {"top": [names[o] for o in r["top"]], "s": [round(s1, 3), round(s2, 3)],
                         "sure": sure, "true_rank": r.get("true_rank")}
        rows.append({"photo": base, "how": how, "res": res})
        for name in SHOWN:
            if name in res:
                x = res[name]
                print(f"{base}: {how}; {name} -> {x['top'][:3]} s={x['s']} sure={x['sure']} "
                      f"true_rank={x['true_rank']}", flush=True)
    with open(args.report, "w", encoding="utf-8") as fo:
        json.dump(rows, fo, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
