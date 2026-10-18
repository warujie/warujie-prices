"""Card-scan probe: match real phone photos against the index, locally.

  python scan_probe/real_photos.py --out OUT PHOTO... [--truth truth.json] [--corners corners.json]
                                   [--mode taken|corners|framed]

The photos are never committed (they are the owner's). Three ways to use them:
  taken   - the photo as it is. It wasn't taken with the guide on screen, so
            guides of a few sizes are tried (round 2's "detect3" near each),
            plus outlines found anywhere in the photo.
  corners - the card's corners from corners.json (tl, tr, br, bl, in the photo
            shrunk to 1440 pixels on its long side): matching
            alone, with finding the card taken out.
  framed  - the photo moved and scaled so the card sits in the on-screen guide
            (a little off, as a hand holds it), then found and matched as the
            phone will: what a visitor sees who follows the guide.
truth.json maps a photo's file name to the right card's oracle id; a photo of
a card that isn't in the index (a token) is left out of it, and any "sure"
answer for it is wrong. "Sure" uses the thresholds the made-up photos
calibrated (results_summary.json, at most 0.5% wrong; round 4's finder and
unknown-card rule when there). Each known photo is also scored as if its card
weren't in the index ("unknown sure", which should stay 0).
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
                     guide_outlines, detect4_variants, expand_border, centre_and_cross, FOUND_SHIFTS,
                     FOUND_SCALES, GUIDE_SHIFTS, GUIDE_SCALES, NEAR_SHIFTS, NEAR_SCALES, BORDER_X, BORDER_Y)
from detect import detect_cards, find_cards_anywhere, CARD_RATIO  # noqa: E402
from synth import FRAME_W, FRAME_H, GUIDE, GUIDE_W  # noqa: E402

FOUND_EMB = centre_and_cross(list(FOUND_SHIFTS), list(FOUND_SCALES))
GUIDE_EMB = centre_and_cross(list(GUIDE_SHIFTS), list(GUIDE_SCALES))
NEAR_EMB = centre_and_cross(list(NEAR_SHIFTS), list(NEAR_SCALES))
SHOWN = ("h256", "h256r", "h256+dhv", "h256+mnv3sb")
MAX_OUTLINES = 9


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


def shrink_border(corners):
    """The outline one card border further in: a sleeve's edge found instead of the card's."""
    src = np.float32([[0, 0], [1, 0], [1, 1], [0, 1]])
    m = cv2.getPerspectiveTransform(src, np.float32(corners))
    bx, by = BORDER_X / (1 + 2 * BORDER_X), BORDER_Y / (1 + 2 * BORDER_Y)
    pts = np.float32([[bx, by], [1 - bx, by], [1 - bx, 1 - by], [bx, 1 - by]])
    return cv2.perspectiveTransform(pts[None], m)[0]


def add_outline(hyps, q, w):
    if all(np.abs(q - p).max() > 0.015 * w for p in hyps):
        hyps.append(np.float32(q))


def outlines_near(photo, guide, finder):
    """The outlines matching tries near one guide: round 3's ("detect3") or round 4's."""
    if finder == 3:
        return outline_hypotheses(detect_cards(photo, guide, np.random.default_rng(0), k=2))
    return guide_outlines(photo, guide)


def outlines_taken(photo, finder):
    """Outlines near centred guides of a few sizes, then anywhere in the photo."""
    w = photo.shape[1]
    hyps = []
    for g in guides_for(photo):
        for q in outlines_near(photo, g, finder):
            add_outline(hyps, q, w)
    near = hyps[:MAX_OUTLINES - 3]
    for q in find_cards_anywhere(photo, k=2):
        for x in (q, shrink_border(q), expand_border(q)):
            add_outline(near, x, w)
    return near[:MAX_OUTLINES + 3]


def frame_card(photo, corners, rng):
    """The photo as a phone frame with the card in the guide: scaled so the
    card is the guide's size (give or take 6%) and moved so it sits within 4%
    of the guide's centre. Returns the frame and the card's corners in it."""
    c = np.float32(corners)
    card_w = (np.linalg.norm(c[1] - c[0]) + np.linalg.norm(c[2] - c[3])) / 2
    s = GUIDE_W / card_w * rng.uniform(0.94, 1.06)
    centre = c.mean(axis=0)
    tx = FRAME_W / 2 + rng.uniform(-0.04, 0.04) * GUIDE_W - s * centre[0]
    ty = FRAME_H / 2 + rng.uniform(-0.04, 0.04) * GUIDE_W - s * centre[1]
    m = np.float32([[s, 0, tx], [0, s, ty]])
    interp = cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR
    frame = cv2.warpAffine(photo, m, (FRAME_W, FRAME_H), flags=interp, borderMode=cv2.BORDER_REFLECT)
    return frame, c * s + np.float32([tx, ty])


def thresholds(out_dir):
    """The "sure" rule per scoring from the made-up photos: round 4's finder
    and the rule that also keeps unknown cards unsure when the results have
    them, else what they have."""
    try:
        table = json.load(open(os.path.join(out_dir, "results_summary.json")))["table"]
    except (OSError, KeyError, ValueError):
        return {}
    out = {}
    for method in ("detect3", "detect4"):   # the later wins
        for k, v in table.items():
            if k.startswith(method + "/"):
                rule = v.get("sure_u@0.005") or v.get("sure@0.005")
                if rule and rule.get("ratio"):
                    out[k.split("/", 1)[1]] = rule
    return out


def is_sure(rule, s1, s2):
    return bool(rule) and s1 <= rule["best_max"] and s1 / max(s2, 1e-9) <= rule["ratio"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--truth")
    ap.add_argument("--corners")
    ap.add_argument("--mode", choices=["taken", "corners", "framed"], default="taken")
    ap.add_argument("--finder", type=int, choices=[3, 4], default=4,
                    help="outlines near the guide: round 3's (detect3) or round 4's (detect4, for carpet and cloth)")
    ap.add_argument("--framings", type=int, default=1, help="framed mode: framings per photo (each a little different)")
    ap.add_argument("--save-found", help="folder for pictures of the outlines tried and the art matched")
    ap.add_argument("--report", default="real_photos_local.json")
    ap.add_argument("photos", nargs="+")
    args = ap.parse_args()
    idx = Index(args.out, models=True, threads=4)
    sure_at = thresholds(args.out)
    truth = json.load(open(args.truth)) if args.truth else {}
    corners = json.load(open(args.corners)) if args.corners else {}
    names = {}
    for o, r in zip(idx.entry_oracle, idx.rows):
        names.setdefault(int(o), idx.entries[r]["name"])
    rows = []
    n1 = len(NEAR_SHIFTS) ** 2 * len(NEAR_SCALES)
    for k_photo, path in enumerate(args.photos):
        base = os.path.basename(path)
        photo = read_photo(path)
        if photo is None:
            print(base, "unreadable")
            continue
        photo, f = shrink(photo)
        true = idx.oracle_index(truth[base]) if base in truth else None
        if args.mode != "taken" and base not in corners:
            print(base, "no corners")
            continue
        for j in range(args.framings if args.mode == "framed" else 1):
            label = f"{base}#{j}" if args.mode == "framed" else base
            if args.mode == "corners":
                pic, hyps, how = photo, [np.float32(corners[base])], "corners"
                var, emb = found_variants(hyps[0]), FOUND_EMB
            else:
                if args.mode == "framed":
                    pic, _ = frame_card(photo, np.float32(corners[base]), np.random.default_rng([20261018, k_photo, j]))
                    hyps = outlines_near(pic, GUIDE, args.finder)
                else:
                    pic, hyps = photo, outlines_taken(photo, args.finder)
                how = f"{args.mode} ({len(hyps)} outlines)" if hyps else "guide only"
                g = GUIDE if args.mode == "framed" else guides_for(pic)[0]
                if args.finder == 4:
                    var, emb = detect4_variants(hyps, g)
                elif hyps:
                    var, emb = near_variants(hyps), [h * n1 + NEAR_EMB[0] for h in range(len(hyps))]
                else:
                    var, emb = guide_variants(g), GUIDE_EMB
            d = idx.distances(pic, var, emb)
            if args.save_found:
                os.makedirs(args.save_found, exist_ok=True)
                vis = pic.copy()
                for k, q in enumerate(hyps):
                    cv2.polylines(vis, [q.astype(np.int32)], True, (255, 0, 0) if k == 0 else (0, 160, 255), 3)
                small = cv2.resize(vis, None, fx=0.4, fy=0.4)
                cv2.imwrite(os.path.join(args.save_found, f"{args.mode}_{j}_{base}"), cv2.cvtColor(small, cv2.COLOR_RGB2BGR))
            res = {}
            for name, sc in Index.scorings(d).items():
                r = idx.rank(sc, true, top=5)
                s1, s2 = r["s"][0], r["s"][1]
                t = sure_at.get(name)
                rank_ = r.get("true_rank")
                # the same photo as if its card weren't in the index: the true card left out
                u = (r["s"][1], r["s"][2]) if rank_ == 0 else (r["s"][0], r["s"][2]) if rank_ == 1 else (s1, s2)
                res[name] = {"top": [names[o] for o in r["top"]], "s": [round(x, 3) for x in r["s"][:3]],
                             "sure": is_sure(t, s1, s2), "true_rank": rank_, "known": true is not None,
                             "unknown_sure": true is not None and is_sure(t, *u)}
            rows.append({"photo": label, "how": how, "res": res})
            print(f"{label}: {how}; " + "; ".join(
                f"{n} {res[n]['top'][0]!r} rank={res[n]['true_rank']} sure={res[n]['sure']}" for n in SHOWN if n in res),
                flush=True)
    with open(args.report, "w", encoding="utf-8") as fo:
        json.dump(rows, fo, ensure_ascii=False, indent=1)
    # one line per scoring: right card first, sure, sure but wrong, and sure
    # of the photos' cards if they weren't in the index (should be 0)
    print(f"\n{'scoring':14s} right first   sure   sure but wrong   unknown sure   ({len(rows)} photos, mode {args.mode})")
    for name in sorted(rows[0]["res"]) if rows else []:
        known = [r["res"][name] for r in rows if r["res"][name]["known"]]
        right = sum(1 for x in known if x["true_rank"] == 0)
        sure = [x for r in rows for x in [r["res"][name]] if x["sure"]]
        wrong = sum(1 for x in sure if not x["known"] or x["true_rank"] != 0)
        unknown = sum(1 for x in known if x["unknown_sure"])
        print(f"{name:14s} {right:3d} / {len(known):<5d} {len(sure):5d}   {wrong:5d}            {unknown:5d}")


if __name__ == "__main__":
    main()
