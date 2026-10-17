"""Card-scan probe, step 1 and 2: choose which card pictures make the index,
download them from Scryfall's image server (once; they are kept in the
Actions cache between runs) and fingerprint them.

  python scan_probe/build_index.py select     --out OUT [--bulk FILE]
  python scan_probe/build_index.py download   --out OUT --cache DIR [--budget-min N]
  python scan_probe/build_index.py fingerprint --out OUT --cache DIR

The index has one entry per distinct look of an artwork: printings that share
the illustration, frame, border and frame effects share one entry, so a
common reprinted twenty times is downloaded once. English pictures are used
where they exist; Japanese pictures where the art is Japanese-only, and also
for card shapes whose fingerprint region holds rules text (sagas, split and
flip cards), since there the language changes the picture.
"""
import argparse
import gzip
import io
import json
import os
import random
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import USER_AGENT, flat_corners, warp_region, region_features, model_input  # noqa: E402

BULK_DATA_ENDPOINT = "https://api.scryfall.com/bulk-data"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}

# the same exclusions as the site's card database (tools/build_ja_database.py)
EXCLUDED_LAYOUTS = {"token", "double_faced_token", "emblem", "art_series", "vanguard", "planar", "scheme"}
EXCLUDED_SET_TYPES = {"token", "memorabilia", "minigame", "alchemy"}
# shapes whose fingerprint region shows rules text, so each language looks different
TEXT_IN_REGION = {"saga", "split", "flip", "case", "class"}

HERE = os.path.dirname(os.path.abspath(__file__))


def log(*a):
    print(*a, flush=True)


# ---- choosing the pictures -----------------------------------------------------------

def bulk_url():
    req = urllib.request.Request(BULK_DATA_ENDPOINT, headers=HEADERS)
    with urllib.request.urlopen(req) as r:
        manifest = json.load(r)
    for e in manifest["data"]:
        if e.get("type") == "all_cards":
            if "jsonl_download_uri" in e:
                return e["jsonl_download_uri"], True
            return e["download_uri"], False
    raise RuntimeError("no all_cards entry")


def iter_cards(path_or_url):
    if os.path.exists(path_or_url):
        opener = open(path_or_url, "rb")
        is_jsonl = path_or_url.endswith(".jsonl.gz") or path_or_url.endswith(".jsonl")
        gz = path_or_url.endswith(".gz")
    else:
        url, is_jsonl = bulk_url()
        log("bulk:", url)
        opener = urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS))
        gz = is_jsonl
    with opener as raw:
        stream = gzip.GzipFile(fileobj=raw) if gz else raw
        if is_jsonl:
            for line in io.TextIOWrapper(stream, encoding="utf-8"):
                line = line.strip()
                if line:
                    yield json.loads(line)
        else:
            for c in json.load(stream):
                yield c


def oracle_id_of(c):
    if c.get("oracle_id"):
        return c["oracle_id"]
    faces = c.get("card_faces") or []
    return faces[0].get("oracle_id") if faces else None


def excluded(c):
    return (c.get("layout") in EXCLUDED_LAYOUTS or c.get("set_type") in EXCLUDED_SET_TYPES
            or c.get("digital") or c.get("type_line", "").startswith("Token")
            or "paper" not in (c.get("games") or []))


def faces_with_pictures(c):
    if c.get("image_uris"):
        return [(0, c["image_uris"], c.get("illustration_id"))]
    out = []
    for i, f in enumerate(c.get("card_faces") or []):
        if f.get("image_uris"):
            out.append((i, f["image_uris"], f.get("illustration_id")))
    return out


def picture_rank(r):
    """Better picture first: real scan, regular printing, newest."""
    return (r["status"] == "highres_scan", not r["promo"], r["released"])


