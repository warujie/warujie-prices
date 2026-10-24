# Probe 4: what each tournament source looks like to a script (robots.txt, page shape, APIs).
import json, os, re, ssl, subprocess, urllib.request
UA = "warujie.jp event calendar probe (+https://warujie.jp)"
os.makedirs("probe/raw", exist_ok=True)
out = {}
def get(url, name, insecure=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ja,en"})
    ctx = ssl._create_unverified_context() if insecure else None
    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
            body = r.read()
            text = body.decode("utf-8", "replace")
            open(f"probe/raw/{name}", "w").write(text[:400000])
            out[name] = {"url": url, "status": r.status, "len": len(body), "final": r.geturl(), "ctype": r.headers.get("content-type")}
            return text
    except Exception as e:
        out[name] = {"url": url, "error": repr(e)[:300]}
        return ""
for host, name in [("https://amenitydream.co.jp", "amenity"), ("https://www.hareruyamtg.com", "hareruya"),
                   ("https://yellowsubmarine.co.jp", "yellowsub"), ("https://locator.wizards.com", "locator"),
                   ("https://www.facebook.com", "facebook")]:
    get(host + "/robots.txt", f"robots_{name}.txt")
    if name == "amenity" and "error" in out.get(f"robots_{name}.txt", {}):
        get(host + "/robots.txt", f"robots_{name}_insecure.txt", insecure=True)
# Amenity Dream: the tournament list, per shop
a = get("https://amenitydream.co.jp/matches/?type=2&shop=12&date=", "amenity_matches.html")
if not a:
    a = get("https://amenitydream.co.jp/matches/?type=2&shop=12&date=", "amenity_matches_insecure.html", insecure=True)
    get("https://amenitydream.co.jp/", "amenity_home_insecure.html", insecure=True)
else:
    get("https://amenitydream.co.jp/", "amenity_home.html")
try:
    out["amenity_tls"] = subprocess.run(["bash", "-c", "echo | openssl s_client -connect amenitydream.co.jp:443 -servername amenitydream.co.jp 2>&1 | head -30"], capture_output=True, text=True, timeout=30).stdout
except Exception as e:
    out["amenity_tls"] = repr(e)
# Hareruya: the store calendar the owner linked, and its list page
get("https://www.hareruyamtg.com/en/events/?shop=30", "hareruya_cal_en.html")
get("https://www.hareruyamtg.com/ja/events/?shop=1", "hareruya_cal_ja.html")
get("https://www.hareruyamtg.com/ja/events/list?formats%5B%5D=2&venues%5B%5D=1&isWeekday=true&isHoliday=true", "hareruya_list.html")
# Wizards: the locator page and its scripts (to see where its data comes from)
loc = get("https://locator.wizards.com/", "locator.html")
for i, src in enumerate(re.findall(r'src="([^"]+\.js)"', loc)[:6]):
    url = src if src.startswith("http") else "https://locator.wizards.com" + ("" if src.startswith("/") else "/") + src
    js = get(url, f"locator_js_{i}.js")
    out[f"locator_js_{i}_apis"] = sorted(set(re.findall(r'https://[a-zA-Z0-9.\-]+(?:/[a-zA-Z0-9_\-/.]*)?', js)))[:80]
get("https://wpn.wizards.com/en/terms-of-use", "wpn_terms.html")
get("https://locator.wizards.com/terms", "locator_terms.html")
# Facebook: the photo post the owner linked
get("https://www.facebook.com/photo?fbid=1608392257968123&set=a.459572686183425", "facebook_photo.html")
json.dump(out, open("probe/result4.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1)[:20000])
