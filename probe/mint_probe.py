"""MINT (mint-web.jp): robots.txt, the TCGイベントスケジュール category, each store's schedule
page and its calendar pictures (the owner's request, 2026-10-25). One page every 4 s."""
import re, time, json, os, urllib.request, html as H
UA = "WarujieEvents/1.0 (+https://warujie.jp; warujie.mtg@gmail.com)"
OUT = "probe/mint"
def get(url, binary=False):
    time.sleep(4)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        b = r.read()
        print("GET", url, r.status, len(b), flush=True)
        if binary:
            return b
        cs = (r.headers.get_content_charset() or "")
        for enc in ([cs] if cs else []) + ["utf-8", "euc-jp", "cp932"]:
            try:
                return b.decode(enc)
            except Exception:
                pass
        return b.decode("utf-8", "replace")
print(get("https://mint-web.jp/robots.txt")[:3000])
home = get("https://mint-web.jp/")
open(f"{OUT}/home.html", "w").write(home)
# store / shop-list links on the home page
for m in sorted(set(re.findall(r'href="([^"]+)"[^>]*>([^<]{0,60}(?:店|店舗|SHOP|ショップ|スケジュール|イベント)[^<]{0,40})<', home))):
    print("HOME LINK", m)
cats = []
page = 1
while page <= 5:
    url = "https://mint-web.jp/?mode=cate&cbid=2870672&csid=0" + (f"&page={page}" if page > 1 else "")
    c = get(url)
    open(f"{OUT}/cate{page}.html", "w").write(c)
    pids = re.findall(r'\?pid=(\d+)', c)
    new = [p for p in dict.fromkeys(pids) if p not in cats]
    print("page", page, "pids", new)
    if not new:
        break
    cats += new
    if f"page={page + 1}" not in c:
        break
    page += 1
stores = []
for pid in cats:
    h = get(f"https://mint-web.jp/?pid={pid}")
    t = re.search(r"<title>(.*?)</title>", h, re.S)
    title = H.unescape(t.group(1)).strip() if t else ""
    imgs = [H.unescape(u) for u in re.findall(r'<img[^>]+src="(https://img\d+\.shop-pro\.jp/[^"]+/etc_base64/[^"]+)"', h)]
    imgs = list(dict.fromkeys(imgs))
    addr = re.findall(r"(〒?\s*\d{3}-\d{4}[^<]{0,80}|(?:東京都|北海道|(?:京都|大阪)府|..県)[^<]{2,60}?(?:丁目|番地|\d+-\d+)[^<]{0,40})", h)
    stores.append({"pid": pid, "title": title, "imgs": imgs, "addr": addr[:3]})
    print("STORE", pid, title, len(imgs), addr[:2], flush=True)
    for i, u in enumerate(imgs[:4]):
        try:
            b = get(u, binary=True)
            ext = ".png" if b[:4] == b"\x89PNG" else ".jpg"
            open(f"{OUT}/{pid}-{i}{ext}", "wb").write(b)
        except Exception as e:
            print("  img fail", u, e)
json.dump(stores, open(f"{OUT}/stores.json", "w"), ensure_ascii=False, indent=1)
# the company's pages that might say anything about reuse
for u in ["https://mint-web.jp/?mode=f1", "https://mint-web.jp/?mode=sk"]:
    try:
        h = get(u)
        txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>|<style.*?</style>", " ", h, flags=re.S)))
        for kw in ["転載", "無断", "複製", "著作権", "引用", "店舗一覧", "店舗"]:
            for m in re.finditer(kw, txt):
                print("TERMS", u, kw, "…", txt[max(0, m.start() - 80):m.start() + 120])
                break
    except Exception as e:
        print("fail", u, e)
