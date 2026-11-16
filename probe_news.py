import re, time, urllib.request
UA = "WarujieNews/1.0 (+https://warujie.jp)"
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA, "Accept-Language": "ja,en"}), timeout=30) as r:
        return r.read(3_000_000).decode("utf-8", "replace")
for h in ["@MTGJapan", "@MagicTheGatheringJP", "@mtg_jp", "@MTGjpOfficial", "@magicjp", "@MTGArenaJP", "@mtgjapanofficial", "@MagicJapan",
          "@playmtg", "@MTGArena", "@magicthegathering", "@MagicTheGatheringOfficial", "@StarCityGames", "@hareruyamtg", "@BIGMAGIC", "@bigmagic_mtg"]:
    time.sleep(2)
    try:
        html = get("https://www.youtube.com/" + h)
        cid = re.search(r'"(?:externalId|channelId)":"(UC[\w-]{22})"', html)
        title = re.search(r'<meta property="og:title" content="([^"]+)"', html)
        print(h, cid and cid.group(1), title and title.group(1))
    except Exception as e:
        print(h, type(e).__name__, e)
for u in ["https://yutura.net/channel/4806/", "https://articles.starcitygames.com/feed/", "https://www.hareruyamtg.com/robots.txt", "https://www.bigmagic.net/robots.txt"]:
    time.sleep(2)
    try:
        t = get(u)
        if "yutura" in u:
            print(u, re.findall(r'youtube\.com/(?:channel/UC[\w-]{22}|@[\w.-]+)', t)[:5], re.search(r"<title>([^<]+)", t).group(1))
        elif "feed" in u:
            print(u, len(re.findall(r"<item>", t)), "items", re.findall(r"<title>([^<]+)", t)[1:4])
        else:
            print(u, t[:600].replace("\n", " | "))
    except Exception as e:
        print(u, type(e).__name__, e)
