"""Dump every Japanese printing (compact) from Scryfall's all_cards bulk file."""
import gzip, json, sys, urllib.request
UA = {'User-Agent': 'WarujieProbe/1.0 (+https://warujie.jp)', 'Accept': 'application/json'}
def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=600)
meta = json.load(get('https://api.scryfall.com/bulk-data'))
entry = next(e for e in meta['data'] if e['type'] == 'all_cards')
url = entry.get('jsonl_download_uri') or entry['download_uri']
print(url, file=sys.stderr)
import shutil
with get(url) as r, open('all.jsonl.gz', 'wb') as f:
    shutil.copyfileobj(r, f)
out = gzip.open('probe_out/ja_printings.jsonl.gz', 'wt', encoding='utf-8')
en = gzip.open('probe_out/en_numbers.jsonl.gz', 'wt', encoding='utf-8')
n = 0
def faces(c):
    return [{k: f.get(k) for k in ('name', 'printed_name', 'printed_type_line', 'printed_text')} for f in c.get('card_faces') or []]
def img(c):
    u = c.get('image_uris') or ((c.get('card_faces') or [{}])[0].get('image_uris')) or {}
    return u.get('large')
opener = gzip.open('all.jsonl.gz', 'rt', encoding='utf-8')
first = opener.read(1); opener.seek(0)
lines = opener if first != '[' else (json.dumps(c) for c in json.load(opener))
for line in lines:
    line = line.strip().rstrip(',')
    if not line or line in '[]':
        continue
    c = json.loads(line)
    oid = c.get('oracle_id') or (c.get('card_faces') or [{}])[0].get('oracle_id')
    if c.get('lang') == 'ja':
        n += 1
        out.write(json.dumps({'id': c['id'], 'oid': oid, 'set': c.get('set'), 'cn': c.get('collector_number'),
            'name': c.get('name'), 'pn': c.get('printed_name'), 'pt': c.get('printed_type_line'), 'tx': c.get('printed_text'),
            'faces': faces(c), 'img': img(c), 'st': c.get('image_status'), 'layout': c.get('layout'),
            'rel': c.get('released_at'), 'digital': c.get('digital'), 'promo': c.get('promo'), 'stype': c.get('set_type'),
            'mid': c.get('multiverse_ids')}, ensure_ascii=False) + '\n')
    elif c.get('lang') == 'en':
        en.write(json.dumps({'set': c.get('set'), 'cn': c.get('collector_number'), 'name': c.get('name'), 'oid': oid,
                             'mid': c.get('multiverse_ids')}, ensure_ascii=False) + '\n')
out.close(); en.close()
print('ja printings', n, file=sys.stderr)
