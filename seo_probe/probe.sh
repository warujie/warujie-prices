#!/bin/bash
for S in https://warujie.warujie-mtg.workers.dev https://warujie.jp; do
echo "######## $S"
echo "== robots"; curl -sS -m 20 $S/robots.txt
echo "== sitemap"; curl -sS -m 30 -D /tmp/h -o /tmp/sm $S/sitemap.xml; head -1 /tmp/h; grep -c "<loc>" /tmp/sm; grep -m1 "view=import" /tmp/sm; grep -m1 "card=" /tmp/sm
echo "== card page"; curl -sS -m 20 -D /tmp/h2 -o /tmp/p -H 'Accept-Encoding: identity' "$S/?card=0b2ee2c9-1f8b-4d48-a1d4-8f0fd6b8a1bd&print=en"; grep -i "x-robots\|^HTTP" /tmp/h2; grep -o '<link rel="canonical"[^>]*>' /tmp/p
done
