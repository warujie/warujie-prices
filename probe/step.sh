sleep 120
curl -sS --compressed -A "WarujieProbe/1.0 (+https://warujie.jp)" -o probe_out/staging_db.json https://staging-warujie.warujie-mtg.workers.dev/ja_cards.json
python3 - <<'PY' > probe_out/staging_check.txt
import json
d=json.load(open('probe_out/staging_db.json')); ix={k:i for i,k in enumerate(d['fields'])}
want={'Orim, Samite Healer',"Orim's Prayer",'Déjà Vu','Djinn of the Lamp','Warrior Angel','Shivan Raptor','Rakdos, the Muscle'}
print('generated', d.get('generated'))
for r in d['cards']:
    if r[ix['name_en']] in want: print(r[ix['name_en']], '|', r[ix['name_ja']])
PY
rm -f probe_out/staging_db.json
cat probe_out/staging_check.txt
