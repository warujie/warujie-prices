#!/bin/bash
B=https://staging-warujie.warujie-mtg.workers.dev
GB='Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'
AD='Mediapartners-Google'
get() { curl -s -A "$2" "$B$1"; }
echo "== home GB"; get "/" "$GB" | grep -o 'id="homeGuideLists">.\{0,600\}' | head -c 700; echo
echo "== home person"; get "/" "Mozilla/5.0" | grep -o 'id="homeGuideLists">.\{0,40\}'; echo
echo "== card AD"; get "/?card=3e4d70f4-abf3-412f-9dd7-8bfaab381a4f" "$AD" | grep -o '<article class="crawler-card">.\{0,300\}'; echo
echo "== sets GB"; get "/?view=sets" "$GB" | grep -o '<h1>MTGのセット一覧.\{0,500\}'; echo
echo "== meta GB"; get "/?view=meta&format=modern" "$GB" | tr -d "\n" | grep -o "モダンのメタゲーム.\{0,500\}" | head -c 800; echo
D=$(get "/?view=meta&format=modern" "$GB" | grep -o 'href="/?view=deck[^"]*"' | head -1 | sed 's/href="//;s/"//;s/&amp;/\&/g'); echo "deck url: $D"
echo "== deck GB"; get "$D" "$GB" | grep -o '<article class="crawler-deck">.\{0,900\}'; echo
echo "== about AD"; get "/?view=about" "$AD" | grep -o '<div id="aboutView"[^>]*>'; echo
echo "== seo files"; curl -s "$B/seo/home.json" | head -c 300; echo; curl -s "$B/seo/sets.json" | head -c 300; echo
