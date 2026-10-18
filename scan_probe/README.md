# Card scan probe (test branch only)

Phase 1 of the card scan plan: before anything is built into warujie.jp, measure how reliably a
phone photo of a card can be matched to the right card by its artwork.

- `build_index.py` chooses one picture per distinct look of every artwork (English where there
  is one, Japanese for Japanese-only art and for sagas/split/flip cards, any other language for
  an art printed only there, such as Phyrexian), downloads Scryfall's small pictures (10 a
  second at most; kept in the Actions cache) and fingerprints them.
- `common.py` is the fingerprint: the art region of the flattened card as a 256-bit DCT hash, a
  64-bit one, and a 4x4 colour grid; `export_model.py` adds two small image models (MobileNetV3,
  ONNX) to compare against. Round 3 adds candidates for real phone photos, whose own processing
  upset the DCT hash on some cards: difference hashes (`dh256`, `dv256`, signs of neighbouring
  brightness differences), equalised and CLAHE versions of the DCT hash, a 144-bit one, and a
  mask of each picture's reliable DCT bits (`h256r`).
- `real_photos.py` runs the owner's own photos locally against the committed fingerprints; the
  photos never go into the repository. Three modes: the photo as taken, the card's given
  corners, and "framed" (the photo moved and scaled so the card sits in the guide, as a visitor
  following the guide would hold it).
- `synth.py` makes believable phone photos (angle, light, glare, sleeve, blur, JPEG; round 4
  adds carpet and cloth, where the owner's photos showed the finder failing);
  `detect.py` finds the card's edges near the on-screen guide, and anywhere in a photo
  (`find_cards_anywhere`). Round 4's finder (`guide_outlines` in `matcher.py`, "detect4") smooths
  more and adds a texture-aware outline: lines whose two sides look alike (a row of carpet
  loops) count less (`discount_texture`); matching then also always tries the guide's wider
  search (`detect4_variants`), which rescued the photos where no outline was right.
- `evaluate.py` matches every test photo and writes `out/results.md`. Its "sure" rules are also
  calibrated with every photo standing in for a card that isn't in the index (a token): the
  scores with the true card left out must not be sure.

- `site_files.py` writes the two files the site's scanner reads (`scan_index.bin`: every
  fingerprint and its card number; `scan_cards.json`: oracle ids, the printing behind each
  fingerprint, and the "sure" rule), from the fingerprints in `out/`. `--rule BEST_MAX,RATIO`
  sets the rule by hand (one checked on the owner's photos) instead of the calibrated one.
  `site/` holds the current pair: the test site reads them from this branch until they are
  published with the daily data. The format is in the site's `docs/card-scan.md`.

Workflow: `.github/workflows/scan-probe.yml`, on push to this branch. Nothing here is used by
the live site or the daily price workflow (the test site reads `site/`), and this branch is never
merged as it is.
