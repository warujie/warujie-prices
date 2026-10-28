#!/bin/bash
# one-off: what search engines get from warujie.jp and its workers.dev copies
GB='Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'
CH='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36'
for url in https://warujie.jp/ https://warujie.jp/robots.txt https://warujie.jp/sitemap.xml https://www.warujie.jp/ http://warujie.jp/ \
           https://warujie.warujie-mtg.workers.dev/ https://warujie.warujie-mtg.workers.dev/robots.txt \
           "https://warujie.warujie-mtg.workers.dev/?card=0b2ee2c9-1f8b-4d48-a1d4-8f0fd6b8a1bd" \
           https://staging-warujie.warujie-mtg.workers.dev/ https://staging-warujie.warujie-mtg.workers.dev/robots.txt \
           https://api.scryfall.com/robots.txt https://cards.scryfall.io/robots.txt https://scryfall.com/robots.txt; do
  for ua in "$GB" "$CH"; do
    echo "=================== $url  [${ua:0:40}]"
    curl -sS -m 20 -D - -o /tmp/body -A "$ua" -H 'Accept-Encoding: identity' "$url" | grep -iv '^set-cookie\|^report-to\|^nel' 
    head -c 1500 /tmp/body; echo
  done
done
