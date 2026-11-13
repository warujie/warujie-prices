"""Probe: fetch Scryfall's rulings and oracle_cards bulk files, save compact copies and size numbers."""
import gzip, json, time, urllib.request, collections
UA = {'User-Agent': 'warujie.jp-rulings-probe/1.0', 'Accept': 'application/json'}
def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()
def load_bulk(entry):
    url = entry.get('jsonl_download_uri') or entry['download_uri']
    raw = get(url)
    if raw[:2] == b'\x1f\x8b':
        raw = gzip.decompress(raw)
    text = raw.decode('utf-8').strip()
    if text.startswith('['):
        return json.loads(text)
    return [json.loads(l) for l in text.splitlines() if l.strip()]
bulk = json.loads(get('https://api.scryfall.com/bulk-data'))
by = {b['type']: b for b in bulk['data']}
print('bulk types', list(by))
time.sleep(0.2)
rulings = load_bulk(by['rulings']); time.sleep(0.2)
cards = load_bulk(by['oracle_cards'])
print('rulings', len(rulings))
slim = [[r['oracle_id'], r.get('source'), r.get('published_at'), r.get('comment')] for r in rulings]
with gzip.open('probe_out/rulings.json.gz', 'wt', encoding='utf-8') as f:
    json.dump(slim, f, ensure_ascii=False)
cs = [[c.get('oracle_id'), c.get('name'), c.get('edhrec_rank'), c.get('penny_rank'),
       ','.join(k for k, v in (c.get('legalities') or {}).items() if v in ('legal', 'restricted')), c.get('digital')] for c in cards]
with gzip.open('probe_out/oracle_slim.json.gz', 'wt', encoding='utf-8') as f:
    json.dump(cs, f, ensure_ascii=False)
uniq = collections.Counter(r['comment'] for r in rulings)
print('cards with rulings', len({r['oracle_id'] for r in rulings}), 'unique texts', len(uniq),
      'chars all', sum(len(r['comment']) for r in rulings), 'chars unique', sum(len(t) for t in uniq))
print('sources', collections.Counter(r.get('source') for r in rulings))
