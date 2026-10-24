"""One-off, part 3: which prefecture each Hareruya store is in (store name -> prefecture only)."""
import json, re, subprocess
UA = "warujie.jp link check (https://warujie.jp/; one-off, a few pages)"
html = subprocess.run(["curl", "-sSL", "-m", "30", "-A", UA, "https://www.hareruyamtg.com/ja/user_data/store_menu"], capture_output=True).stdout.decode('utf-8', 'replace')
text = re.sub(r'<[^>]+>', ' ', html); text = re.sub(r'\s+', ' ', text)
PREF = r'(北海道|東京都|京都府|大阪府|[^\s　]{2,3}県)'
names = ['TC東京', 'トーナメントセンター東京', '成田', '福岡', '札幌', 'TC大阪', 'トーナメントセンター大阪', '名古屋', '静岡', '秋葉原', '仙台', '横浜', '高松', '飲める屋', '大宮', '宇都宮', '広島', '郡山', '吉祥寺', '大須', '三宮', '甲府', '川崎', '水戸', '日本橋', '新潟', '金沢', '千葉', '渋谷', '高崎', '京都', '町田', '長野', '岡山', '四日市']
out = {'len': len(text)}
for n in names:
    hits = []
    for m in re.finditer(re.escape(n), text):
        p = re.search(PREF, text[m.end(): m.end() + 250])
        if p: hits.append(p.group(1))
    out[n] = sorted(set(hits))
json.dump(out, open('probe/result3.json', 'w'), ensure_ascii=False, indent=1)
print(out)
