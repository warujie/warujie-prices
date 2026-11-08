import json, os, time, urllib.request
UA = {"User-Agent": "warujie.jp-dev-probe/1.0", "Accept": "*/*"}
def get(u, p):
    try:
        req = urllib.request.Request(u, headers=UA)
        open(p, "wb").write(urllib.request.urlopen(req, timeout=30).read())
    except Exception as e: print("fail", u, e)
    time.sleep(0.12)
os.makedirs("out/icons", exist_ok=True); os.makedirs("out/img", exist_ok=True)
sets = [s for s in json.load(open("out/sets.json"))["data"] if not s.get("digital") and s.get("card_count", 0) > 0]
seen = set()
for s in sets:
    u = s["icon_svg_uri"].split("?")[0]
    n = u.rsplit("/", 1)[1]
    if n in seen: continue
    seen.add(n); get(u, "out/icons/" + n)
for code in ["dsk", "mh3"]:
    for c in json.load(open(f"out/search_{code}.json"))["data"][:40]:
        iu = c.get("image_uris") or (c.get("card_faces") or [{}])[0].get("image_uris") or {}
        if iu.get("normal"): get(iu["normal"], f"out/img/{c['id']}.jpg")
print("icons", len(seen))