def cmd_select(args):
    site = set(json.load(gzip.open(os.path.join(HERE, "site_oracles.json.gz"))))
    log("site cards:", len(site))
    recs = []
    seen = 0
    for c in iter_cards(args.bulk or ""):
        seen += 1
        if c.get("lang") not in ("en", "ja") or excluded(c):
            continue
        oid = oracle_id_of(c)
        if oid not in site:
            continue
        status = c.get("image_status")
        if status in ("missing", "placeholder") or not status:
            continue
        for fi, uris, ill in faces_with_pictures(c):
            if not uris.get("small") or not uris.get("normal"):
                continue
            recs.append({
                "id": c["id"], "face": fi, "oracle": oid, "name": c.get("name"), "lang": c["lang"],
                "set": c.get("set"), "cn": c.get("collector_number"), "layout": c.get("layout"),
                "frame": c.get("frame"), "border": c.get("border_color"), "full_art": bool(c.get("full_art")),
                "effects": sorted(c.get("frame_effects") or []), "textless": bool(c.get("textless")),
                "promo": bool(c.get("promo")), "released": c.get("released_at", ""), "status": status,
                "ill": ill, "basic": c.get("type_line", "").startswith("Basic Land"),
                "small": uris["small"], "normal": uris["normal"],
            })
        if seen % 100000 == 0:
            log(f"  read {seen:,}, kept {len(recs):,}")
    log(f"read {seen:,} printings, kept {len(recs):,} en/ja faces with a picture")

    # Japanese printings without an illustration id borrow the English one of the same set and number
    en_ill = {(r["set"], r["cn"], r["face"]): r["ill"] for r in recs if r["lang"] == "en" and r["ill"]}
    borrowed = 0
    for r in recs:
        if not r["ill"]:
            r["ill"] = en_ill.get((r["set"], r["cn"], r["face"]))
            if r["ill"]:
                borrowed += 1
            else:
                r["ill"] = "card:" + r["id"]
    log("illustration ids borrowed from English:", borrowed)

    groups = {}
    for r in recs:
        key = (r["ill"], r["frame"], r["border"], r["full_art"], tuple(r["effects"]), r["textless"], r["layout"], r["face"])
        groups.setdefault(key, []).append(r)

    entries = []
    for key, rs in groups.items():
        en = sorted([r for r in rs if r["lang"] == "en"], key=picture_rank, reverse=True)
        ja = sorted([r for r in rs if r["lang"] == "ja"], key=picture_rank, reverse=True)
        oracles = sorted({r["oracle"] for r in rs})
        base = {"group": len(entries), "oracles": oracles, "printings": len(rs)}
        if en:
            entries.append(dict(en[0], **base, kind="en", ja_alt=(ja[0]["id"] if ja else None)))
            if ja and en[0]["layout"] in TEXT_IN_REGION and ja[0]["status"] == "highres_scan":
                entries.append(dict(ja[0], **base, kind="ja_text"))
        elif ja:
            entries.append(dict(ja[0], **base, kind="ja_only"))
    log(f"groups: {len(groups):,}; index entries: {len(entries):,}")
    kinds = {}
    for e in entries:
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    log("entry kinds:", kinds)

    # test sample: printings whose normal-size picture is downloaded to make test photos
    rng = random.Random(20261017)
    by_id = {(r["id"], r["face"]): r for r in recs}
    en_entries = [e for e in entries if e["kind"] == "en"]
    used = set()
    tests = []

    def take(category, pool, n, query_of=lambda e: e):
        pool = [e for e in pool if e["group"] not in used]
        rng.shuffle(pool)
        for e in pool[:n]:
            q = query_of(e)
            if q is None:
                continue
            used.add(e["group"])
            tests.append({"category": category, "group": e["group"], "oracle": e["oracle"], "id": q["id"],
                          "face": q["face"], "lang": q["lang"], "name": q["name"], "set": q["set"],
                          "normal": q["normal"]})

    def ja_of(e):
        if not e.get("ja_alt"):
            return None
        q = by_id.get((e["ja_alt"], e["face"]))
        return q if q and q["status"] in ("highres_scan", "lowres") else None

    take("ja_same_art", [e for e in en_entries if e.get("ja_alt") and e["layout"] not in TEXT_IN_REGION], 450, ja_of)
    take("ja_only_art", [e for e in entries if e["kind"] == "ja_only" and e["status"] == "highres_scan"], 150)
    take("old_frame", [e for e in en_entries if e["frame"] in ("1993", "1997")], 200)
    take("special_frame", [e for e in en_entries if e["border"] == "borderless" or e["full_art"]
                           or set(e["effects"]) & {"showcase", "extendedart", "etched", "inverted"}], 200)
    take("back_face", [e for e in en_entries if e["face"] == 1], 100)
    take("basic_land", [e for e in en_entries if e["basic"]], 100)
    take("odd_shape", [e for e in entries if e["layout"] in TEXT_IN_REGION | {"adventure", "prototype", "leveler", "mutate"}], 100)
    take("random", en_entries, 1200)
    log("test sample:", len(tests))

    os.makedirs(args.out, exist_ok=True)
    keep = ("group", "kind", "id", "face", "oracle", "oracles", "name", "lang", "set", "cn", "layout", "frame",
            "border", "full_art", "effects", "status", "basic", "printings", "small")
    with gzip.open(os.path.join(args.out, "index_entries.json.gz"), "wt", encoding="utf-8") as f:
        json.dump([{k: e.get(k) for k in keep} for e in entries], f, ensure_ascii=False)
    with open(os.path.join(args.out, "test_sample.json"), "w", encoding="utf-8") as f:
        json.dump(tests, f, ensure_ascii=False, indent=0)
    with open(os.path.join(args.out, "select_summary.json"), "w") as f:
        json.dump({"printings_read": seen, "faces_kept": len(recs), "groups": len(groups),
                   "entries": len(entries), "kinds": kinds, "tests": len(tests)}, f, indent=1)


