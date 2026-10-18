// Card-scan probe: the fingerprint in plain JavaScript, written to give the
// same bits as common.py, so the site can fingerprint camera frames against
// an index built in Python. No libraries; works on RGBA pixel arrays
// (canvas getImageData) or RGB arrays.

export const CARD_W = 488, CARD_H = 680;
export const REGION = [0.15, 0.15, 0.85, 0.47];
export const REGION_W = 342, REGION_H = 218;

// 3x3 homography taking (0,0) (W,0) (W,H) (0,H) to the four corners
export function homography(corners, W = CARD_W, H = CARD_H) {
  const src = [[0, 0], [W, 0], [W, H], [0, H]];
  const A = [], b = [];
  for (let i = 0; i < 4; i++) {
    const [x, y] = src[i], [u, v] = corners[i];
    A.push([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.push(u);
    A.push([0, 0, 0, x, y, 1, -v * x, -v * y]); b.push(v);
  }
  const h = solve(A, b);
  return [[h[0], h[1], h[2]], [h[3], h[4], h[5]], [h[6], h[7], 1]];
}

function solve(A, b) {   // Gaussian elimination with partial pivoting
  const n = b.length, M = A.map((r, i) => [...r, b[i]]);
  for (let c = 0; c < n; c++) {
    let p = c;
    for (let r = c + 1; r < n; r++) if (Math.abs(M[r][c]) > Math.abs(M[p][c])) p = r;
    [M[c], M[p]] = [M[p], M[c]];
    for (let r = 0; r < n; r++) {
      if (r === c) continue;
      const f = M[r][c] / M[c][c];
      for (let k = c; k <= n; k++) M[r][k] -= f * M[c][k];
    }
  }
  return M.map((r, i) => r[n] / r[i]);
}

// the fingerprint region of the card, flattened: like cv2.warpPerspective
// (bilinear, pixel centres on integers, edges repeated), at the photo's own
// resolution, then shrunk by area averaging (cv2.INTER_AREA)
export function warpRegion(px, w, h, ch, corners) {
  const d = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
  const cardPx = (d(corners[1], corners[0]) + d(corners[2], corners[3])) / 2;
  const scale = Math.max(1, cardPx / CARD_W);
  const ww = Math.round(REGION_W * scale), hh = Math.round(REGION_H * scale);
  const [x0, y0, x1, y1] = REGION;
  const sx = (x1 - x0) * CARD_W / ww, sy = (y1 - y0) * CARD_H / hh;
  const M = homography(corners);
  const out = new Float32Array(ww * hh * 3);
  const at = (x, y, k) => px[(Math.min(h - 1, Math.max(0, y)) * w + Math.min(w - 1, Math.max(0, x))) * ch + k];
  for (let v = 0; v < hh; v++) {
    const cy = y0 * CARD_H + v * sy;
    for (let u = 0; u < ww; u++) {
      const cx = x0 * CARD_W + u * sx;
      const z = M[2][0] * cx + M[2][1] * cy + M[2][2];
      const X = (M[0][0] * cx + M[0][1] * cy + M[0][2]) / z;
      const Y = (M[1][0] * cx + M[1][1] * cy + M[1][2]) / z;
      const xi = Math.floor(X), yi = Math.floor(Y), fx = X - xi, fy = Y - yi;
      for (let k = 0; k < 3; k++) {
        const top = at(xi, yi, k) * (1 - fx) + at(xi + 1, yi, k) * fx;
        const bot = at(xi, yi + 1, k) * (1 - fx) + at(xi + 1, yi + 1, k) * fx;
        out[(v * ww + u) * 3 + k] = top * (1 - fy) + bot * fy;
      }
    }
  }
  return ww === REGION_W && hh === REGION_H ? out : areaResize(out, ww, hh, 3, REGION_W, REGION_H);
}

// area-average shrink (each output pixel averages the input area it covers)
export function areaResize(src, w, h, ch, W, H) {
  const out = new Float32Array(W * H * ch);
  const fx = w / W, fy = h / H;
  const spans = (n, f, N) => {   // for each output index, [index, weight] pairs
    const r = [];
    for (let o = 0; o < N; o++) {
      const a = o * f, b = Math.min(n, (o + 1) * f), s = [];
      for (let i = Math.floor(a); i < Math.ceil(b); i++) {
        const wgt = Math.min(b, i + 1) - Math.max(a, i);
        if (wgt > 1e-9) s.push([i, wgt / (b - a)]);
      }
      r.push(s);
    }
    return r;
  };
  const sxs = spans(w, fx, W), sys = spans(h, fy, H);
  for (let Y = 0; Y < H; Y++) for (let X = 0; X < W; X++) for (let k = 0; k < ch; k++) {
    let acc = 0;
    for (const [y, wy] of sys[Y]) for (const [x, wx] of sxs[X]) acc += src[(y * w + x) * ch + k] * wy * wx;
    out[(Y * W + X) * ch + k] = acc;
  }
  return out;
}

const dctCache = {};
function dctMatrix(n) {
  if (dctCache[n]) return dctCache[n];
  const m = new Float64Array(n * n);
  for (let k = 0; k < n; k++) for (let i = 0; i < n; i++)
    m[k * n + i] = Math.cos(Math.PI * (2 * i + 1) * k / (2 * n)) * Math.sqrt(2 / n) / (k === 0 ? Math.SQRT2 : 1);
  return (dctCache[n] = m);
}

// 256-bit DCT hash of an RGB region (REGION_W x REGION_H), as 8 32-bit words,
// most significant bit first (numpy.packbits order)
export function hash256(region) {
  const n = 64, k = 16, N = REGION_W * REGION_H;
  const g = new Float32Array(N);
  for (let i = 0; i < N; i++) g[i] = region[i * 3] * 0.299 + region[i * 3 + 1] * 0.587 + region[i * 3 + 2] * 0.114;
  const s = areaResize(g, REGION_W, REGION_H, 1, n, n);
  const D = dctMatrix(n);
  // c = D s D^T, only the top-left k x k block
  const t = new Float64Array(k * n);
  for (let a = 0; a < k; a++) for (let j = 0; j < n; j++) {
    let acc = 0;
    for (let i = 0; i < n; i++) acc += D[a * n + i] * s[i * n + j];
    t[a * n + j] = acc;
  }
  const c = new Float64Array(k * k);
  for (let a = 0; a < k; a++) for (let b = 0; b < k; b++) {
    let acc = 0;
    for (let j = 0; j < n; j++) acc += t[a * n + j] * D[b * n + j];
    c[a * k + b] = acc;
  }
  const rest = Array.from(c.subarray(1)).sort((x, y) => x - y);
  const med = (rest[(rest.length - 1) >> 1] + rest[rest.length >> 1]) / 2;
  const words = new Uint32Array(8);
  for (let i = 0; i < 256; i++) if (c[i] > med) words[i >> 5] |= 1 << (31 - (i & 31));
  return words;
}

export function popcount32(x) {
  x -= (x >>> 1) & 0x55555555;
  x = (x & 0x33333333) + ((x >>> 2) & 0x33333333);
  return (((x + (x >>> 4)) & 0x0f0f0f0f) * 0x01010101) >>> 24;
}
