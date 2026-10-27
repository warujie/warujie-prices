# warujie-prices developer guide

This repository builds the price, listing, combo and role-tag data that
[warujie.jp](https://warujie.jp) reads, and publishes it to the private Cloudflare R2 bucket
`warujie-price-data` (the site reads it through its Worker at `warujie.jp/data/`). GitHub Pages
(`https://warujie.github.io/warujie-prices/`) only shows a notice now. The site itself is in
[warujie/Warujie](https://github.com/warujie/Warujie) (a private repository; its `docs/` folder
explains the site). This repository stays public: unlimited Actions minutes are free only for
public repositories on the free plan.

- The owner's rules (which outside data may be used, no secrets in the repo) are in
  [`../CLAUDE.md`](../CLAUDE.md) and in the site repository's `CLAUDE.md`.
- The format of every published file is in [data-formats.md](data-formats.md).

## The parts

| File | What it builds | Into | Source |
|---|---|---|---|
| [`build_prices.py`](../build_prices.py) | Price history, today's shop prices, lowest listings, offers with stock, price movers | `site/index.json`, `site/h/`, `site/q/`, `site/movers.json`, `site/cheap.json.gz`, `site/ids.json.gz` | Scryfall `default_cards` bulk file (TCGplayer USD, Cardmarket EUR), MTGJSON (history backfill, shop prices), TCGCSV and Cardmarket's price guide (lowest listings), Card Kingdom's and Mana Pool's public price lists, CardTrader's API, last night's ENNDAL GAMES data, today's PullVault data |
| [`shop_enndal.py`](../shop_enndal.py) | ENNDAL GAMES' in-stock singles in yen (Japan), read once a night; also matches them to printings for `build_prices.py` | `enndal.json.gz` (kept encrypted as an artifact, not published) | ENNDAL GAMES' shop pages, with the shop's permission |
| [`shop_pullvault.py`](../shop_pullvault.py) | PullVault's in-stock singles in dollars (US), read once a day, each matched to its printing and checked against the listing's own photos | `pullvault.json.gz` (read by `build_prices.py` in the same run, not published) | pullvault.gg's singles page, with the shop's permission; Scryfall's search and card pictures |
| [`build_combos.py`](../build_combos.py) | Commander combos per card | `site/c/` | Commander Spellbook's bulk file |
| [`build_tags.py`](../build_tags.py) | Role tags (removal, draw, ramp…) and EDHREC rank per card | `site/t/tags.json.gz` | Scryfall Tagger oracle tags, via Scryfall's search API |
| [`build_precons.py`](../build_precons.py) | Every Commander precon's deck list (commander and cards), for the site's Commander set pages and the deck price page's precon menu | `site/precons.json.gz` | MTGJSON's `DeckList.json`, `SetList.json` and deck files (MIT licence) |
| [`.github/workflows/update-prices.yml`](../.github/workflows/update-prices.yml) | Runs the builders and publishes `site/` to R2 (GitHub Pages gets only a notice) | | |
| [`.github/workflows/enndal-nightly.yml`](../.github/workflows/enndal-nightly.yml) | Runs `shop_enndal.py` at 2am Japan time and keeps the result, encrypted, as the "enndal" artifact (older ones are deleted) | | |

**Nothing is committed by the workflow.** Each run reads yesterday's published data
(`--previous`: a copy of the R2 bucket in `prev/`; if R2 can't be read the run stops), adds
today, and publishes the result to R2. R2 needs the
`CLOUDFLARE_R2_TOKEN` secret, a Cloudflare API token that may only edit R2; the S3-style key
pair `aws s3 sync` uses is made from it in the workflow. The repository never grows,
and the published site *is* the history: if a run publishes a broken history, the next run
builds on it. That's why `build_prices.py` stops without publishing when the old history can't
be read or Scryfall's export looks incomplete (`--min-cards`, default 20,000 priced printings).

## When it runs

`update-prices.yml` runs:

- every day at **12:17 UTC** (21:17 in Japan), after Scryfall's daily export;
- when `build_prices.py`, `build_combos.py`, `build_tags.py`, `build_precons.py` or the workflow changes on `main`;
- by hand ("Run workflow" in GitHub Actions).

`enndal-nightly.yml` runs every day at **17:00 UTC** (2:00 in Japan) and stops by 20:45 UTC
(5:45 in Japan): that is what we told ENNDAL GAMES. `shop_enndal.py` refuses to start outside
that window, so a run by hand in the daytime does nothing. The evening price update then uses
that night's data, so ENNDAL's stock on the site is from the night before.

`shop_pullvault.py` runs inside `update-prices.yml`, just before the price build (step "Read
PullVault's singles"). It can't stop the price update: if it fails, the build runs without
`--pullvault` and the published PullVault offers are kept for `KEEP_DAYS` (3) days.

`build_combos.py`, `build_tags.py` and `build_precons.py` rebuild only when the published data is older than 7 days;
on other days they copy the published files over. Neither can stop the price update: on any
problem they keep the published data and exit normally.

**Pushing a builder change to `main` runs it and publishes the result at once**, which reaches
warujie.jp immediately. Test locally first (below), and merge to `main` only when it's ready.

## Secrets

`CARDTRADER_TOKEN` (a GitHub Actions secret, Settings → Secrets and variables → Actions) lets
`build_prices.py` read CardTrader's European sellers. Without it they're skipped. Never write
the token anywhere else.

## What each builder does, in short

### `build_prices.py`

1. Reads the published `index.json` and `h/` shards (`read_previous()`).
2. Reads Scryfall's `default_cards` bulk file and stores today's four series per printing:
   US dollars and euros, non-foil and foil (`build()`).
3. While the history is shorter than 60 days, fills in up to 90 earlier days from MTGJSON's
   price archive (`backfill()`); after a failed attempt waits 7 days before trying again.
4. Today's shop prices from MTGJSON's daily file (`shop_prices()`), plus lowest listings
   from TCGCSV and Cardmarket's price guide (`add_lows()`).
5. Offers by condition with stock (`shop_offers()`): Card Kingdom, Mana Pool, and, with the token,
   CardTrader (`cardtrader_offers()`, time-limited by `CARDTRADER_MINUTES`; it resumes where it
   stopped on the next day via `ct_resume`), and ENNDAL GAMES from `--enndal` (`add_offers()` in
   `shop_enndal.py`: matched by set and collector number, or by a name that is unique in the set).
   Without `--enndal`, the published ENNDAL offers are kept for up to `KEEP_DAYS`. PullVault from
   `--pullvault` (`add_offers()` in `shop_pullvault.py`: the listings already matched and checked
   there; without it, the published ones are kept for up to its `KEEP_DAYS`). The cheapest
   `LISTINGS_PER_FINISH` per market and finish are kept.
6. Price movers (`movers()`): biggest rises and falls over 1, 7 and 30 days (`WINDOWS`), US and EU,
   for cards worth at least `MIN_PRICE_CENTS` that moved at least `MIN_CHANGE_CENTS`, ignoring
   one-day spikes and prices MTGJSON disagrees with.
7. A self-check of the sources (`source_check()`), then `write_output()`.
8. Each card's cheapest printing for deck prices (`note_cheapest()` during the read, written as
   `cheap.json.gz`; see [data-formats.md](data-formats.md)).

Daily values are kept for 120 days (`DAILY_DAYS`); older history keeps one value a week (Mondays),
so the files stay small for years.

### `shop_enndal.py`

ENNDAL GAMES agreed to low-frequency automated reading on 2026-10-15, and we told them how we
read: once a night, one page at a time, `PAGE_GAP` (4) seconds apart, with a User-Agent naming
warujie.jp and our contact address. **Keep it that way: never read pages in parallel or in the
daytime, and stop at once if they ask.** A 403, 429 or 503 stops the night.

`nightly()` reads the set menu (`MENU_URL`, leaving out `SKIP_WORDS` such as supplies and
Flesh and Blood), then each set's in-stock list pages (`list_url()`, 100 products a page), the
sets read longest ago first, for at most `NIGHT_MINUTES`. A set not read tonight keeps its
products for up to `KEEP_DAYS`. `parse_list()` reads each product's code
(`SET-<rarity><colour>-<number>-<lang>-<condition>-<finish>`) and its price table.

### `shop_pullvault.py`

PullVault (pullvault.gg) is a US shop; its owner gave permission on 2026-10-25 (the site
owner's word, recorded in the site's `CLAUDE.md`). We still read gently: once a day, only pages
its robots.txt allows (it disallows `/api/`, `.json` and sort/filter/page links), with a
User-Agent naming warujie.jp, and every listing links back to its product page. **Stop at once
if PullVault asks.**

The shop is a JavaScript page on Shopify. `read_shop()` opens `SHOP_PAGES` (only
https://pullvault.gg/singles) in a headless browser (Playwright) and keeps the product list that
page itself receives from Shopify (all products, 100 at a time; it scrolls for more, `PAGE_GAP`
seconds apart, if the list says there are more). It sends no requests of its own to the shop.

`listings()` keeps the in-stock products whose title reads "Card - Set" (not `SEALED_TYPES`), one
listing per available variant (condition and finish come from the variant's options when it has
them, else from the product's `card.condition` and `card.language` fields; an unknown condition
stays empty). `parse_title()` splits "Name (Kind) - Set Name (CODE) (Language)".

Then each listing is matched (`nightly()`, `match_listing()`):

1. **Candidates**: every printing of that name from Scryfall's search (`printings()`, English
   where there is one, a printing only made in Japanese as it is), and the same in the
   listing's language, or in Japanese for an English listing, for the language check.
   `SCRYFALL_PAUSE` between requests.
2. **What the title allows** (`title_fits()`): the set by code, else by name; the words in
   brackets (`VARIANT_WORDS`: Serial, Borderless, Extended, Showcase, Retro, Etched, Poster,
   Surge…); a title without "Serial" rules serialized printings out; foil or not.
3. **What the photos show** (`picture_scores()`, `match_photo()`): the listing's first
   `PHOTOS_PER_LISTING` photos (at `PHOTO_WIDTH`) against each candidate's Scryfall picture: SIFT
   features, a perspective fit (RANSAC), and the photo straightened into the card's shape and
   compared with the whole picture (`_likeness()`, edge pictures, so frames and borders count). A
   printing is shown when at least `MIN_INLIERS` features fit and the likeness is at least
   `MIN_LIKENESS`; printings within `LOOK_MARGIN` of the best look alike (a serialized copy looks
   like the plain showcase one; the title tells them apart).
4. **The decision** (`choose()`): the printing both allow. When they disagree, the photos win
   only when they show one printing beyond doubt (`decisive()`: `SURE_INLIERS`,
   `SURE_LIKENESS`, every other look `SURE_GAP` behind, the listing's language); the listing is
   then shown under that printing and the run log notes it. One exception (the owner's choice,
   2026-10-25): when that printing is a language-only one (a Japanese-only promo) with the same
   artwork (`illustration_id`) as the printing the title names, the listing is filed under the
   title's printing, marked with the copy's language (note starting `SAME_ART`). Otherwise it is held back with the
   reason (in the run's warnings and in the file); held-back listings are never shown.
5. **The language** (`text_likeness()`): the straightened photo's name bar and text box against
   the English and the Japanese (or the listing's language) picture of that printing; a listing
   whose text looks like the other language is held back.

`python3 shop_pullvault.py --out x.json.gz --debug folder` also writes each listing's scores per
printing (`scores.txt`) and the straightened photos, to check the picture check by eye.
`--products saved.json` reads a saved product list instead of the shop. The offline checks are
`python3 dev/test_pullvault.py` (made-up cards and photos; needs numpy and opencv).

First run (2026-10-25): 27 products, 4 looked like cards. The Tenth Doctor (Serial) → WHO #561z
and The One Ring (Borderless Foil Poster) → LTR #748, both as titled. "Cloud, Midgar Mercenary -
Pro Tour Promos (PTP) (Japanese)": the photos clearly show the Japanese Magic Spotlight promo
(PSPL #4), which has the same art as the English Pro Tour one (PPRO #2025-1); the owner chose to
show it under PPRO #2025-1, marked Japanese.
A draft night ticket is not a card.

### `build_combos.py`

Downloads Commander Spellbook's `variants.json.gz` (they ask sites to download the bulk file on
their own schedule rather than call their API from visitors' browsers), keeps each card's
`PER_CARD` most played combos, and writes shards keyed by the first two characters of the
card's oracle id.

### `build_tags.py`

Reads every Scryfall Tagger tag in `TAGS` with Scryfall's search API, 0.7 s apart (`PAUSE`),
waiting a minute after a 429, within a 15-minute budget (`MINUTES`). A tag that fails keeps its
published cards. **`TAGS` must contain every tag the site's `ROLE_LIST` uses**; add a tag here
when the site gets a role that needs it.

### `build_precons.py`

Reads MTGJSON's `DeckList.json`, keeps the decks of type "Commander Deck" (`DECK_TYPES`; about
200, from Commander 2011 on), and reads each one's file, one every `DECK_GAP` (0.5) seconds,
with `SetList.json` for the set names and parent sets. A card listed twice (foil and not) is
added up. Fewer than `MIN_DECKS` (100) decks, or more than a fifth of the files failing, keeps
the published file. The first run (2026-10-27) found 198 decks from 49 sets, every one 100
cards, in a 107 kB file.

## Running a builder on your computer

All three use only Python's standard library.

```sh
python3 build_prices.py --out site --previous https://warujie.github.io/warujie-prices/
python3 build_combos.py --out site/c --previous https://warujie.github.io/warujie-prices/
python3 build_tags.py   --out site/t --previous https://warujie.github.io/warujie-prices/ --force
python3 build_precons.py --out site --force
```

`build_prices.py` downloads Scryfall's bulk file and several hundred MB from MTGJSON. To work
offline, every source has an option to read a saved file instead (`--bulk`,
`--mtgjson-prices`, `--mtgjson-today`, `--tcgcsv`, `--ck-pricelist`, `--manapool-variants`,
`--cardtrader`…; see `python3 build_prices.py --help`), and `--quotes never`, `--lows never`,
`--offers never`, `--backfill never` switch parts off.

The site repository's end-to-end test (`dev/tests/e2e.py` there) runs `build_prices.py` and
`build_combos.py` over simulated days with fixtures, so **run the site's tests after changing a
builder or a file format** (clone both repositories side by side).

## Changing a file format

The site reads these files directly, so a format change is a change in two repositories:

1. Keep the old shape readable if you can (add fields rather than rename them); bump
   `FORMAT_VERSION` / `version` when you can't.
2. Change the reader in the site's `index.html` (see [data-formats.md](data-formats.md) for
   which function reads which file) and push it to the site's `staging`.
3. Update [data-formats.md](data-formats.md) and the site's `docs/data.md` in the same commits.
4. Merge the builder change to `main` here only when the site change is ready to publish.

## Troubleshooting

| Symptom on warujie.jp | Look at |
|---|---|
| No price history, listings or movers on any card | GitHub → warujie-prices → Actions → the last "Update price history" run. A red run publishes nothing, so yesterday's data stays up. |
| Data is a day old | Normal until 12:17 UTC plus the run time (the run can take over an hour with CardTrader) |
| ENNDAL GAMES prices missing on the Japan tab | Actions → "ENNDAL GAMES nightly": a red run (the shop refused, or it started too late) keeps the earlier data for up to a week. Its notice line says how many sets were read |
| PullVault listings missing | Actions → the "Update price history" run → the "Read PullVault's singles" step: its warnings list the listings held back and why (photos that don't show the printing the title names); a failed step keeps the published offers for 3 days |
| CardTrader listings missing | Token missing or expired (the run log says so); the 40-minute budget may also have ended before a set was reached |
| Role search falls back to text | `t/tags.json.gz` missing or broken; check the "Build the role tags" step |
| Combos missing on the preview page | `c/index.json`; check the "Build the Commander combos" step |
| The workflow fails at "Check this is the warujie-prices repository" | The workflow must live in a repository named exactly `warujie-prices` |
| "Docs match the code" fails with only site names (`loadPriceIndex()`…) missing | The site checkout failed (the site repository is private) but left an empty `Warujie` folder; `dev/check_docs.py` only counts a folder with a `docs/` folder as the other repository |

## Keeping these docs true

Every commit that changes a builder's behaviour, a published file, an option, the schedule or a
source updates this folder in the same commit (`data-formats.md` for file shapes, this file for
the rest). Run `python3 dev/check_docs.py` before pushing: it fails when a name the docs mention
no longer exists in the code. GitHub runs it too on pushes to `main` and on pull requests
(`.github/workflows/check-docs.yml`, check "Docs match the code"); it only reads files and never
publishes data. The site repository is private, so that check usually can't read it and runs
with `--partial`: names that only the site has are listed as not checked instead of failing.
The site's own check runs this repository's check in full on every push to its `staging` and
`main`, so a doc here that names a removed site function turns the site's check red.
