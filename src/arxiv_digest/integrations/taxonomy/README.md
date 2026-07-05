# `integrations.taxonomy`

The app's controlled subject vocabularies — **two**, at two granularities:

- **arXiv categories** — the ~155 fine-grained arXiv codes (`cs.LG`, `math.PR`,
  …) grouped into 8 areas, each a `{code, name}` pair. arXiv-specific.
- **S2 fields of study** — Semantic Scholar's own much coarser ~20 fields
  (`Computer Science`, `Mathematics`, …).

## Why it exists

Two different consumers want two different vocabularies:

- The **S2 seed-search filter** needs S2's fields of study — S2's
  `/paper/search` filters on exactly these (`fieldsOfStudy`). This is the live,
  in-use vocabulary now that search runs on Semantic Scholar.
- The **detail panel** (planned) will label an arXiv paper's own category tags
  (`cs.LG` → "Machine Learning") — for arXiv papers only, the same
  arXiv-specific enrichment spirit as the `arxiv`/ar5iv package. A paper's *own*
  categories come from arXiv metadata, not S2; this package only describes *what*
  categories exist.

Keeping both here makes this the one home for "controlled subject vocabularies,"
rather than scattering them.

## How it's structured

The odd one out among the integrations — static/inline data, so no HTTP client
and no cache table. Split into a package like its neighbours so they read alike:

```
loader.py     — loads + memoizes the bundled taxonomy.json (arXiv data access)
     ↓
categories.py — arXiv query API: groups(), valid_codes()
fields.py     — S2 fields of study: all_fields(), valid_fields()  (inline list)
```

- **`loader.py`** — `data()`, an `@lru_cache`'d parse of the bundled
  `taxonomy.json` (arXiv). Public within the package because `categories`
  queries it across the module boundary — the file-load analogue of the HTTP
  packages' `client.fetch_*`.
- **`categories.py`** — `groups()` (the arXiv areas-with-categories tree) and
  `valid_codes()` (an `@lru_cache`'d `frozenset` of every code).
- **`fields.py`** — `all_fields()` (S2's ~20 fields, alphabetical) and
  `valid_fields()`. A small fixed vocabulary, inlined as a tuple — no bundled
  JSON, since each value is already its own human-readable label. (`all_fields`,
  not `fields`, so it doesn't shadow the `fields` module when re-exported.)

`__init__.py` re-exports `groups`, `valid_codes`, `all_fields`, `valid_fields`.

## Design decisions worth knowing

- **arXiv data is a bundled file; S2 data is inline.** The arXiv taxonomy is 155
  code+name pairs (worth a generated JSON); the S2 fields are ~20 plain strings
  (a tuple is clearer than a file). Different shapes, different treatment.
- **No `code → name` lookup for arXiv yet.** The API answers "what areas exist"
  and "is this code real", but not "what's the label for `cs.LG`". The planned
  detail-panel use needs that; it'll be added with that feature, not now.
- **S2 field casing is Title Case** (`"Computer Science"`), matching what S2
  returns on paper objects and accepts in the `fieldsOfStudy` filter. If it ever
  differs live, `S2_FIELDS` is the one tuple to edit.

## Who uses it, and how/why (traced)

- **`services/search.py`** (ported) — `live_search` forwards an S2 fields filter
  to `s2.search_papers` (`fieldsOfStudy`); its values come from this package.
- **`routes/search.py`** (not yet ported) — `GET /api/taxonomy` serves a picker,
  and seed search validates a submitted filter against `valid_fields()` (S2
  fields) — the arXiv `valid_codes()` path retires with the arXiv search bar.
- **Detail panel (planned, not built)** — `groups()` / a future `code → name`
  lookup to label an arXiv paper's own category tags in the detail window.

## Testing

`test_loader.py` — `data()` returns the parsed arXiv document and is memoized.
`test_categories.py` — 8 arXiv areas, a known code's label (`cs.LG` →
"Machine Learning"), `valid_codes()` covers exactly the codes in `groups()`,
memoization. `test_fields.py` — the S2 vocabulary is the expected 23 fields in
alphabetical order, and `valid_fields()` rejects junk (and arXiv codes). All
offline (static/inline data).
