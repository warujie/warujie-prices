"""Card-scan probe: turns a flat card picture into a believable phone photo:
the card held roughly inside the on-screen guide, tilted and turned a little,
on a table, playmat, carpet or cloth, under room light, with glare, shadow, a sleeve's haze,
blur, noise and JPEG compression. Three levels: easy, normal, hard.
"""
import numpy as np
import cv2

FRAME_W, FRAME_H = 1080, 1440            # a portrait phone camera frame
CARD_RATIO = 63 / 88
GUIDE_W = 0.74 * FRAME_W                 # the on-screen card guide
GUIDE_H = GUIDE_W / CARD_RATIO
GUIDE = (FRAME_W / 2 - GUIDE_W / 2, FRAME_H / 2 - GUIDE_H / 2, FRAME_W / 2 + GUIDE_W / 2, FRAME_H / 2 + GUIDE_H / 2)

LEVELS = {
    "easy": dict(scale=(0.95, 1.03), shift=0.02, rot=2, persp=0.015, bright=(0.9, 1.1), wb=0.05,
                 shadow=0.1, glare=0.1, glare_i=(0.1, 0.25), sleeve=0.1, foil=0.0, blur=(0.0, 0.8),
                 motion=0.0, noise=2, jpeg=(85, 92)),
    "normal": dict(scale=(0.88, 1.06), shift=0.04, rot=5, persp=0.035, bright=(0.7, 1.2), wb=0.12,
                   shadow=0.4, glare=0.5, glare_i=(0.2, 0.5), sleeve=0.3, foil=0.15, blur=(0.5, 1.8),
                   motion=0.15, noise=4, jpeg=(75, 88)),
    "hard": dict(scale=(0.8, 1.08), shift=0.07, rot=8, persp=0.06, bright=(0.45, 1.3), wb=0.2,
                 shadow=0.6, glare=0.9, glare_i=(0.4, 0.9), sleeve=0.5, foil=0.4, blur=(1.2, 3.0),
                 motion=0.4, noise=7, jpeg=(60, 80)),
}


