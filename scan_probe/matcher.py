"""Card-scan probe: the index in memory, and matching one photo against it
with each way of scoring, so they can be compared on the same photos."""
import gzip
import json
import os

import numpy as np
import cv2

from common import CARD_W, warp_region, region_features, hamming, colour_dist, model_input, jitter_corners


USE_MODELS = ("mnv3s",)   # round 1: the large model was no better and is 3x the size

# shifts and scales tried around a found card (fractions of its size)
FOUND_SHIFTS, FOUND_SCALES = (-0.015, 0.0, 0.015), (0.96, 1.0, 1.04, 1.08)
# round 2: smaller steps, tried around each of a few outlines
NEAR_SHIFTS, NEAR_SCALES = (-0.012, 0.0, 0.012), (0.97, 1.0, 1.03)
# a card's black border, as a share of the width / height inside it: when the
# table is dark the border's inner edge is the one found
BORDER_X, BORDER_Y = 0.0365, 0.0252
# around the guide alone, when no card outline was found
GUIDE_SHIFTS, GUIDE_SCALES = (-0.06, -0.03, 0.0, 0.03, 0.06), (0.88, 0.94, 1.0, 1.06)


class Index:
    def __init__(self, out_dir, models=True, threads=1):
        self.entries = json.load(gzip.open(os.path.join(out_dir, "index_entries.json.gz")))
        z = np.load(os.path.join(out_dir, "index_features.npz"))
        keep = z["have"]
        self.rows = np.nonzero(keep)[0]
        self.h256 = z["h256"][keep].view(np.uint64)          # (N, 4)
        self.h64 = z["h64"][keep].view(np.uint64)            # (N, 1)
        self.col = z["col"][keep]
        oracles = [self.entries[i]["oracle"] for i in self.rows]
        self.oracle_names = sorted(set(oracles))
        oid = {o: k for k, o in enumerate(self.oracle_names)}
        self.oracle_id_to_index = oid
        self.entry_oracle = np.array([oid[o] for o in oracles])
        self.order = np.argsort(self.entry_oracle, kind="stable")
        so = self.entry_oracle[self.order]
        self.seg_starts = np.r_[0, np.nonzero(np.diff(so))[0] + 1]
        self.seg_oracle = so[self.seg_starts]
        self.emb = {}
        self.sessions = {}
        for key in z.files:
            if not (key.startswith("pca_") and key.endswith("_p256")):
                continue
            name = key[4:-5]
            p = z[key][keep].astype(np.float32) / 127.0
            p /= np.linalg.norm(p, axis=1, keepdims=True) + 1e-6
            p64 = p[:, :64] / (np.linalg.norm(p[:, :64], axis=1, keepdims=True) + 1e-6)
            vt = z[f"pca_{name}_vt"]
            self.emb[name] = {"mean": z[f"pca_{name}_mean"], "vt": vt,
                              "spaces": {256: (vt, p), 64: (vt[:64], p64)},
                              "bits": np.packbits(p > 0, axis=1).view(np.uint64)}
        self.out_dir = out_dir
        if models:
            self.open_models(threads)

    def open_models(self, threads=1):
        """The image models, opened separately so worker processes open their own."""
        if not self.emb:
            return
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = threads
        opts.inter_op_num_threads = 1
        for name in self.emb:
            if name not in USE_MODELS:
                continue
            p = os.path.join(self.out_dir, "models", name + ".onnx")
            if os.path.exists(p):
                self.sessions[name] = ort.InferenceSession(p, opts, providers=["CPUExecutionProvider"])

    def per_oracle(self, d):
        """Lowest score of each card (its best-matching entry)."""
        return np.minimum.reduceat(d[self.order], self.seg_starts)

    def embed(self, regions):
        out = {}
        for name, s in self.sessions.items():
            x = np.stack([model_input(r) for r in regions]).astype(np.float32)
            y = s.run(None, {s.get_inputs()[0].name: x})[0].astype(np.float32)
            y /= np.linalg.norm(y, axis=1, keepdims=True) + 1e-6
            out[name] = y
        return out

    def distances(self, photo, variants, emb_variants):
        """Every scoring's distance to every index entry, lowest over the variants."""
        # shrink a big photo once so the card is about "normal" size, as the phone will
        c0 = np.float32(variants[0])
        card_px = (np.linalg.norm(c0[1] - c0[0]) + np.linalg.norm(c0[2] - c0[3])) / 2
        f = 1.15 * CARD_W / card_px
        if f < 1:
            photo = cv2.resize(photo, (int(round(photo.shape[1] * f)), int(round(photo.shape[0] * f))),
                               interpolation=cv2.INTER_AREA)
            variants = [np.float32(v) * f for v in variants]
        h256 = np.full(len(self.rows), 10 ** 6, np.int64)
        h64 = h256.copy()
        col = h256.copy()
        regions = []
        for c in variants:
            reg = warp_region(photo, c)
            regions.append(reg)
            f = region_features(reg)
            q256 = f["h256"].view(np.uint64)
            q64 = f["h64"].view(np.uint64)
            np.minimum(h256, np.bitwise_count(self.h256 ^ q256[None, :]).sum(axis=1, dtype=np.int64), out=h256)
            np.minimum(h64, np.bitwise_count(self.h64 ^ q64[None, :]).sum(axis=1, dtype=np.int64), out=h64)
            np.minimum(col, colour_dist(f["col"], self.col), out=col)
        d = {"h64": h64.astype(np.float32), "h256": h256.astype(np.float32), "col": col.astype(np.float32)}
        if self.sessions and emb_variants:
            embs = self.embed([regions[i] for i in emb_variants])
            for name, q in embs.items():
                info = self.emb[name]
                qc = q - info["mean"]
                for dim, (vt, idx) in info["spaces"].items():
                    p = qc @ vt.T
                    p /= np.linalg.norm(p, axis=1, keepdims=True) + 1e-6
                    d[f"{name}_p{dim}"] = (1 - (idx @ p.T).max(axis=1)).astype(np.float32)
                qb = np.packbits((qc @ info["vt"].T) > 0, axis=1).view(np.uint64)
                best = None
                for row in qb:
                    hd = np.bitwise_count(info["bits"] ^ row[None, :]).sum(axis=1, dtype=np.int64)
                    best = hd if best is None else np.minimum(best, hd)
                d[f"{name}_b256"] = best.astype(np.float32)
        return d

    @staticmethod
    def scorings(d):
        """The ways of scoring compared: the hash, the small image model, and
        the two added (each divided by its median so they mix on one scale)."""
        med = {k: float(np.median(v)) or 1.0 for k, v in d.items()}
        n = {k: v / med[k] for k, v in d.items()}
        s = {k: d[k] for k in ("h256", "mnv3s_p256", "mnv3s_b256") if k in d}
        if "mnv3s_p256" in n:
            s["h256+mnv3s"] = n["h256"] + n["mnv3s_p256"]
            s["h256+mnv3sb"] = n["h256"] + n["mnv3s_b256"]
        return s

    def rank(self, scores, true_oracle=None, top=5):
        """For one scoring: the best cards, their scores, and where the true card came."""
        po = self.per_oracle(scores)
        k = min(top, len(po) - 1)
        part = np.argpartition(po, k)[:k + 1]
        part = part[np.argsort(po[part])]
        res = {"top": [int(self.seg_oracle[i]) for i in part[:top]], "s": [float(po[i]) for i in part[:top]]}
        if true_oracle is not None:
            pos = np.nonzero(self.seg_oracle == true_oracle)[0]
            if pos.size:
                t = po[pos[0]]
                res["true_rank"] = int((po < t).sum())
                res["true_s"] = float(t)
        return res

    def oracle_index(self, oracle_id):
        return self.oracle_id_to_index.get(oracle_id)