# ---- downloading ------------------------------------------------------------------------

class Pacer:
    """At most `rate` requests a second over all threads."""
    def __init__(self, rate):
        self.gap = 1.0 / rate
        self.next = time.monotonic()
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            now = time.monotonic()
            t = max(now, self.next)
            self.next = t + self.gap
        time.sleep(max(0.0, t - now))


def picture_path(cache, size, pid, face):
    return os.path.join(cache, size, pid[:2], f"{pid}_{face}.jpg")


def cmd_download(args):
    entries = json.load(gzip.open(os.path.join(args.out, "index_entries.json.gz")))
    tests = json.load(open(os.path.join(args.out, "test_sample.json"), encoding="utf-8"))
    jobs = [(e["small"], picture_path(args.cache, "small", e["id"], e["face"])) for e in entries]
    jobs += [(t["normal"], picture_path(args.cache, "normal", t["id"], t["face"])) for t in tests]
    todo = [j for j in jobs if not os.path.exists(j[1])]
    log(f"pictures: {len(jobs):,}, already cached: {len(jobs) - len(todo):,}, to fetch: {len(todo):,}")
    pacer = Pacer(args.rate)
    deadline = time.monotonic() + args.budget_min * 60
    stats = {"ok": 0, "failed": 0, "bytes": 0}
    lock = threading.Lock()
    stop = threading.Event()

    def fetch(job):
        url, path = job
        if stop.is_set() or time.monotonic() > deadline:
            stop.set()
            return
        for attempt in range(4):
            pacer.wait()
            try:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "image/*"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = r.read()
                if len(data) < 500:
                    raise ValueError("tiny file")
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path + ".part", "wb") as f:
                    f.write(data)
                os.replace(path + ".part", path)
                with lock:
                    stats["ok"] += 1
                    stats["bytes"] += len(data)
                    if stats["ok"] % 2000 == 0:
                        log(f"  fetched {stats['ok']:,} ({stats['bytes'] / 1e6:,.0f} MB)")
                return
            except Exception as ex:  # noqa: BLE001
                code = getattr(ex, "code", None)
                if code == 429:
                    time.sleep(30)
                elif code == 404:
                    break
                else:
                    time.sleep(2 * (attempt + 1))
        with lock:
            stats["failed"] += 1

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.threads) as pool:
        list(pool.map(fetch, todo))
    left = sum(1 for j in jobs if not os.path.exists(j[1]))
    log(f"fetched {stats['ok']:,} ({stats['bytes'] / 1e6:,.0f} MB) in {time.time() - t0:,.0f} s; "
        f"failed {stats['failed']:,}; still missing {left:,}" + ("; stopped at the time budget" if stop.is_set() else ""))
    with open(os.path.join(args.out, "download_summary.json"), "w") as f:
        json.dump(dict(stats, missing=left, total=len(jobs), seconds=round(time.time() - t0)), f, indent=1)


