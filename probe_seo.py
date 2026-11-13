# Checks the test site (staging) for the 2026-11-13 Search Console fixes: what a crawler gets.
# The User-Agent says what it is (our own checker); worker.js treats any agent with "bot" as a crawler.
import json, re, time, urllib.request, urllib.error

SITE = "https://staging-warujie.warujie-mtg.workers.dev/"
UA = "WarujieSeoCheck-bot/1.0 (+https://warujie.jp)"

def get(url, ua=UA):
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")

def canonical(html):
    m = re.search(r'<link rel="canonical" href="([^"]*)"', html)
    return m.group(1).replace("&amp;", "&") if m else ""

# wait for the deploy carrying the change (robots.txt gains /contact)
for i in range(40):
    st, robots = get(SITE + "robots.txt")
    if "Disallow: /contact" in robots:
        print("deployed: robots.txt has the new lines")
        break
    time.sleep(30)
else:
    print("NOT DEPLOYED after 20 minutes; robots.txt:", robots)

def sf(path):
    time.sleep(0.2)
    req = urllib.request.Request("https://api.scryfall.com" + path, headers={"User-Agent": "WarujieProbe/1.0 (+https://warujie.jp)", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)

prints = sf('/cards/search?q=%21%22Lightning+Bolt%22&unique=prints&order=released&dir=asc')["data"]
ids = [p["id"] for p in prints]
print("Lightning Bolt printings:", len(ids))
main = None
for pid in ids:
    st, html = get(SITE + "?card=" + pid)
    c = canonical(html)
    if c.endswith(pid):
        main = pid
        break
print("main page (canonical is itself):", main)
others = [p for p in ids if p != main][:3]
for pid in others:
    st, html = get(SITE + "?card=" + pid)
    print("another printing", pid, "status", st, "canonical", canonical(html), "has card text", "crawler-card" in html and "稲妻" in html)
st, html = get(SITE + "?card=" + (others[0] if others else ids[0]), ua="Mozilla/5.0 (X11; Linux x86_64) Chrome/140 Safari/537.36")
print("a person, another printing: status", st, "canonical", canonical(html), "crawler text", "crawler-card" in html)
st, _ = get(SITE + "?card=ffffffff-ffff-4fff-bfff-ffffffffffff")
print("unknown card, crawler: status", st)
st, _ = get(SITE + "?card=ffffffff-ffff-4fff-bfff-ffffffffffff", ua="Mozilla/5.0 (X11; Linux x86_64) Chrome/140 Safari/537.36")
print("unknown card, person: status", st)
st, _ = get(SITE + "?set=zzzq9")
print("unknown set, crawler: status", st)
st, _ = get(SITE + "?set=m10")
print("real set, crawler: status", st)
st, _ = get(SITE + "?view=deck&format=modern&deck=No+Such+Deck+Here")
print("unknown deck, crawler: status", st)
st, html = get(SITE + "?view=events")
m = re.search(r'<div class="crawler-events"><h2>([^<]*)</h2>', html)
print("events page: status", st, "heading", m.group(1) if m else None, "list items", html.count("<li>") if m else 0)
st, html = get(SITE + "?view=prices")
m = re.search(r'<div class="crawler-movers"><h2>([^<]*)</h2>', html)
print("prices page: status", st, "heading", m.group(1) if m else None, "first", re.findall(r'<ol class="crawler-list"><li>(.*?)</li>', html)[:1])
st, _ = get(SITE + "contact")
print("/contact GET:", st)
