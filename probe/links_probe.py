"""One-off: read the shape of three shops' event pages (form fields, link targets) for
warujie.jp's links-only 大会 page. Saves only field names/values and link URLs+texts,
never page content. Respects robots.txt."""
import json, time, urllib.request, urllib.robotparser, urllib.parse
from html.parser import HTMLParser

UA = "warujie.jp link check (https://warujie.jp/; one-off, a few pages)"
PAGES = [
    "https://www.hareruyamtg.com/ja/events/search",
    "https://www.hareruyamtg.com/ja/events/",
    "https://www.hareruyamtg.com/ja/store/",
    "https://yellowsubmarine.co.jp/tournament/",
    "http://amenitydream.co.jp/matches/",
    "https://www.amenitydream.com/",
]

class P(HTMLParser):
    def __init__(s):
        super().__init__(); s.inputs = []; s.links = []; s.forms = []; s._a = None; s._opt = None; s._sel = None; s._label = ''
    def handle_starttag(s, tag, a):
        a = dict(a)
        if tag == 'form': s.forms.append({k: a.get(k) for k in ('action', 'method', 'id')})
        if tag == 'input': s.inputs.append({k: a.get(k) for k in ('type', 'name', 'value', 'id')})
        if tag == 'select': s._sel = a.get('name')
        if tag == 'option': s._opt = {'select': s._sel, 'value': a.get('value'), 'text': ''}
        if tag == 'a' and a.get('href'): s._a = {'href': a['href'], 'text': ''}
    def handle_data(s, d):
        if s._a is not None: s._a['text'] += d.strip()
        if s._opt is not None: s._opt['text'] += d.strip()
    def handle_endtag(s, tag):
        if tag == 'a' and s._a is not None: s.links.append(s._a); s._a = None
        if tag == 'option' and s._opt is not None: s.inputs.append(s._opt); s._opt = None

robots = {}
def allowed(url):
    u = urllib.parse.urlsplit(url); base = f"{u.scheme}://{u.netloc}"
    if base not in robots:
        rp = urllib.robotparser.RobotFileParser(base + "/robots.txt")
        try:
            req = urllib.request.Request(base + "/robots.txt", headers={"User-Agent": UA})
            txt = urllib.request.urlopen(req, timeout=20).read().decode('utf-8', 'replace')
            rp.parse(txt.splitlines()); robots[base] = (rp, txt[:1500])
        except Exception as e:
            robots[base] = (None, f"robots error: {e}")
    rp = robots[base][0]
    return True if rp is None else rp.can_fetch(UA, url)

out = {}
for url in PAGES:
    rec = {}
    try:
        if not allowed(url):
            rec['skipped'] = 'robots.txt disallows'
        else:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            r = urllib.request.urlopen(req, timeout=30)
            html = r.read().decode('utf-8', 'replace'); rec['status'] = r.status; rec['final_url'] = r.geturl()
            p = P(); p.feed(html)
            rec['forms'] = p.forms; rec['inputs'] = p.inputs
            keep = ('event', 'tmt_list', 'matches', 'store', 'shop', 'tournament')
            rec['links'] = [l for l in p.links if any(k in l['href'] for k in keep)][:400]
    except Exception as e:
        rec['error'] = repr(e)
    out[url] = rec
    time.sleep(4)
out['_robots'] = {k: v[1] for k, v in robots.items()}
json.dump(out, open('probe/result.json', 'w'), ensure_ascii=False, indent=1)
print({k: (v.get('status'), v.get('skipped'), v.get('error'), len(v.get('links', []))) for k, v in out.items() if k != '_robots'})
