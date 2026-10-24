# Probe 5: page shapes for the event calendar builder (printed to the log only; nothing saved).
import html as H, re, ssl, time, urllib.request
UA = "warujie.jp event calendar probe (+https://warujie.jp)"
def get(url, insecure=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ja"})
    ctx = ssl._create_unverified_context() if insecure else None
    try:
        with urllib.request.urlopen(req, timeout=40, context=ctx) as r:
            return r.read().decode("utf-8", "replace")
    except Exception as e:
        print("ERR", url, repr(e)[:200]); return ""
    finally:
        time.sleep(4)
def text(h):
    h = re.sub(r"<(script|style|svg)\b.*?</\1>", " ", h, flags=re.S)
    h = re.sub(r"<br\s*/?>|</(p|div|li|tr|td|th|h\d)>", "\n", h)
    t = H.unescape(re.sub(r"<[^>]+>", " ", h))
    return "\n".join(l.strip() for l in t.split("\n") if l.strip())
print("=== Hareruya store list")
h = get("https://www.hareruyamtg.com/ja/store/")
t = text(h)
for m in re.finditer(r"〒?\d{3}-\d{4}[^\n]{0,80}|(?:東京都|北海道|(?:京都|大阪)府|\S{2,3}県)\S{1,30}[市区町村郡]\S{0,30}", t):
    s = t[max(0, m.start() - 60):m.end()].replace("\n", " | ")
    print("  ", s[:200])
print("store links:", sorted(set(re.findall(r'href="([^"]*/store/[^"]+)"', h)))[:60])
print("=== Hareruya next month, shop 1")
h = get("https://www.hareruyamtg.com/ja/events/?shop=1&date=202611")
print("len", len(h), "days", len(re.findall(r'class="eventCalendar__calendarList__data"', h)), "events", h.count("eventCalendar__unregular__tournament__container"))
i = h.find('<li id="'); print(re.sub(r"\s+", " ", h[i:i + 1500]))
print("title:", re.search(r"<title>(.*?)</title>", h, re.S).group(1)[:120] if "<title>" in h else "")
print("=== Amenity Dream")
h = get("https://amenitydream.co.jp/matches/", insecure=True)
for sel in re.findall(r'<select name="(\w+)">(.*?)</select>', h, re.S):
    print(sel[0], re.findall(r'value="([^"]*)"[^>]*>([^<]*)<', sel[1])[:40])
h = get("https://amenitydream.co.jp/matches/?type=2&shop=&date=", insecure=True)
rows = re.findall(r"<tr>\s*(.*?)</tr>", h, re.S)
print("all-shop rows", len(rows), "pagination:", re.sub(r"\s+", " ", re.search(r'<p class="pagination">(.*?)</p>', h, re.S).group(1))[:300] if 'class="pagination"' in h else None)
shops = {}
for r in rows:
    tds = [text(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]
    if len(tds) >= 4: shops[tds[1]] = shops.get(tds[1], 0) + 1
print("rows per shop", shops)
for r in rows[:3]: print("  ", [text(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)])
for slug in ["tokyo-akihabara", "tokyo-machida", "aichi-osu"]:
    t = text(get(f"https://amenitydream.co.jp/shop/{slug}/", insecure=True))
    m = re.search(r"(〒?\d{3}-\d{4}.{0,80})", t.replace("\n", " "))
    print(slug, m.group(1) if m else t[:300].replace("\n", " | "))
print("=== Yellow Submarine")
h = get("https://yellowsubmarine.co.jp/tmt_list/shinjuku/")
print("len", len(h), "tables", h.count("<table"), "classes", sorted(set(re.findall(r'class="([^"]*(?:tmt|tour|event|list)[^"]*)"', h)))[:30])
t = text(h)
i = t.find("大会"); print(t[:200].replace("\n", " | ")); print("---"); print(t[i:i + 2500])
i = h.find("<table"); print("--- table html:"); print(re.sub(r"\s+", " ", h[i:i + 2500]))
h = get("https://yellowsubmarine.co.jp/tournament/")
print("tournament page links:", sorted(set(re.findall(r'href="([^"]*(?:tmt|shop|store)[^"]*)"', h)))[:80])
