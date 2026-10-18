"""Card-scan probe, step 3: make test photos from the sample cards, find the
card in each, and measure how often each way of matching names the right
card, and how often it would open a wrong card page when it says it is sure.

  python scan_probe/evaluate.py --out OUT --cache DIR [--budget-min N] [--workers 4]

Ways of locating the card compared on every photo:
  truth   - the card's real corners (the best a card finder could do)
  detect3 - round 2's outlines near the guide (best, it one border further
            out, second best), else the guide itself
  detect4 - round 4's: the same found after more smoothing, plus the best
            outline of the texture-aware search (carpet, cloth)
"Sure" rules are calibrated twice: on the test photos alone, and with each
photo also standing in for a card that isn't in the index (a token, an art
card): its scores with the true card left out, which must never be sure.
"""
import argparse
import gzip
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from matcher import (Index, found_variants, guide_variants, centre_and_cross,  # noqa: E402
                     outline_hypotheses, guide_outlines, near_variants,
                     FOUND_SHIFTS, FOUND_SCALES, GUIDE_SHIFTS, GUIDE_SCALES, NEAR_SHIFTS, NEAR_SCALES)
from synth import make_photo, GUIDE  # noqa: E402
from detect import detect_cards  # noqa: E402
from build_index import picture_path, read_rgb  # noqa: E402

LEVELS = ("easy", "normal", "hard")
METHODS = ("truth", "detect3", "detect4")   # round 3 dropped "detect" (one outline); round 4 adds detect4
TARGETS = (0.002, 0.005, 0.01)   # wrong-page rates allowed among confident answers

IDX = None
TESTS = None
CACHE = None
FOUND_EMB = centre_and_cross(list(FOUND_SHIFTS), list(FOUND_SCALES))
GUIDE_EMB = centre_and_cross(list(GUIDE_SHIFTS), list(GUIDE_SCALES))
NEAR_EMB = centre_and_cross(list(NEAR_SHIFTS), list(NEAR_SCALES))


def init_worker():
    cv2.setNumThreads(1)
    IDX.open_models(threads=1)


def run_test(i):
    t = TESTS[i]
    img = read_rgb(picture_path(CACHE, "normal", t["id"], t["face"]))
    if img is None:
        return []
    if img.shape[:2] != (680, 488):
        img = cv2.resize(img, (488, 680), interpolation=cv2.INTER_AREA)
    true = IDX.oracle_index(t["oracle"])
    if true is None:
        return []
    out = []
    for lv in LEVELS:
        rng = np.random.default_rng([20261017, i, LEVELS.index(lv)])
        photo, corners = make_photo(img, lv, rng)
        quads = detect_cards(photo, GUIDE, rng, k=2)
        found = quads[0] if quads else None
        hyps4 = guide_outlines(photo, GUIDE)
        card_w = np.linalg.norm(corners[1] - corners[0])
        for m in METHODS:
            t0 = time.time()
            rec = {"t": i, "cat": t["category"], "lv": lv, "m": m}
            if m == "truth":
                var, emb = found_variants(corners), FOUND_EMB
            elif m == "detect" and found is not None:
                var, emb = found_variants(found), FOUND_EMB
                rec["det"] = 1
                rec["cerr"] = round(float(np.linalg.norm(found - corners, axis=1).mean() / card_w), 4)
            elif (m == "detect3" and found is not None) or (m == "detect4" and hyps4):
                hyps = outline_hypotheses(quads) if m == "detect3" else hyps4
                var = near_variants(hyps)
                # the image model looks at the centre of each outline tried
                n1 = len(NEAR_SHIFTS) ** 2 * len(NEAR_SCALES)
                emb = [h * n1 + NEAR_EMB[0] for h in range(len(hyps))]
                rec["det"] = 1
                rec["cerr"] = round(float(min(np.linalg.norm(q - corners, axis=1).mean() for q in hyps) / card_w), 4)
            else:
                var, emb = guide_variants(GUIDE), GUIDE_EMB
                rec["det"] = 0
            d = IDX.distances(photo, var, emb)
            res = {}
            for name, sc in Index.scorings(d).items():
                r = IDX.rank(sc, true, top=5)
                # [true card's rank, best, second, right?, best card's name, third]
                res[name] = [r.get("true_rank", 99), round(r["s"][0], 4), round(r["s"][1], 4), int(r["top"][0] == true),
                             IDX.oracle_names[r["top"][0]], round(r["s"][2], 4)]
            rec["res"] = res
            rec["sec"] = round(time.time() - t0, 3)
            out.append(rec)
    return out


