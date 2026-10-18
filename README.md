# warujie-prices

Daily MTG price history and Commander combo data for 悪知恵 (warujie), published to a private Cloudflare R2 bucket that the site reads through its Worker (and, during the move, with GitHub Pages at https://warujie.github.io/warujie-prices/).

- `build_prices.py` builds the data (Scryfall: TCGplayer USD, Cardmarket EUR; MTGJSON: past prices and today's shop prices; TCGCSV and Cardmarket's price guide: lowest listings; Card Kingdom's and Mana Pool's public price lists: offers by condition with the copies in stock; CardTrader's API: sellers in Europe, when the `CARDTRADER_TOKEN` secret is set).
- `.github/workflows/update-prices.yml` runs it every day at 12:17 UTC and publishes the result. Nothing is committed, so the repository never grows.
- `build_combos.py` builds the Commander combo data (from Commander Spellbook's bulk file) into `c/`, rebuilt weekly.
- `build_tags.py` builds the role tags (what each card does - removal, card draw, ramp... - from Scryfall Tagger's oracle tags) into `t/`, rebuilt weekly, for the site's role search and similar cards.

**Developers:** start with [`docs/README.md`](docs/README.md) (how it works) and [`docs/data-formats.md`](docs/data-formats.md) (the published files).
