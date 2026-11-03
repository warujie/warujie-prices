import json, time, urllib.request, urllib.parse
UA = {"User-Agent": "WarujieProbe/1.0 (+https://warujie.jp)"}
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30) as r:
        return json.loads(r.read().decode())
PLACES = [  # pref, city, town, store
 ("群馬県","伊勢崎市","宮子町","コミかる伊勢崎"), ("群馬県","高崎市","江木町","コミかる高崎"),
 ("千葉県","松戸市","本町","ホビーステーション松戸店"), ("神奈川県","厚木市","中町","ホビーステーション本厚木店"),
 ("長野県","塩尻市","広丘原新田","Suzunone"), ("静岡県","浜松市","常盤町","マスターズギルド"),
 ("静岡県","浜松市","貴布祢","マスターズギルドなゆた"), ("愛知県","半田市","一本木町","アップキープ"),
 ("愛知県","名古屋市","栄","Misteria"), ("愛知県","名古屋市","椿町","竜星の嵐名古屋店"),
 ("愛知県","名古屋市","港町","パピー弥富店"), ("愛知県","弥富市","鯏浦町","トレカっち"),
 ("愛知県","江南市","東野町","尾張堂"), ("愛知県","稲沢市","小池","紙屋敷"),
 ("滋賀県","草津市","西草津","カードショップLight"), ("大阪府","堺市","三国ヶ丘御幸通","黄鶏屋"),
 ("岡山県","岡山市","大供","若院"), ("福岡県","福岡市","大名","MINT福岡店"),
 ("長崎県","長崎市","大橋町","TiM"), ("鹿児島県","出水市","上鯖淵","いずマジ"),
 ("鹿児島県","鹿児島市","上之園町","BOOKBOX"), ("沖縄県","中城村","南上原","ABSOLUTE ZERO"),
 ("栃木県","小山市","城山町","ホウネンエソ"), ("沖縄県","沖縄市","泡瀬","マンガ倉庫 泡瀬店"),
]
for pref, city, town, store in PLACES:
    q = pref + city + town
    try:
        g = get("https://msearch.gsi.go.jp/address-search/AddressSearch?q=" + urllib.parse.quote(q))
        hits = [h for h in g if city in h["properties"]["title"] and town[:2] in h["properties"]["title"]] or g
        lon, lat = hits[0]["geometry"]["coordinates"]
        title = hits[0]["properties"]["title"]
        time.sleep(1)
        s = get(f"https://express.heartrails.com/api/json?method=getStations&x={lon}&y={lat}")
        st = [f'{x["name"]}({x["line"]},{x["distance"]})' for x in s["response"].get("station", [])[:4]]
        print("STN", json.dumps({"q": q, "store": store, "geo": title, "lat": lat, "lon": lon, "near": st}, ensure_ascii=False))
    except Exception as e:
        print("ERR", q, e)
    time.sleep(1)
