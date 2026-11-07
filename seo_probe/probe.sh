#!/bin/bash
B=https://warujie.warujie-mtg.workers.dev
GB='Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'
AD='Mediapartners-Google'
get() { curl -s -A "$2" "$B$1" | tr -d '\n'; }
echo "== card AD"; get "/?card=3e4d70f4-abf3-412f-9dd7-8bfaab381a4f" "$AD" | grep -o '<article class="crawler-card">.\{0,200\}' | head -c 300; echo
echo "== sets GB"; get "/?view=sets" "$GB" | grep -o '<h1>MTGのセット一覧.\{0,300\}' | head -c 400; echo
echo "== meta GB"; get "/?view=meta&format=modern" "$GB" | grep -o 'モダンのメタゲーム.\{0,300\}' | head -c 400; echo
echo "== deck GB"; get "/?view=deck&format=modern&deck=Broodscale" "$GB" | grep -o '<article class="crawler-deck">.\{0,400\}' | head -c 500; echo
echo "== about AD"; get "/?view=about" "$AD" | grep -o '<div id="aboutView"[^>]*>'; echo
echo "== home same"; a=$(get "/" "$GB" | md5sum); b=$(get "/" "Mozilla/5.0" | md5sum); [ "$a" = "$b" ] && echo same || echo DIFFERENT
echo "== sitemap contact"; curl -s "$B/sitemap.xml" | grep -c "view=contact"
