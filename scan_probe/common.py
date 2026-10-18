"""Shared pieces of the card-scan probe: where the art sits on a card, how a
picture of a card becomes fingerprints, and how fingerprints are compared.

Everything here works on a card seen through its four corners, so the same
code fingerprints Scryfall's flat pictures (corners = the picture's corners)
and phone photos (corners = wherever the card was found).
"""
import numpy as np
import cv2

# A card warped flat is CARD_W x CARD_H, the size of Scryfall's "normal" picture.
CARD_W, CARD_H = 488, 680

# The part of the card that is fingerprinted, as fractions of its width and
# height. It sits inside the art box of every frame (1993, 1997, 2003, 2015,
# borderless, showcase) and below the name bar, so it holds only artwork: the
# same on a Japanese and an English printing.
REGION = (0.15, 0.15, 0.85, 0.47)
REGION_W, REGION_H = 342, 218   # the region at "normal" size

USER_AGENT = "WarujieCardScanProbe/0.1 (+https://warujie.jp)"


def dct_matrix(n):
    k = np.arange(n)[:, None]
    i = np.arange(n)[None, :]
    m = np.cos(np.pi * (2 * i + 1) * k / (2 * n)) * np.sqrt(2.0 / n)
    m[0] /= np.sqrt(2.0)
    return m


D32 = dct_matrix(32)
D64 = dct_matrix(64)


def card_to_image_homography(corners):
    """corners: 4x2 (top-left, top-right, bottom-right, bottom-left) in the image."""
    src = np.float32([[0, 0], [CARD_W, 0], [CARD_W, CARD_H], [0, CARD_H]])
    return cv2.getPerspectiveTransform(src, np.float32(corners))


def warp_region(img, corners, out_w=REGION_W, out_h=REGION_H):
    """The fingerprint region of the card whose corners are given, flattened to
    out_w x out_h. Warps at the photo's own resolution first, then shrinks by
    area averaging, so a large photo isn't aliased."""
    corners = np.float32(corners)
    card_px = (np.linalg.norm(corners[1] - corners[0]) + np.linalg.norm(corners[2] - corners[3])) / 2
    scale = max(1.0, card_px / CARD_W)
    ww, hh = int(round(out_w * scale)), int(round(out_h * scale))
    x0, y0, x1, y1 = REGION
    # region pixel (u, v) -> card point -> image point
    t = np.array([[(x1 - x0) * CARD_W / ww, 0, x0 * CARD_W],
                  [0, (y1 - y0) * CARD_H / hh, y0 * CARD_H],
                  [0, 0, 1]], dtype=np.float64)
    m = card_to_image_homography(corners).astype(np.float64) @ t
    big = cv2.warpPerspective(img, m, (ww, hh), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                              borderMode=cv2.BORDER_REPLICATE)
    if (ww, hh) != (out_w, out_h):
        big = cv2.resize(big, (out_w, out_h), interpolation=cv2.INTER_AREA)
    return big


def flat_corners(img):
    h, w = img.shape[:2]
    return np.float32([[0, 0], [w, 0], [w, h], [0, h]])


def to_gray(rgb):
    rgb = rgb.astype(np.float32)
    return rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114


def dct_block(gray, n, k):
    small = cv2.resize(gray, (n, n), interpolation=cv2.INTER_AREA).astype(np.float64)
    d = D64 if n == 64 else D32
    return (d @ small @ d.T)[:k, :k].flatten()


def phash_bits(gray, n, k):
    block = dct_block(gray, n, k)
    med = np.median(block[1:])
    return np.packbits(block > med)


def dhash_bits(gray, axis):
    """Signs of neighbour differences on a 16 x 16 grid (256 bits): a tone
    curve (the phone's own processing, dim light) keeps their order."""
    if axis == 1:
        s = cv2.resize(gray, (17, 16), interpolation=cv2.INTER_AREA)
        return np.packbits((s[:, 1:] > s[:, :-1]).flatten())
    s = cv2.resize(gray, (16, 17), interpolation=cv2.INTER_AREA)
    return np.packbits((s[1:, :] > s[:-1, :]).flatten())


CLAHE = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
RELIABLE = 160   # h256m marks the 160 of 256 hash bits furthest from the median


def colour_sig(rgb):
    """4x4 grid of chroma (r and g share of r+g+b) after a grey-world white
    balance, 32 bytes. Survives dim or warm light better than raw colour."""
    s = cv2.resize(rgb.astype(np.float32), (4, 4), interpolation=cv2.INTER_AREA).astype(np.float64) + 1.0
    s = s / s.reshape(-1, 3).mean(axis=0) * s.mean()   # grey-world balance (exact: means are linear)
    tot = s.sum(axis=2, keepdims=True)
    ch = s[..., :2] / tot
    return np.clip(np.round(ch * 255), 0, 255).astype(np.uint8).reshape(-1)


def region_features(region_rgb):
    g = to_gray(region_rgb)
    g8 = np.clip(g + 0.5, 0, 255).astype(np.uint8)
    block = dct_block(g, 64, 16)
    med = np.median(block[1:])
    dev = np.abs(block - med)
    dev[0] = 0
    b12 = dct_block(g, 64, 12)
    return {
        "h256": np.packbits(block > med),                     # 32 bytes
        "h64": phash_bits(g, 32, 8),                          # 8 bytes
        "col": colour_sig(region_rgb),                        # 32 bytes
        # round 3 candidates, compared on the owner's real photos
        "h256m": np.packbits(dev >= np.sort(dev)[-RELIABLE]),  # which h256 bits are reliable
        "h144": np.packbits(b12 > np.median(b12[1:])),        # lower frequencies only, 18 bytes
        "h256eq": phash_bits(cv2.equalizeHist(g8).astype(np.float32), 64, 16),
        "h256cl": phash_bits(CLAHE.apply(g8).astype(np.float32), 64, 16),
        "dh256": dhash_bits(g, 1),
        "dv256": dhash_bits(g, 0),
    }


def hamming(packed_query, packed_index):
    """packed_query: (B,) uint8; packed_index: (N, B) uint8 -> (N,) distances."""
    x = np.bitwise_xor(packed_index, packed_query[None, :])
    return np.bitwise_count(x).sum(axis=1)


def colour_dist(q, index):
    return np.abs(index.astype(np.int16) - q.astype(np.int16)[None, :]).sum(axis=1)


def jitter_corners(corners, shifts, scales):
    """Variants of a found card: moved by each shift (fractions of the card's
    size) and scaled about its centre, for a search that forgives a card found
    a little off."""
    c = np.float32(corners)
    centre = c.mean(axis=0)
    ex = (c[1] - c[0] + c[2] - c[3]) / 2   # along the width
    ey = (c[3] - c[0] + c[2] - c[1]) / 2   # along the height
    out = []
    for s in scales:
        base = centre + (c - centre) * s
        for dx in shifts:
            for dy in shifts:
                out.append(base + ex * dx + ey * dy)
    return out


# ImageNet input for the image models
IMNET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMNET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def model_input(region_rgb, size=224):
    x = cv2.resize(region_rgb, (size, size), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    x = (x - IMNET_MEAN) / IMNET_STD
    return x.transpose(2, 0, 1)
