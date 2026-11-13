"""Japanese names in MTGJSON's set files, for comparison with Scryfall's."""
import gzip, json, sys, time, urllib.request, lzma
UA = {'User-Agent': 'WarujieProbe/1.0 (+https://warujie.jp)'}
sets = sys.argv[1].split(',')
out = {}
for s in sets:
    url = f'https://mtgjson.com/api/v5/{s.upper()}.json.xz'
    try:
        data = json.loads(lzma.decompress(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read()))
    except Exception as e:
        print(s, 'error', e, file=sys.stderr); continue
    rows = []
    for c in data['data'].get('cards', []):
        for f in c.get('foreignData') or []:
            if f.get('language') == 'Japanese':
                rows.append({'name': c['name'], 'face': c.get('faceName'), 'cn': c.get('number'), 'ja': f.get('name'),
                             'faceja': f.get('faceName'), 'mid': (f.get('identifiers') or {}).get('multiverseId'),
                             'sfid': (f.get('identifiers') or {}).get('scryfallId')})
    out[s] = rows
    print(s, len(rows), file=sys.stderr)
    time.sleep(1)
json.dump(out, open('probe_out/mtgjson_ja.json', 'w'), ensure_ascii=False)
