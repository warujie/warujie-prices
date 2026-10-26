# Is the publish live? The live Worker's own address serves the same page as warujie.jp.
for h in warujie.warujie-mtg.workers.dev staging-warujie.warujie-mtg.workers.dev; do
  curl -s -A "warujie.jp check (warujie.mtg@gmail.com)" --compressed "https://$h/" -o /tmp/p.html -w "$h %{http_code} %{size_download}\n"
  for w in ev-cal-btn ev-where-t square-3rd.jp EV_CAL_ICON; do echo "  $w: $(grep -c "$w" /tmp/p.html)"; done
done
# recheck Mon Oct 26 15:41:39 UTC 2026
