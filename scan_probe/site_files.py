"""Card-scan probe: the files the site's scanner reads, made from the probe's
fingerprints (out/index_features.npz, out/index_entries.json.gz).

  python scan_probe/site_files.py --out scan_probe/out --dest DIR [--rule-from scan_probe/out]
                                  [--rule BEST_MAX,RATIO]

scan_index.bin (little-endian):
  "WJS1", entries n (uint32), cards m (uint32),
  n x 32 bytes: each entry's 256-bit art fingerprint (h256, numpy.packbits order),
  n x uint32: each entry's card number (into "cards" below).
scan_cards.json:
  cards: oracle ids, by card number; entries: [set, collector number, language] for each
  entry, the printing whose picture was fingerprinted; rule: when a match counts as sure
  (best score at most best_max, best / second best at most ratio), from the probe's
  calibration on made-up photos (round 4's finder, unknown cards kept unsure).
"""
import argparse
import gzip
import json
import os
import struct

import numpy as np


def rule_from(out_dir, scoring="h256"):
    try:
        table = json.load(open(os.path.join(out_dir, "results_summary.json")))["table"]
    except (OSError, KeyError, ValueError):
        return None
    for method in ("detect4", "detect3"):
        row = table.get(f"{method}/{scoring}") or {}
        rule = row.get("sure_u@0.005") or row.get("sure@0.005")
        if rule and rule.get("ratio"):
            return {"best_max": rule["best_max"], "ratio": rule["ratio"], "from": f"{method}/{scoring}"}
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="the probe's output folder")
    ap.add_argument("--dest", required=True)
    ap.add_argument("--rule-from", help="folder with results_summary.json (default: --out)")
    ap.add_argument("--rule", help="BEST_MAX,RATIO instead of the calibrated rule (e.g. one checked on real photos)")
    args = ap.parse_args()
    entries = json.load(gzip.open(os.path.join(args.out, "index_entries.json.gz")))
    z = np.load(os.path.join(args.out, "index_features.npz"))
    have = np.nonzero(z["have"])[0]
    h = np.ascontiguousarray(z["h256"][have])
    oracles = [entries[i]["oracle"] for i in have]
    cards = sorted(set(oracles))
    num = {o: k for k, o in enumerate(cards)}
    card_of = np.array([num[o] for o in oracles], dtype="<u4")
    os.makedirs(args.dest, exist_ok=True)
    with open(os.path.join(args.dest, "scan_index.bin"), "wb") as f:
        f.write(b"WJS1" + struct.pack("<II", len(have), len(cards)))
        f.write(h.tobytes())
        f.write(card_of.tobytes())
    meta = {"version": 1, "cards": cards,
            "entries": [[entries[i]["set"], entries[i]["cn"], entries[i]["lang"]] for i in have],
            "rule": rule_from(args.rule_from or args.out)}
    if args.rule:
        best_max, ratio = (float(v) for v in args.rule.split(","))
        meta["rule"] = {"best_max": best_max, "ratio": ratio, "from": "given"}
    with open(os.path.join(args.dest, "scan_cards.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, separators=(",", ":"))
    print(f"{len(have):,} entries, {len(cards):,} cards, rule {meta['rule']}")


if __name__ == "__main__":
    main()
