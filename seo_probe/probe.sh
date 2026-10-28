#!/bin/bash
S=https://staging-warujie.warujie-mtg.workers.dev
echo "== robots"; curl -sS -m 20 $S/robots.txt
echo "== sitemap"; curl -sS -m 30 -D /tmp/h -o /tmp/sm $S/sitemap.xml; head -1 /tmp/h; grep -i content-type /tmp/h; grep -c "<loc>" /tmp/sm; head -c 600 /tmp/sm; echo; grep -m2 "card=" /tmp/sm
echo "== card page"; curl -sS -m 20 -D /tmp/h2 -o /tmp/p -H 'Accept-Encoding: identity' "$S/?card=0b2ee2c9-1f8b-4d48-a1d4-8f0fd6b8a1bd&print=en"; grep -i "x-robots\|^HTTP" /tmp/h2; grep -o '<link rel="canonical"[^>]*>' /tmp/p; grep -c 'application/ld+json' /tmp/p
echo "== live workers.dev (before publish)"; curl -sS -m 20 -D - -o /dev/null https://warujie.warujie-mtg.workers.dev/ | grep -i "^HTTP\|x-robots"
