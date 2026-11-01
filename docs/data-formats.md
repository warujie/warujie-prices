# Published files

Everything is published to the private R2 bucket `warujie-price-data` (read by the site at
`warujie.jp/data/`). Money is in
**cents** (integers) everywhere; a missing value is `null` (or left off the end of an array).
"Shard" files split data by the first two hex characters of an id, so a card page downloads
one small file instead of everything.

| Path | Built by | Read on the site by |
|---|---|---|
| `index.json` | `build_prices.py` | `loadPriceIndex()` |
| `h/<xx>.json.gz` | `build_prices.py` | `loadPriceShard()`, `drawPriceHistory()` |
| `q/<xx>.json.gz` | `build_prices.py` | `loadQuoteShard()`, `loadCardQuotes()` |
| `movers.json` | `build_prices.py` | `loadMovers()`, `renderHomeMovers()` |
| `cheap.json.gz` | `build_prices.py` | `loadCheapest()`, `deckCost()` (deck prices and Arena wildcards on the metagame tab and deck pages) |
| `ids.json.gz` | `build_prices.py` | nobody (the builder's own cache: MTGJSON ids → Scryfall ids, kept a week) |
| `c/index.json`, `c/<xx>.json.gz` | `build_combos.py` | `loadComboIndex()`, `loadComboShard()` |
| `t/tags.json.gz` | `build_tags.py` | `loadTags()` |
| `precons.json.gz` | `build_precons.py` | `loadPrecons()`, `renderSetPrecons()`, `drawPreconMenu()`, `openPrecon()` |

## `index.json`

```json
{
  "version": 1, "updated": "2026-10-15T13:02:11Z", "today": "2026-10-15",
  "dates": ["2026-06-20", "…", "2026-10-15"],
  "shards": ["00", "01", "…", "ff"],
  "series": 4, "series_names": ["usd", "usd_foil", "eur", "eur_foil"],
  "source": "…", "sources": ["…"],
  "quotes_date": "2026-10-14",
  "providers": {"tcgplayer": "USD", "cardkingdom": "USD", "cardmarket": "EUR", "tcgplayer_low": "USD", "cardmarket_low": "EUR", "…": "…"},
  "offers": {"cardkingdom": "…", "manapool": "…", "cardtrader": "…", "enndal": "2026-10-17T17:00:00Z", "pullvault": "2026-10-25T12:20:00Z"},
  "ct_resume": 0,
  "backfill_tried": "2026-06-20"
}
```

`dates` is the history's timeline: daily for the last 120 days, Mondays before that.
`quotes_date`, `providers` and `offers` appear only when those parts were read; `offers` says
when each listing source was read (for `enndal`, the night ENNDAL GAMES was read).

## `h/<xx>.json.gz`: price history

Gzipped JSON, one file per first two characters of the **Scryfall printing id** (256 files).

```json
{"dates": ["…same as index.json…"],
 "p": {"<scryfall id>": [[usd…], [usd_foil…], [eur…], [eur_foil…]]}}
```

Each of the four series has one value per date (cents or `null`). History is kept for English
printings; the site maps a Japanese printing to its English twin first.

## `q/<xx>.json.gz`: today's shop prices, listings and links

```json
{"date": "2026-10-14",
 "p":  {"<scryfall id>": {"<shop>": [sell, sell_foil, buy, buy_foil]}},
 "l":  {"<scryfall id>": [["ck", 0, "NM", 1299, 4, ""], ["ct", 1, "SP", 950, 1, "JA", "DE"], ["ed", 0, "NM", 6980, 2, "JA"]]},
 "lk": {"<scryfall id>": {"tcg": 123456, "cm": 654321, "ck": ["<url>", "<foil url>"], "mp": "<url>", "ct": 98765,
                          "ed": ["<path>", "<foil path>"], "pv": "<product handle>"}}}
```

- **`p`**: shop prices from MTGJSON's daily file (`tcgplayer`, `cardkingdom`, `cardsphere`,
  `cardmarket`, `manapool`…) plus `tcgplayer_low` and `cardmarket_low` (lowest listings, from
  TCGCSV and Cardmarket's price guide; only the first two slots). Currencies are in
  `index.json` `providers`.
- **`l`**: offers with stock: `[shop, foil (0/1), condition, cents, copies, language, country]`.
  Shops: `ck` Card Kingdom, `mp` Mana Pool, `pv` PullVault (US market; PullVault's condition is
  empty when the listing doesn't state one, and a copy in another language has that language), `ct` CardTrader (EU market; `country` is
  the seller's), `ed` ENNDAL GAMES (Japan market, `OFFER_MARKETS`: **the price is in yen**, not
  cents; conditions NM and EX; language `JA` or empty for English). Language is empty for
  English. At most `LISTINGS_PER_FINISH` per market and finish, cheapest first.
- **`lk`**: product ids or URLs for links straight to the product: TCGplayer product id,
  Cardmarket product id, Card Kingdom URLs (non-foil, foil), Mana Pool URL, CardTrader
  blueprint id, ENNDAL GAMES product paths (non-foil, foil; after `https://www.enndalgames.com/`),
  PullVault product handle (after `https://pullvault.gg/product/`).

`l` and `lk` are present only when offers were read.

## `enndal.json.gz` (not published): one night of ENNDAL GAMES

Written by `shop_enndal.py` (`nightly()`, `save()`) and kept as the "enndal" artifact of the
ENNDAL GAMES nightly workflow, encrypted (`enndal.json.gz.enc`, AES-256 with the
`CLOUDFLARE_R2_TOKEN` secret as the password) because a public repository's artifacts can be
downloaded by anyone signed in to GitHub; older "enndal" artifacts are deleted. Decrypted and
read by `build_prices.py --enndal`. Products in stock only;
nothing of the shop's pages is kept besides these values.

```json
{"version": 1, "updated": "2026-10-17T17:00:00Z", "read_tonight": 210, "sets": 210,
 "cats": {"2363": {"name": "ブルームバロウ", "read": "2026-10-17T17:00:00Z",
                   "p": [["blb", "2", "normal", "<product path>", [["JA", "NM", 999, 11], ["EN", "NM", 799, 2]]]]}}}
```

Each product: Scryfall-style set code (`SET_ALIASES` fixes the codes that differ), collector
number without leading zeros, finish (`normal`, `foil`, `etched`), its path on the shop, and an
offer per language and condition `[language, condition, yen, copies]`.

## `pullvault.json.gz` (not published): one day of PullVault

Written by `shop_pullvault.py` (`nightly()`, `save()`) in the price workflow and read by
`build_prices.py --pullvault` in the same run; not kept or published. Prices in cents (USD).

```json
{"version": 1, "updated": "2026-10-25T13:41:36Z", "products": 27,
 "listings": [
  {"handle": "the-tenth-doctor-serial-universes-beyond-doctor-who-who", "title": "The Tenth Doctor (Serial) - …",
   "cents": 165000, "qty": 1, "cond": "", "lang": "EN", "foil": true,
   "id": "<scryfall id>", "set": "who", "number": "561z", "inliers": 422, "likeness": 0.87, "photo": 0, "text": [0.8, 0.3]},
  {"handle": "…", "title": "…", "cents": 72999, "qty": 1, "cond": "", "lang": "JA", "foil": false, "id": "…",
   "set": "pspl", "number": "4", "inliers": 432, "likeness": 0.963, "photo": 0,
   "note": "the title fits PPRO #2025-1, but the photos clearly show PSPL #4"},
  {"handle": "…", "title": "…", "cents": 1000, "qty": 1, "cond": "", "lang": "EN", "foil": false,
   "held": "the photos look like M11 #146, but the title fits M10 #146"}]}
```

A listing has either the printing it was matched to (`id`, with the picture check's numbers:
features that fit, likeness of the straightened photo, which photo, and the name-and-text
likeness to the English and the other-language picture) or `held`, the reason it is not shown.
`note` marks a listing shown under the printing its photos clearly show although its title named
another, or (starting "the photos show the same art as") a copy in another language filed under
the title's printing with the same art. Products that turn out not to be cards keep only `handle`, `title` and `held`.

## `movers.json`

```json
{"version": 1, "updated": "…", "today": "2026-10-15",
 "windows": {
   "7": {"from": "2026-10-08",
         "all": {"up": [ENTRY, …], "down": [ENTRY, …]},
         "eur": {"up": […], "down": […]}}}}
```

Windows `"1"`, `"7"`, `"30"` (a window is missing until the history is long enough). `all` is
the US market in dollars (TCGplayer), `eur` is Cardmarket in euros. Up to 50 entries per list,
one printing per card (its biggest move). Each entry:

| Key | Meaning |
|---|---|
| `id` | Scryfall printing id |
| `o` | oracle id |
| `n`, `s`, `sn`, `c`, `r` | name, set code, set name, collector number, rarity |
| `col` | colours |
| `img` | small picture URL |
| `f` | 1 when the foil price moved (no non-foil price) |
| `now`, `then`, `pct` | today's and the earlier price in cents, change in % |

## `cheap.json.gz`: each card's cheapest printing

```json
{"version": 1, "date": "2026-10-15", "fields": ["usd", "eur", "arena", "tix"],
 "cards": {"Lightning Bolt": [74, 110, "c", 2], "Island": [5, 4, "c", 1], …}}
```

One row per card name (two-part cards under their full Scryfall name). `usd` is the lowest
TCGplayer non-foil price of any paper printing and `eur` the lowest Cardmarket one, in cents;
a card with no non-foil price at all falls back to its lowest foil price (`note_cheapest()`,
`finish_cheapest()`). `arena` is the lowest MTG Arena rarity among its Arena printings
(`c`, `u`, `r`, `m`), or `""` when it isn't on Arena. `tix` is the lowest MTGO price of any
MTGO printing (Scryfall's `prices.tix`, Cardhoarder's price, in hundredths of a ticket; MTGO-only
printings count here), or `null` when no MTGO printing has a price; added 2026-10-31 for the
site's MTGO（tix）switch, so files from before have three fields. Excluded printings (the same rules as
the rest of the build) don't count for `usd` and `eur`.

