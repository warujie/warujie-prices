"""One-off, part 2: label texts of Hareruya's search checkboxes, whether a filtered list URL
answers, which Yellow Submarine store pages list マジック events (a count only), and Amenity
Dream's tournament page links. Saves names, ids, counts and URLs only; respects robots.txt."""
import json, re, ssl, subprocess, time, urllib.request, urllib.robotparser, urllib.parse
from html.parser import HTMLParser

UA = "warujie.jp link check (https://warujie.jp/; one-off, a few pages)"
def get(url):
    r = subprocess.run(["curl", "-sSL", "-m", "30", "-A", UA, "-w", "\n%{http_code} %{url_effective}", url], capture_output=True)
    body = r.stdout.decode('utf-8', 'replace'); tail = body.rsplit('\n', 1)
    return (tail[0], tail[1] if len(tail) > 1 else '', r.stderr.decode()[:300])
def allowed(url):
    u = urllib.parse.urlsplit(url); txt, st, _ = get(f"{u.scheme}://{u.netloc}/robots.txt")
    rp = urllib.robotparser.RobotFileParser(); rp.parse(txt.splitlines() if st.startswith('200') else [])
    return rp.can_fetch(UA, url), txt[:600], st

class L(HTMLParser):
    def __init__(s): super().__init__(); s.labels = {}; s._for = None; s._t = ''; s.links = []; s._a = None
    def handle_starttag(s, tag, a):
        a = dict(a)
        if tag == 'label' and a.get('for'): s._for = a['for']; s._t = ''
        if tag == 'a' and a.get('href'): s._a = {'href': a['href'], 'text': ''}
    def handle_data(s, d):
        if s._for: s._t += d.strip()
        if s._a is not None: s._a['text'] += d.strip()
    def handle_endtag(s, tag):
        if tag == 'label' and s._for: s.labels[s._for] = s._t; s._for = None
        if tag == 'a' and s._a is not None: s.links.append(s._a); s._a = None

out = {}
html, st, err = get("https://www.hareruyamtg.com/ja/events/search")
p = L(); p.feed(html)
out['hareruya_labels'] = {k: v for k, v in p.labels.items() if k.startswith('eventSearch-')}
time.sleep(4)
test = "https://www.hareruyamtg.com/ja/events/list?term=&from=&to=&formats%5B%5D=2&venues%5B%5D=8&isWeekday=true&isHoliday=true"
ok, _, _ = allowed(test)
if ok:
    html, st, err = get(test); p = L(); p.feed(html)
    out['hareruya_list_test'] = {'status': st, 'event_links': sum(1 for l in p.links if re.search(r'/events/\d+/', l['href'])), 'err': err}
time.sleep(4)
YS = ["sapporo_gs", "shinjuku", "ikebukuro_gs", "machida", "akihabara_rpg", "akihabara_mnt", "tachikawa", "yokohama", "mizo",
      "kawasaki", "yokohama_m", "kashiwa_m", "chiba_gs", "omiya_ps", "kawagoe_cs", "utsunomiya", "nagoya_gs", "nanba_s", "nanba_3",
      "kyoto", "sannomiya", "himeji", "hiroshima", "fukuoka_mc"]
out['ys_magic_rows'] = {}
for slug in YS:
    url = f"https://yellowsubmarine.co.jp/tmt_list/{slug}/"
    html, st, err = get(url)
    out['ys_magic_rows'][slug] = {'status': st, 'マジック': html.count('マジック'), 'MTG': html.count('MTG')}
    time.sleep(4)
for url in ["http://amenitydream.co.jp/matches/", "https://amenitydream.co.jp/matches/"]:
    ok, rtxt, rst = allowed(url)
    rec = {'robots_status': rst, 'robots': rtxt, 'allowed': ok}
    if ok:
        html, st, err = get(url); p = L(); p.feed(html)
        rec.update({'status': st, 'err': err, 'links': p.links[:200], 'マジック': html.count('マジック')})
    out[url] = rec
    time.sleep(4)
json.dump(out, open('probe/result2.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps({k: (v if k != 'hareruya_labels' else len(v)) for k, v in out.items() if not k.startswith('http')}, ensure_ascii=False)[:3000])
