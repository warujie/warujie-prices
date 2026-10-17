# warujie-prices developer guide

This repository builds the price, listing, combo and role-tag data that
[warujie.jp](https://warujie.jp) reads, and publishes it on GitHub Pages at
`https://warujie.github.io/warujie-prices/`. The site itself is in
[warujie/Warujie](https://github.com/warujie/Warujie) (a private repository; its `docs/` folder
explains the site). This repository stays public: GitHub Pages and unlimited Actions minutes
are free only for public repositories on the free plan.

- The owner's rules (which outside data may be used, no secrets in the repo) are in
  [`../CLAUDE.md`](../CLAUDE.md) and in the site repository's `CLAUDE.md`.
- The format of every published file is in [data-formats.md](data-formats.md).

## The parts

| File | What it builds | Into | Source |
|---|---|---|---|
| [`build_prices.py`](../build_prices.py) | Price history, today's shop prices, lowest listings, offers with stock, price movers | `site/index.json`, `site/h/`, `site/q/`, `site/movers.json`, `site/cheap.json.gz`, `site/ids.json.gz` | Scryfall `default_cards` bulk file (TCGplayer USD, Cardmarket EUR), MTGJSON (history backfill, shop prices), TCGCSV and Cardmarket's price guide (lowest listings), Card Kingdom's and Mana Pool's public price lists, CardTrader's API, last night's ENNDAL GAMES data |
| [`shop_enndal.py`](../shop_enndal.py) | ENNDAL GAMES' in-stock singles in yen (Japan), read once a night; also matches them to printings for `build_prices.py` | `enndal.json.gz` (an artifact, not published) | ENNDAL GAMES' shop pages, with the shop's permission |
| [`build_combos.py`](../build_combos.py) | Commander combos per card | `site/c/` | Commander Spellbook's bulk file |
| [`build_tags.py`](../build_tags.py) | Role tags (removal, draw, ramp…) and EDHREC rank per card | `site/t/tags.json.gz` | Scryfall Tagger oracle tags, via Scryfall's search API |
| [`.github/workflows/update-prices.yml`](../.github/workflows/update-prices.yml) | Runs the three builders and publishes `site/` to GitHub Pages | | |
| [`.github/workflows/enndal-nightly.yml`](../.github/workflows/enndal-nightly.yml) | Runs `shop_enndal.py` at 2am Japan time and keeps the result as the "enndal" artifact | | |

**Nothing is committed by the workflow.** Each run reads yesterday's published data from the
Pages address (`--previous`), adds today, and publishes the result. The repository never grows,
and the published site *is* the history: if a run publishes a broken history, the next run
builds on it. That's why `build_prices.py` stops without publishing when the old history can't
be read or Scryfall's export looks incomplete (`--min-cards`, default 20,000 priced printings).

## When it runs

`update-prices.yml` runs:

- every day at **12:17 UTC** (21:17 in Japan), after Scryfall's daily export;
- when `build_prices.py`, `build_combos.py`, `build_tags.py` or the workflow changes on `main`;
- by hand ("Run workflow" in GitHub Actions).

`enndal-nightly.yml` runs every day at **17:00 UTC** (2:00 in Japan) and stops by 20:45 UTC
(5:45 in Japan): that is what we told ENNDAL GAMES. `shop_enndal.py` refuses to start outside
that window, so a run by hand in the daytime does nothing. The evening price update then uses
that night's data, so ENNDAL's stock on the site is from the night before.

`build_combos.py` and `build_tags.py` rebuild only when the published data is older than 7 days;
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
   Without `--enndal`, the published ENNDAL offers are kept for up to `KEEP_DAYS`. The cheapest
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

## Running a builder on your computer

All three use only Python's standard library.

```sh
python3 build_prices.py --out site --previous https://warujie.github.io/warujie-prices/
python3 build_combos.py --out site/c --previous https://warujie.github.io/warujie-prices/
python3 build_tags.py   --out site/t --previous https://warujie.github.io/warujie-prices/ --force
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
| CardTrader listings missing | Token missing or expired (the run log says so); the 40-minute budget may also have ended before a set was reached |
| Role search falls back to text | `t/tags.json.gz` missing or broken; check the "Build the role tags" step |
| Combos missing on the preview page | `c/index.json`; check the "Build the Commander combos" step |
| The workflow fails at "Check this is the warujie-prices repository" | The workflow must live in a repository named exactly `warujie-prices` |

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