def found_variants(corners):
    return jitter_corners(corners, FOUND_SHIFTS, FOUND_SCALES)


def expand_border(corners):
    """The outline one black border further out, in the card's own perspective."""
    src = np.float32([[0, 0], [1, 0], [1, 1], [0, 1]])
    m = cv2.getPerspectiveTransform(src, np.float32(corners))
    pts = np.float32([[-BORDER_X, -BORDER_Y], [1 + BORDER_X, -BORDER_Y], [1 + BORDER_X, 1 + BORDER_Y], [-BORDER_X, 1 + BORDER_Y]])
    return cv2.perspectiveTransform(pts[None], m)[0]


def outline_hypotheses(quads):
    """What matching tries: the best outline, it one border further out, and
    the second-best outline."""
    if not quads:
        return []
    hyp = [quads[0], expand_border(quads[0])]
    hyp += quads[1:2]
    return hyp


def near_variants(hyps):
    out = []
    for q in hyps:
        out += jitter_corners(q, NEAR_SHIFTS, NEAR_SCALES)
    return out


def guide_variants(guide):
    x0, y0, x1, y1 = guide
    c = np.float32([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])
    return jitter_corners(c, GUIDE_SHIFTS, GUIDE_SCALES)


def centre_and_cross(shifts, scales):
    """Indexes (in jitter_corners order) of the unshifted variant at scale 1 and
    its four neighbours, for the image models (which forgive small shifts)."""
    n = len(shifts)
    mid = shifts.index(0.0)
    base = scales.index(1.0) * n * n
    at = lambda i, j: base + i * n + j  # noqa: E731
    return [at(mid, mid), at(mid - 1, mid), at(mid + 1, mid), at(mid, mid - 1), at(mid, mid + 1)]