## `c/`: Commander combos

`c/index.json`: `{"version": 2, "generated", "source": {"name", "url", "timestamp"}, "combos",
"cards", "per_card", "shards": [...]}`.

`c/<xx>.json.gz`, keyed by the first two characters of the card's **oracle id**:

```json
{"fields": ["id", "identity", "cards", "templates", "results", "mana", "popularity", "legal", "prerequisites", "steps"],
 "formats": ["standard", "pioneer", "modern", "legacy", "vintage", "premodern", "commander", "pauper"],
 "cards": [["<name>", "<oracle id>"]], "results": ["<result text>", …],
 "combos": [[…one array per combo, in the order of "fields"…]],
 "by": {"<oracle id>": [combo positions, most played first]},
 "total": {"<oracle id>": 57}}
```

Inside a combo, `cards` is `[[card position, quantity, zones], …]` (zones as letters, e.g. `B`
battlefield, `H` hand), `templates` are "any card that…" requirements, `results` is a list of
positions in `results`, `legal` is a bit mask over `formats`, and `prerequisites` and `steps` are
English text (at most `MAX_TEXT` characters). The site's `combo_ja.js` translates them. `total` is how many combos the
card has in all (the site links to Commander Spellbook for the rest).

## `t/tags.json.gz`: role tags

