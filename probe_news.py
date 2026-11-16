import re, time, urllib.request, html
UA = "WarujieNews/1.0 (+https://warujie.jp)"
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA, "Accept-Language": "ja,en"}), timeout=30) as r:
        return r.read(3_000_000).decode("utf-8", "replace")
ids = ["UC8ZGymAvfP97qJabgqUkz4A", "UC7Z_SvRUcFzKy7AgDDAWEkA", "UCOPmiw4U-ZZwJgg3Vh18_uQ", "UCJ6yc6KcQrnky3TRpUUtylA", "UC2lJogHackxCqDXfc7dV2YQ", "UC_awtZFkwnfYF6EKUT-RpOQ", "UC8zICvPIzVvKWrVJ62BSYRw"]
for h in ["@MagicTheGathering", "@WizardsMagic", "@MTGjp", "@mtgjp_official", "@magic_the_gathering_jp", "@MTGJapanOfficial", "@hareruya", "@HareruyaMTG", "@hareruyatv", "@BigMagicTV"]:
    time.sleep(2)
    try:
        t = get("https://www.youtube.com/" + h)
        cid = re.search(r'"(?:externalId|channelId)":"(UC[\w-]{22})"', t)
        if cid and cid.group(1) not in ids: ids.append(cid.group(1))
        print(h, cid and cid.group(1))
    except Exception as e:
        print(h, type(e).__name__)
for c in ids:
    time.sleep(2)
    try:
        t = get("https://www.youtube.com/feeds/videos.xml?channel_id=" + c)
        name = re.search(r"<author>\s*<name>([^<]+)", t)
        titles = [html.unescape(x) for x in re.findall(r"<media:title>([^<]+)", t)][:4]
        dates = re.findall(r"<published>([^<]+)", t)[1:3]
        print(c, name and html.unescape(name.group(1)), dates, titles)
    except Exception as e:
        print(c, type(e).__name__, e)
