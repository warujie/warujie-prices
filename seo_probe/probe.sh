#!/bin/bash
S=https://warujie.warujie-mtg.workers.dev
GB='Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'
# a real database id: the first card in the sitemap
ID=$(curl -sS -m 30 $S/sitemap.xml | grep -o 'card=[0-9a-f-]*' | sed -n 200p | cut -d= -f2)
echo "card $ID"
curl -sS -m 20 -A "$GB" -H 'Accept-Encoding: identity' "$S/?card=$ID" -o /tmp/p
grep -o '<title>[^<]*</title>' /tmp/p; grep -o '<meta name="description"[^>]*>' /tmp/p
python3 - <<'PY'
import re
t=open('/tmp/p',encoding='utf-8').read(); i=t.find('id="cardViewCard"'); print(t[i:i+1500])
print('cardView tag:', re.search(r'<div id="cardView"[^>]*>', t).group(0))
PY
echo "== person"; curl -sS -m 20 -H 'Accept-Encoding: identity' "$S/?card=$ID" | grep -c crawler-card
echo "== set page"; curl -sS -m 20 -A "$GB" -H 'Accept-Encoding: identity' "$S/?set=mh3" -o /tmp/s
grep -o '<title>[^<]*</title>' /tmp/s; python3 -c "
t=open('/tmp/s',encoding='utf-8').read(); i=t.find('id=\"setGrid\"'); print(t[i:i+600]); print(t.count('<li><a href=\"/?card='))"
echo "== seo file direct"; curl -sS -m 20 -o /dev/null -w '%{http_code}\n' $S/seo/s/mh3.json
