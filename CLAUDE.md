# warujie-prices — working notes

The data behind warujie.jp's prices, listings, price movers, Commander combos and role search.
The site is in `warujie/Warujie` (private); its `CLAUDE.md` has the owner's full rules. This
repository is public, so it holds no private details. Keep it public: on GitHub's free plan,
Pages (which the site reads every file from) and unlimited Actions minutes need a public
repository, and the price history lives only in the published Pages files.

**Start with [`docs/README.md`](docs/README.md)** (how the builders and the daily workflow work)
and [`docs/data-formats.md`](docs/data-formats.md) (every published file).

## Rules (the owner's, keep them)

1. **`main` is live.** A push that changes a builder or the workflow on `main` runs the workflow
   and publishes to GitHub Pages at once, which warujie.jp reads immediately. Work on a branch,
   test locally (and with the site's `dev/tests/e2e.py`), and merge to `main` only when the owner
   says "publish", as for the site.
2. **Permitted sources only:** Scryfall (bulk files and API, with a real User-Agent and pauses),
   MTGJSON, TCGCSV, Cardmarket's price guide, Card Kingdom's and Mana Pool's public price lists,
   CardTrader's API (with the token), Commander Spellbook's bulk file, Scryfall Tagger tags, and
   ENNDAL GAMES (permission 2026-10-15: once a night 2-6am Japan time, one page every 4 s; see
   `shop_enndal.py`). Any new source, above all Japanese shops, needs the owner's permission
   first; never scrape.
3. **No secrets in the repo or in chat.** The CardTrader token is the GitHub secret
   `CARDTRADER_TOKEN`; never print it, and never ask the owner to paste a token.
4. **The published data is the history.** Nothing is committed; each run builds on yesterday's
   published files. Never let a run publish an empty or partial history (the builders refuse;
   keep it that way).

## Documentation (keep it true)

- **Every commit that changes a builder's behaviour, a published file, an option, a source or
  the schedule also updates `docs/` in the same commit.** File shapes go in
  `docs/data-formats.md`; everything else in `docs/README.md`.
- A file-format change also needs the site's reader and its `docs/data.md` changed (see
  "Changing a file format" in `docs/README.md`).
- Name code by function or constant, never by line number.
- Before pushing, run `python3 dev/check_docs.py` (with the site repository cloned next to this
  one): it fails when a name the docs mention no longer exists in the code. GitHub runs it on
  pushes to `main` and on pull requests (`.github/workflows/check-docs.yml`); the site repo is
  private, so there it skips names only the site has (`--partial`), and the site's own check
  runs this one in full.