def background(rng):
    h, w = FRAME_H, FRAME_W
    kind = rng.choice(["mat", "wood", "white", "dark", "busy", "carpet", "fabric"])
    low = cv2.resize(rng.normal(0, 1, (6, 8, 3)).astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC)
    if kind in ("carpet", "fabric"):
        # fine texture that makes many short edges: carpet loops in rows, a woven cloth
        ang = rng.uniform(0, np.pi)
        y, x = np.mgrid[0:h, 0:w].astype(np.float32)
        u = x * np.cos(ang) + y * np.sin(ang)
        v = -x * np.sin(ang) + y * np.cos(ang)
        base = rng.uniform(20, 120) * (1 + rng.uniform(-0.25, 0.25, 3))
        if kind == "carpet":
            s = rng.uniform(3, 8)
            loops = cv2.resize(rng.random((int(h / s) + 1, int(w / s) + 1)).astype(np.float32), (w, h),
                               interpolation=cv2.INTER_CUBIC)
            rows = 0.5 + 0.5 * np.sin(2 * np.pi * v / (s * rng.uniform(1.5, 3)))
            tex = (loops * rows - 0.25) * rng.uniform(60, 140)
        else:
            p = rng.uniform(3, 9)
            tex = np.sin(2 * np.pi * u / p) * np.sin(2 * np.pi * v / p) * rng.uniform(15, 45)
            tex += cv2.resize(rng.normal(0, 1, (h // 4, w // 4)).astype(np.float32), (w, h)) * 8
        img = base[None, None, :] + tex[..., None] + low * 10
        img = img.astype(np.float32) + rng.normal(0, 3, img.shape).astype(np.float32)
        return np.clip(img, 0, 255)
    if kind == "mat":
        base = rng.uniform(20, 200, 3) * np.ones((h, w, 3))
        img = base + low * 18
    elif kind == "wood":
        y = np.arange(h)[:, None] + rng.normal(0, 1, (h, 1)) * 3
        x = np.arange(w)[None, :]
        stripes = np.sin((y + 9 * np.sin(x / 60.0)) / rng.uniform(5, 14)) * 20
        base = np.array([140, 95, 60]) * rng.uniform(0.6, 1.2)
        img = base + stripes[..., None] + low * 15
    elif kind == "white":
        img = rng.uniform(200, 245) * np.ones((h, w, 3)) + low * 8
    elif kind == "dark":
        img = rng.uniform(8, 40) * np.ones((h, w, 3)) + low * 6
    else:
        img = rng.uniform(60, 180, 3) * np.ones((h, w, 3)) + low * 15
        for _ in range(int(rng.integers(4, 12))):   # other cards, dice, sleeves nearby
            c = tuple(float(v) for v in rng.uniform(0, 255, 3))
            x0, y0 = int(rng.uniform(-200, w)), int(rng.uniform(-200, h))
            cv2.rectangle(img, (x0, y0), (x0 + int(rng.uniform(80, 500)), y0 + int(rng.uniform(80, 600))), c, -1)
    img = img.astype(np.float32) + rng.normal(0, 3, img.shape).astype(np.float32)
    return np.clip(img, 0, 255)


def rounded_mask(w, h, r):
    m = np.zeros((h, w), np.uint8)
    cv2.rectangle(m, (r, 0), (w - r, h), 255, -1)
    cv2.rectangle(m, (0, r), (w, h - r), 255, -1)
    for cx, cy in ((r, r), (w - r, r), (r, h - r), (w - r, h - r)):
        cv2.circle(m, (cx, cy), r, 255, -1)
    return m


def card_corners(rng, p):
    gx0, gy0, gx1, gy1 = GUIDE
    s = rng.uniform(*p["scale"])
    w, h = GUIDE_W * s, GUIDE_H * s
    cx = FRAME_W / 2 + rng.uniform(-1, 1) * p["shift"] * GUIDE_W
    cy = FRAME_H / 2 + rng.uniform(-1, 1) * p["shift"] * GUIDE_H
    a = np.deg2rad(rng.uniform(-p["rot"], p["rot"]))
    base = np.array([[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2]])
    rot = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
    pts = base @ rot.T
    # a tilt: one edge nearer the camera than the other
    tilt = rng.uniform(-1, 1, 2) * p["persp"]
    pts[:, 0] *= 1 + tilt[1] * np.sign(base[:, 1])
    pts[:, 1] *= 1 + tilt[0] * np.sign(base[:, 0])
    pts += rng.normal(0, p["persp"] * 0.3 * w, pts.shape)
    return (pts + [cx, cy]).astype(np.float32)


def make_photo(card_rgb, level, rng):
    """card_rgb: flat card picture (any size). Returns (photo uint8 RGB, corners 4x2)."""
    p = LEVELS[level]
    ch, cw = card_rgb.shape[:2]
    card = card_rgb.astype(np.float32)

    # on the card's surface: sleeve haze, foil sheen, glare
    yy, xx = np.mgrid[0:ch, 0:cw].astype(np.float32)
    if rng.random() < p["sleeve"]:
        a = rng.uniform(0.04, 0.14)
        card = card * (1 - a) + 235 * a
    if rng.random() < p["foil"]:
        ang = rng.uniform(0, np.pi)
        t = (xx * np.cos(ang) + yy * np.sin(ang)) / max(cw, ch) * rng.uniform(2, 5) * np.pi
        rainbow = np.stack([np.sin(t), np.sin(t + 2.1), np.sin(t + 4.2)], axis=2) * 0.5 + 0.5
        a = rng.uniform(0.05, 0.2)
        card = card * (1 - a) + rainbow * 255 * a
    if rng.random() < p["glare"]:
        for _ in range(int(rng.integers(1, 3))):
            gx, gy = rng.uniform(0.1, 0.9) * cw, rng.uniform(0.1, 0.8) * ch
            rx, ry = rng.uniform(0.1, 0.45) * cw, rng.uniform(0.05, 0.3) * ch
            inten = rng.uniform(*p["glare_i"])
            g = np.exp(-(((xx - gx) / rx) ** 2 + ((yy - gy) / ry) ** 2))
            card = card + g[..., None] * inten * 255

    corners = card_corners(rng, p)
    src = np.float32([[0, 0], [cw, 0], [cw, ch], [0, ch]])
    m = cv2.getPerspectiveTransform(src, corners)
    warped = cv2.warpPerspective(np.clip(card, 0, 255), m, (FRAME_W, FRAME_H), flags=cv2.INTER_LINEAR)
    mask = cv2.warpPerspective(rounded_mask(cw, ch, int(0.035 * cw)), m, (FRAME_W, FRAME_H), flags=cv2.INTER_LINEAR)
    mask = (mask.astype(np.float32) / 255)[..., None]
    img = background(rng)
    # a soft drop shadow under the card
    sh = cv2.GaussianBlur(mask, (0, 0), 12)
    if sh.ndim == 2:
        sh = sh[..., None]
    img = img * (1 - 0.35 * np.roll(np.roll(sh, 8, 0), 6, 1))
    img = img * (1 - mask) + warped * mask

    # room light: brightness, gamma, white balance, a hand's shadow, vignette
    fy, fx = np.mgrid[0:FRAME_H, 0:FRAME_W].astype(np.float32)
    img = img * rng.uniform(*p["bright"])
    wb = 1 + rng.uniform(-1, 1, 3) * p["wb"]
    img = img * wb[None, None, :]
    if rng.random() < p["shadow"]:
        ang = rng.uniform(0, 2 * np.pi)
        t = ((fx - FRAME_W / 2) * np.cos(ang) + (fy - FRAME_H / 2) * np.sin(ang)) / FRAME_H + 0.5
        img = img * (1 - rng.uniform(0.15, 0.5) * np.clip(t, 0, 1))[..., None]
    r2 = ((fx - FRAME_W / 2) / FRAME_W) ** 2 + ((fy - FRAME_H / 2) / FRAME_H) ** 2
    img = img * (1 - 0.35 * r2)[..., None]
    gamma = rng.uniform(0.85, 1.2)
    lut = (255 * (np.arange(256) / 255.0) ** gamma).astype(np.float32)
    img = lut[np.clip(img, 0, 255).astype(np.uint8)]

    # camera: focus, shake, noise, compression
    sigma = rng.uniform(*p["blur"])
    if sigma > 0.05:
        img = cv2.GaussianBlur(img, (0, 0), sigma)
    if rng.random() < p["motion"]:
        n = int(rng.integers(5, 15))
        k = np.zeros((n, n), np.float32)
        k[n // 2, :] = 1.0 / n
        rotm = cv2.getRotationMatrix2D((n / 2 - 0.5, n / 2 - 0.5), rng.uniform(0, 180), 1)
        k = cv2.warpAffine(k, rotm, (n, n))
        k /= max(k.sum(), 1e-6)
        img = cv2.filter2D(img, -1, k)
    img = img + rng.normal(0, p["noise"], img.shape).astype(np.float32)
    img = np.clip(img, 0, 255).astype(np.uint8)
    q = int(rng.integers(*p["jpeg"]))
    ok, buf = cv2.imencode(".jpg", cv2.cvtColor(img, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, q])
    img = cv2.cvtColor(cv2.imdecode(buf, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
    return img, corners
