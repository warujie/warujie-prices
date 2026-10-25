import re, time, urllib.request, html, json, os
UA = "WarujieEvents/1.0 (+https://warujie.jp; warujie.mtg" + "@" + "gmail.com)"
OUT = "probe/hfee"; os.makedirs(OUT, exist_ok=True)
def get(u):
    time.sleep(4)
    return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=60).read().decode("utf-8", "replace")
def text(h):
    h = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", h, flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()
res = {}
for shop in (1, 7):
    cal = get(f"https://www.hareruyamtg.com/ja/events/?shop={shop}&date=202611")
    urls = list(dict.fromkeys(re.findall(r'https://www\.hareruyamtg\.com/ja/events/\d+/detail', cal)))
    names = re.findall(r'class="eventCalendar__calendarList__data__name">(.*?)</span>', cal, re.S)
    res[f"shop{shop}"] = {"events": len(urls), "distinct_names": len(set(text(n) for n in names))}
    for i, u in enumerate(urls[:4]):
        h = get(u)
        if i == 0:
            open(f"{OUT}/shop{shop}-{i}.html", "w").write(h)
        t = text(h)
        k = t.find("参加費")
        res[u] = [t[max(0, k - 80):k + 160], t.count("参加費")]
        m = re.search(r"参加費.{0,300}", h, re.S)
        res[u + "#html"] = m.group(0)[:400] if m else None
json.dump(res, open(f"{OUT}/result.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1)[:6000])