# ---- fingerprinting ---------------------------------------------------------------------

def read_rgb(path):
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        return None
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def load_models(models_dir):
    sessions = {}
    try:
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = int(os.environ.get("ORT_THREADS", "4"))
        for name in ("mnv3s", "mnv3l"):
            p = os.path.join(models_dir, name + ".onnx")
            if os.path.exists(p):
                sessions[name] = ort.InferenceSession(p, opts, providers=["CPUExecutionProvider"])
    except Exception as ex:  # noqa: BLE001
        log("no image models:", ex)
    return sessions


def pca_space(e, have, dims=256):
    """Model features -> unit length -> centred -> the 256 main directions
    (fitted on up to 30,000 entries) -> unit length again. Only this compact
    form is kept: the first 64 of the 256 numbers, or their signs, are the
    smaller forms a phone could load."""
    e = e / (np.linalg.norm(e, axis=1, keepdims=True) + 1e-6)
    mean = e[have].mean(axis=0)
    idx = np.nonzero(have)[0]
    sample = e[np.random.default_rng(0).choice(idx, min(len(idx), 30000), replace=False)] - mean
    _, _, vt = np.linalg.svd(sample, full_matrices=False)
    vt = vt[:dims].astype(np.float32)
    p = (e - mean) @ vt.T
    p /= np.linalg.norm(p, axis=1, keepdims=True) + 1e-6
    return mean.astype(np.float32), vt, p


def cmd_fingerprint(args):
    entries = json.load(gzip.open(os.path.join(args.out, "index_entries.json.gz")))
    n = len(entries)
    h256 = np.zeros((n, 32), np.uint8)
    h64 = np.zeros((n, 8), np.uint8)
    col = np.zeros((n, 32), np.uint8)
    have = np.zeros(n, bool)
    sessions = load_models(os.path.join(args.out, "models"))
    emb = {k: [None] * n for k in sessions}
    batch, batch_idx = [], []

    def flush():
        if not batch:
            return
        x = np.stack(batch).astype(np.float32)
        for k, s in sessions.items():
            y = s.run(None, {s.get_inputs()[0].name: x})[0]
            for j, i in enumerate(batch_idx):
                emb[k][i] = y[j].astype(np.float32)
        batch.clear()
        batch_idx.clear()

    t0 = time.time()
    for i, e in enumerate(entries):
        img = read_rgb(picture_path(args.cache, "small", e["id"], e["face"]))
        if img is None:
            continue
        reg = warp_region(img, flat_corners(img))
        f = region_features(reg)
        h256[i], h64[i], col[i] = f["h256"], f["h64"], f["col"]
        have[i] = True
        if sessions:
            batch.append(model_input(reg))
            batch_idx.append(i)
            if len(batch) == 64:
                flush()
        if i % 10000 == 0:
            log(f"  fingerprinted {i:,}/{n:,} ({time.time() - t0:,.0f} s)")
    flush()
    out = {"h256": h256, "h64": h64, "col": col, "have": have}
    for k in sessions:
        dim = next((v.shape[0] for v in emb[k] if v is not None), 0)
        e = np.stack([v if v is not None else np.zeros(dim, np.float32) for v in emb[k]]).astype(np.float32)
        mean, vt, p = pca_space(e, have)
        out[f"pca_{k}_mean"], out[f"pca_{k}_vt"] = mean, vt
        out[f"pca_{k}_p256"] = np.clip(np.round(p * 127), -127, 127).astype(np.int8)
    np.savez_compressed(os.path.join(args.out, "index_features.npz"), **out)
    log(f"fingerprinted {int(have.sum()):,} of {n:,} entries in {time.time() - t0:,.0f} s; models: {list(sessions)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["select", "download", "fingerprint"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--cache", default="scan_cache")
    ap.add_argument("--bulk")
    ap.add_argument("--budget-min", type=float, default=230)
    ap.add_argument("--rate", type=float, default=10.0)
    ap.add_argument("--threads", type=int, default=4)
    args = ap.parse_args()
    {"select": cmd_select, "download": cmd_download, "fingerprint": cmd_fingerprint}[args.cmd](args)


if __name__ == "__main__":
    main()