# ---- turning the records into numbers ------------------------------------------------------

def unknown_scores(r):
    """A test photo's scores as if its card weren't in the index (a token, an
    art card): the true card left out of the best three. None for records
    from before round 4 (no third score)."""
    if len(r) < 6:
        return None
    rank, s1, s2, s3 = r[0], r[1], r[2], r[5]
    return (s2, s3) if rank == 0 else (s1, s3) if rank == 1 else (s1, s2)


def calibrate(recs, scoring, target, rng, with_unknown=False):
    """Split the test cards in two; on one half find the ratio (best / second
    best) and best-score limits that let the most answers through as 'sure'
    with at most `target` of them wrong; report that rule on the other half.
    with_unknown: every photo also counts once as an unknown card, and a sure
    answer to it is wrong. "unknown_sure" is how often the rule is sure of a
    card that isn't in the index."""
    cards = sorted({r["t"] for r in recs})
    rng.shuffle(cards)
    half = set(cards[: len(cards) // 2])

    def arrays(rs, unknown=False):
        if unknown:
            u = [unknown_scores(r["res"][scoring]) for r in rs]
            v = np.array([(0, a, b, 0) for a, b in (x for x in u if x)], dtype=np.float64).reshape(-1, 4)
        else:
            v = np.array([r["res"][scoring][:4] for r in rs], dtype=np.float64).reshape(-1, 4)
        s1, s2, ok = v[:, 1], v[:, 2], v[:, 3] > 0
        ratio = np.where(s2 > 0, s1 / np.maximum(s2, 1e-9), 1.0)
        return ratio, s1, ok

    def joined(rs):
        a = arrays(rs)
        if not with_unknown:
            return a
        b = arrays(rs, unknown=True)
        return tuple(np.concatenate([x, y]) for x, y in zip(a, b))

    cal = [r for r in recs if r["t"] in half]
    tst = [r for r in recs if r["t"] not in half]
    if not cal or not tst:
        return None
    ratio, s1, ok = joined(cal)
    if with_unknown and len(ratio) == len(cal):
        return None   # no third scores: records from before round 4
    best = None
    for rq in np.unique(np.quantile(ratio, np.linspace(0.01, 1.0, 120))):
        for aq in list(np.unique(np.quantile(s1, np.linspace(0.05, 1.0, 20)))) + [np.inf]:
            conf = (ratio <= rq) & (s1 <= aq)
            n = conf.sum()
            if n == 0:
                continue
            wrong = (conf & ~ok).sum() / n
            if wrong <= target and (best is None or n > best[0]):
                best = (n, rq, aq)
    if best is None:
        return {"coverage": 0.0, "wrong": None}
    _, rq, aq = best
    ratio, s1, ok = arrays(tst)
    conf = (ratio <= rq) & (s1 <= aq)
    n = int(conf.sum())
    out = {"ratio": float(rq), "best_max": float(aq), "coverage": n / len(tst),
           "wrong": (float((conf & ~ok).sum() / n) if n else None), "n": len(tst),
           "wrong_count": int((conf & ~ok).sum()), "sure_count": n}
    ur, us, _ = arrays(tst, unknown=True)
    if len(ur):
        out["unknown_sure"] = float(((ur <= rq) & (us <= aq)).mean())
    return out


def pct(x):
    return "–" if x is None else f"{100 * x:.1f}%"


def summarise(recs, out_dir, meta):
    rng = np.random.default_rng(7)
    scorings = sorted(recs[0]["res"].keys()) if recs else []
    table = {}
    for m in METHODS:
        rs = [r for r in recs if r["m"] == m]
        for sc in scorings:
            v = np.array([r["res"][sc][:4] for r in rs])
            row = {"top1": float((v[:, 0] == 0).mean()), "top5": float((v[:, 0] < 5).mean())}
            for tg in TARGETS:
                row[f"sure@{tg}"] = calibrate(rs, sc, tg, rng)
                row[f"sure_u@{tg}"] = calibrate(rs, sc, tg, rng, with_unknown=True)
            for lv in LEVELS:
                vv = np.array([r["res"][sc][:4] for r in rs if r["lv"] == lv])
                if len(vv):
                    row[f"top1_{lv}"] = float((vv[:, 0] == 0).mean())
            table[f"{m}/{sc}"] = row
    # the best scoring for each locating method, by sure-coverage at 0.5% wrong
    best = {}
    for m in METHODS:
        cands = [(table[f"{m}/{sc}"]["sure@0.005"] or {}).get("coverage", 0) for sc in scorings]
        if cands:
            best[m] = scorings[int(np.argmax(cands))]
    by_cat = {}
    for m, sc in best.items():
        for cat in sorted({r["cat"] for r in recs}):
            for lv in LEVELS:
                v = np.array([r["res"][sc][:4] for r in recs if r["m"] == m and r["cat"] == cat and r["lv"] == lv])
                if len(v):
                    by_cat.setdefault(m, {}).setdefault(cat, {})[lv] = {
                        "n": len(v), "top1": float((v[:, 0] == 0).mean()), "top5": float((v[:, 0] < 5).mean())}
    detect_stats = {}
    for m in METHODS:
        det = [r for r in recs if r["m"] == m and m != "truth"]
        if not det:
            continue
        det_ok = [r for r in det if r.get("det")]
        st = {lv: {"found": float(np.mean([r.get("det", 0) for r in det if r["lv"] == lv])),
                   "corner_err_median": float(np.median([r["cerr"] for r in det_ok if r["lv"] == lv]))
                   if any(r["lv"] == lv for r in det_ok) else None} for lv in LEVELS}
        cerr = np.array([r["cerr"] for r in det_ok])
        st["best_of_tried_over_3pct"] = float((cerr > 0.03).mean()) if cerr.size else None
        detect_stats[m] = st
    secs = {m: float(np.mean([r["sec"] for r in recs if r["m"] == m])) for m in METHODS if any(r["m"] == m for r in recs)}
    summary = {"meta": meta, "table": table, "best": best, "by_category": by_cat, "detect": detect_stats,
               "seconds_per_match": secs}
    with open(os.path.join(out_dir, "results_summary.json"), "w") as f:
        json.dump(summary, f, indent=1)

    L = ["# Card scan probe: results", "",
         f"Index: {meta.get('index_entries')} entries ({meta.get('index_oracles')} cards). "
         f"Test photos: {meta.get('tests_done')} cards × 3 levels × {len(METHODS)} ways of finding the card. "
         f"Run took {meta.get('minutes')} min.", "",
         "## Best scoring per way of finding the card", "",
         "| Finding | Scoring | Right card first | In top 5 | Sure (≤0.2% wrong) | Sure (≤0.5% wrong) | Sure (≤1% wrong) | Easy | Normal | Hard |",
         "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for m, sc in best.items():
        r = table[f"{m}/{sc}"]
        sure = [r[f"sure@{tg}"] or {} for tg in TARGETS]
        L.append(f"| {m} | {sc} | {pct(r['top1'])} | {pct(r['top5'])} | "
                 + " | ".join(f"{pct(s.get('coverage'))} (wrong {pct(s.get('wrong'))})" for s in sure)
                 + f" | {pct(r.get('top1_easy'))} | {pct(r.get('top1_normal'))} | {pct(r.get('top1_hard'))} |")
    L += ["", "## Every scoring", "",
          "Unknown card sure: how often the ≤0.5% rule is sure of a card that isn't in the index. "
          "With unknown cards: the rule calibrated so those count as wrong answers too.", "",
          "| Finding/scoring | Right first | Top 5 | Sure ≤0.5% wrong | Unknown card sure | Sure ≤0.5% with unknown cards (unknown sure) | Easy | Normal | Hard |",
          "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for k, r in sorted(table.items(), key=lambda kv: -kv[1]["top1"]):
        s = r["sure@0.005"] or {}
        u = r.get("sure_u@0.005") or {}
        L.append(f"| {k} | {pct(r['top1'])} | {pct(r['top5'])} | {pct(s.get('coverage'))} | {pct(s.get('unknown_sure'))} | "
                 f"{pct(u.get('coverage'))} ({pct(u.get('unknown_sure'))}) | "
                 f"{pct(r.get('top1_easy'))} | {pct(r.get('top1_normal'))} | {pct(r.get('top1_hard'))} |")
    for m, cats in by_cat.items():
        L += ["", f"## By kind of card ({m}, {best[m]}): right card first / in top 5", "",
              "| Kind | Easy | Normal | Hard |", "| --- | --- | --- | --- |"]
        for cat, lv in cats.items():
            L.append(f"| {cat} (n={lv.get('easy', {}).get('n', 0)}) | "
                     + " | ".join(f"{pct(lv[x]['top1'])} / {pct(lv[x]['top5'])}" if x in lv else "–" for x in LEVELS) + " |")
    L += ["", "## Card finder", "", "| Finder | Level | Outline found | Median corner error of the best outline tried (share of card width) |",
          "| --- | --- | --- | --- |"]
    for m, st in detect_stats.items():
        for lv in LEVELS:
            L.append(f"| {m} | {lv} | {pct(st[lv]['found'])} | {pct(st[lv]['corner_err_median'])} |")
        L.append(f"| {m} | all | best outline tried more than 3% off | {pct(st['best_of_tried_over_3pct'])} |")
    L += ["", f"Seconds per match on the runner (Python, one core): {json.dumps(secs)}"]
    with open(os.path.join(out_dir, "results.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))


def main():
    global IDX, TESTS, CACHE
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--cache", default="scan_cache")
    ap.add_argument("--budget-min", type=float, default=60)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    t_start = time.time()
    CACHE = args.cache
    IDX = Index(args.out, models=False)
    TESTS = json.load(open(os.path.join(args.out, "test_sample.json"), encoding="utf-8"))
    order = list(np.random.default_rng(1).permutation(len(TESTS)))
    if args.limit:
        order = order[: args.limit]
    print(f"index entries {len(IDX.rows):,}, cards {len(IDX.oracle_names):,}, tests {len(order):,}, "
          f"models {list(IDX.emb)}", flush=True)
    recs = []
    done = 0
    deadline = t_start + args.budget_min * 60
    ctx = mp.get_context("fork")
    with ctx.Pool(args.workers, initializer=init_worker) as pool:
        for out in pool.imap_unordered(run_test, [int(i) for i in order], chunksize=2):
            recs.extend(out)
            done += 1
            if done % 100 == 0:
                print(f"  {done:,} cards, {time.time() - t_start:,.0f} s", flush=True)
            if time.time() > deadline:
                print("time budget reached", flush=True)
                pool.terminate()
                break
    with gzip.open(os.path.join(args.out, "results.jsonl.gz"), "wt") as f:
        for r in recs:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    meta = {"index_entries": len(IDX.rows), "index_oracles": len(IDX.oracle_names),
            "tests_done": done, "minutes": round((time.time() - t_start) / 60, 1)}
    summarise(recs, args.out, meta)


if __name__ == "__main__":
    main()