```json
{"version": 1, "generated": "2026-10-12", "source": "…",
 "tags": ["anthem", "boardwipe", "…"],
 "cards": [["<first 12 characters of oracle id>", 1234, 3, 17, 40]]}
```

Each card row: shortened oracle id, EDHREC rank (or `null`), then the positions of its tags in
`tags`. The site's `ROLE_LIST` names roles by these tag names.

## `precons.json.gz`: Commander precon deck lists

```json
{"version": 1, "generated": "2026-10-27T15:04:02Z",
 "source": {"name": "MTGJSON", "url": "https://mtgjson.com/", "license": "MIT"},
 "sets": {"blc": {"name": "Bloomburrow Commander", "parent": "blb", "date": "2024-08-02"}},
 "decks": [{"id": "AnimatedArmy_BLC", "name": "Animated Army", "set": "blc", "date": "2024-08-02",
            "commander": [[1, "Bello, Bard of the Brambles"]],
            "main": [[1, "Sol Ring"], [1, "Discovery // Dispersal"]]}]}
```

Decks newest first. `id` is MTGJSON's deck file name (the site's `?view=import&precon=<id>`);
set codes are lower case, as Scryfall's; `parent` is the main set a Commander set belongs to (empty
for sets like Commander 2021). Cards are `[count, English name]`, two-part cards written
`A // B`; partner commanders are two rows of `commander`. Deck names are English only.
