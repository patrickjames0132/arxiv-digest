# The citation threshold — one predicate instead of four rules

A design settled by Patrick on **2026-07-20**, in a conversation that started
"I think I want to rip all of it out and start over" and ended with a rule that
fits on one line. This page is the record: the reasoning, the two wrong turns
that were corrected on the way, every decision made, and the plan for building
it.

It is written to be picked up **on another machine** — the fit needs the offline
S2 citations corpus, which lives on the Windows box. Read this first; it assumes
you have not seen the conversation.

**Status: designed, not built.** Nothing in `src/` has changed yet. This
supersedes the "Spike: is the SKIP rule what we actually want?" ticket in
[`../OnePager.md`](../OnePager.md) — see [Relationship to the spike](#relationship-to-the-spike).

---

## The problem

Today the landmark band is chosen by **rank within the seed's citers**, capped
per publication year. That rule is a function of *the whole ranked pool* — and
so the answer changes with the pool's shape. Which is why there are four rules,
not one:

| Scenario | Rule today |
| --- | --- |
| Offline corpus (whole history, ranked) | STOP — prefix the ranking |
| OpenAlex (server-sorted) | STOP — prefix the first page |
| Live S2, **complete** pool | STOP — prefix the ranking |
| Live S2, **truncated** pool | SKIP — band per year |
| Non-adaptive (any provider) | Decline the budget, ship to the payload guard |

Five behaviors, and the same seed can produce a visibly different graph
depending on which one it lands in. Supporting vocabulary:
[`landmark-vocabulary.md`](landmark-vocabulary.md) runs to 293 lines to keep
STOP, SKIP, prefix, banded, truncated, predicted and computed straight.

---

## The epiphany: a predicate, not a selection

> *"We simply split citations into landmarks vs latest publications via a
> number-of-citers threshold."* — Patrick, 2026-07-20

The structural reason this works is worth stating precisely, because it is the
whole justification for the rip-out:

**Every current rule is a *selection* — a function of the whole ranked pool.
The replacement is a *predicate* — a function of one citer.**

```
is_landmark(citer) -> bool          # reads ONE citer, never the others
```

A predicate is **order-free and pool-free**. It cannot depend on how the pool
was sorted, how deep it was paged, or whether it was truncated, because it never
looks at the pool at all. Scenario-independence is therefore not a pleasant
property of the new rule — it is a **theorem** about predicates. That is the
entire win, and it is why five behaviors collapse to one.

### Two bonuses that fall out

- **It pushes down into the query.** OpenAlex supports `cited_by_count:>N`
  server-side; the offline corpus is DuckDB, where it is a `WHERE` clause. Two
  of the three paths get *cheaper*, not merely simpler. Only the live S2 feed
  still has to page blind (no server-side sort or filter).
- **Truncation becomes a caveat instead of a branch.** The live S2 offset
  ceiling (~9,000 citers) is a **data** limit and does not go away. But today it
  forces a *different rule*; under a predicate the rule is identical and only
  the input differs. That is a sentence in the docs instead of a code path.

**Do not oversell this.** A truncated pool still cannot show landmarks it never
fetched. Same rule, different data. The graph does not become
provider-independent — it becomes *rule*-independent.

---

## Wrong turn #1 — a flat threshold biases the band to old papers

The first formulation keyed the threshold off **the seed's** publication year:
one scalar per graph.

```
is_landmark(citer) = citer.cited_by >= T(seed.year)      # WRONG
```

This fails because citation counts grow with a citer's own age, and a seed's
citers span many ages. *Attention Is All You Need* (2017) has citers from 2017
and citers from 2025. Any bar a 2017 citer clears, a 2025 citer essentially
cannot. The landmark band comes out **all-old** — a date split wearing a
citation costume.

Worse, that is a rediscovery of a bug the repo already paid for: it is the
**v5.5.0 landmark hole**, where a top-N prefix over a truncated pool stranded
2024–2025 entirely and left an 18-month gap before the Latest frontier. See
[`history.md`](history.md) (v5.5.0) and the 29-vs-84 DQN measurement in
[`landmark-vocabulary.md`](landmark-vocabulary.md).

---

## Wrong turn #2 — indexing the curve by calendar year

The correction was a threshold that varies with time. But it was first written
**indexed by calendar year** — `T[2010] = 400`, `T[2018] = 120` — which Patrick
rejected on the spot, correctly:

> *"In 2027, won't we have to retrain our model T[Y] to account for a new year?"*

Yes. And the fix is that the curve was never about calendar years. Index it by
the citer's **age**:

```
age = current_year - citer.year

T[0]  =   2      T[5]  =  40
T[1]  =   8      T[10] = 120
T[2]  =  15      T[16] = 400
```

*(Illustrative shape, not measured — the real numbers come from the fit.)*

Now the curve is **stationary**. "A 5-year-old paper needs ~40 citations to
stand out" is a claim about 5-year-old papers, not about the year 2021, so in
2027 a 2022 citer looks up `T[5]` and is automatically right. No new bucket
every January.

It is not *perfectly* stationary — publication volume grows, so citation counts
inflate across decades. That is a periodic refit on a decade timescale, not an
annual one.

### Why *not* "years since the seed"

Patrick's alternative was to index on `citer.year - seed.year`. It was rejected
because that quantity does not measure citation maturity:

| seed | citer | offset from seed | citer's actual age |
| --- | --- | --- | --- |
| Attention (2017) | a 2018 paper | +1 | **8 years** |
| some 2024 paper | a 2025 paper | +1 | **1 year** |

Both would look up `T[+1]`, but one has had eight years to earn citations and
the other one year. Bucketing them together is wrong-turn #1 rotated ninety
degrees. **Maturity is `now − citer.year`.**

---

## The two normalizations

Patrick's objection to the age-only curve was the one that produced the final
formula:

> *"A niche 2019 paper should never have only 3 clear the bar."*

Correct — and changing the *axis* does not fix it. Whatever it is indexed on, an
**absolute** bar is blind to how large the seed is. A niche paper's citers are
all low-cited, so a fixed bar sweeps up nearly nothing; a blockbuster's citers
are all high-cited, so the same bar sweeps up thousands.

These are **two independent problems**, and the design needs both fixed:

1. **Maturity** — so a young citer can compete with an old one.
   → index the curve on the **citer's age**.
2. **Dynamic range** — so a niche seed is not empty and *Attention* is not
   flooded. → scale the bar by the **seed's own** citation count.

### The rule

```
is_landmark(citer) =
    citer.cited_by >= max(FLOOR, T[now - citer.year] * S(seed.cited_by))
```

Three fitted things: the curve `T[]`, the seed scale `S()`, and the absolute
`FLOOR`.

`S(seed)` derives from the seed's citation count, which is known **before any
citer is fetched** — so the rule stays order-free and still pushes into a SQL
`WHERE` or an OpenAlex filter. The niche 2019 seed gets a low bar and a
populated graph; *Attention* gets a punishing one. Neither needs a cap to
rescue it.

### The floor is what creates the second category

`T[age]` alone breaks at the recent end: the bar for a two-month-old paper would
be ~2 citations, which is not a landmark of anything. `FLOOR` fixes that — and
in doing so it does something better.

The cohort curve binds for old citers; the floor binds for recent ones.
**Recent years fall below the floor wholesale, so they are "Latest" by
construction.** Recency never has to be legislated; it falls out.

Which gives a property the current design cannot express:

> **A paper migrates categories on its own.** A 2025 citer sits in Latest,
> accrues citations, crosses the floor, and becomes a Landmark — same rule, no
> code change, no re-fit. The boundary moves with the literature instead of
> with a release.

Patrick on this: *"I do like the idea that new papers get more citers over time,
and therefore it will eventually cross our threshold and become a landmark,
which is exciting!"*

---

## The predicate cap — the honest cost

A predicate answers yes/no for one citer without consulting any other. That is
the source of its scenario-independence, and also its one weakness: **nothing
knows how many yeses there are.** The landmark count is however many happen to
clear the bar.

The current design cannot have this problem, because "how many to ship" *is* its
output — rank-and-cap is bounded by construction. The predicate trades that
guarantee away. Unmitigated:

- A niche 2019 seed with 60 citers → maybe 3 clear the bar → a near-empty graph.
- *Attention* has 180,215 citers → even 2% passing is **~3,600 landmark nodes**.

`S(seed)` is the primary mitigation — it is precisely the term that bounds both
ends, which is why the fit objective is written in terms of landmark *count*
(below). The cap is the backstop.

### The resolution: sliders come back

Patrick's call, and it settles the cap question by demoting it:

> *"I like a combination of #1 (cap as post-filter) and #3 (trim at render),
> because I'm also thinking we should just keep the sliders permanently — yes,
> welcome back sliders! — and simply default the sliders to some number that
> caps huge renders, but the user can technically still hit those renders if
> they wish by pushing the slider (maybe they have a really good machine). In
> the end, we rip out the adaptive switch in the settings and keep the sliders
> visible always."*

So:

- **`PER_YEAR_CAP = 12` stops being semantics.** Today it partly *defines* what
  a landmark is. It becomes a **default slider position** — a transport/display
  guard. The threshold decides what is *true*; the slider decides what is
  *drawn*. That demotion is most of why the vocabulary doc collapses.
- **The adaptive switch is deleted**, not re-plumbed. `BuildShape.adaptive`,
  `_decline_budget`, and the whole adaptive/non-adaptive fork go.
- **Sliders are always visible**, defaulted to a sane cap, and the user can push
  past it.

---

## Decisions

All four settled by Patrick on 2026-07-20.

| # | Decision | Chosen | Rejected |
| --- | --- | --- | --- |
| 1 | **Threshold formula** | Age curve × seed scale, with a floor | Age curve alone (niche seeds sparse, blockbusters flood); seed-relative quantile (needs the whole pool → forfeits order-free evaluation *and* the server-side push-down) |
| 2 | **Unbounded output** | Sliders, always visible, display-only, defaulted to a sane cap | Slider drives the fetch (refetch per drag, cache key stays); pure self-limiting quantile |
| 3 | **Latest Publications** | Becomes the **complement** — one fetch, one threshold, two buckets | Stays a separately-fetched per-year banded relation |
| 4 | **Naming** | **Landmarks / Latest Publications** — drop only the word "Field" | Established/Emerging; Milestones/Latest |

### On the naming

Patrick's objection was that "Field Landmark" overclaims — *"one paper's field
landmark could be another paper's latest publication."* Right, but the
inaccuracy is narrower than it looks: **"landmark" is already a relative word**
— a landmark is defined by where you are standing. *"Field"* was doing all the
overclaiming.

So the fix is deleting one word. That is ~6 user-facing strings, and the
`landmark` identifier stays valid across all 51 code files that use it.

Known user-facing occurrences:

```
frontend/src/graph/GraphExplorer.tsx:94, 96
frontend/src/graph/theme.ts:70, 126
frontend/src/graph/controls/Legend.tsx:41
frontend/src/tour/steps.ts:163
```

`Established / Emerging` was the runner-up and remains the better *description*
of the new rule (a citation threshold literally measures "established", and it
makes the floor-crossing migration self-evident). It lost on churn.

### What the complement decision deletes

Choosing "Latest = the complement" means one citer fetch sorts into three
outcomes:

```
fetch citers once
  -> above the line     = Landmarks
  -> below + recent     = Latest Publications
  -> below + old        = dropped entirely
```

That third bucket — old *and* unremarkable — is correctly invisible, and it is
what makes the split meaningful rather than chronological.

Deletes: `bands.py` in full (`tail_edge`, `earliest_band_year`), `tau = 0.25`,
`max_span = 7`, `MIN_LANDMARK_YEARS = 10`, and the `ml_pipelines/latest_gap`
pipeline and its model.

---

## The provider-calibration problem

**Settled 2026-07-20: option 1, two curves.**

Citation counts are provider-specific: OpenAlex's `cited_by_count` and S2's
`citationcount` disagree for the same paper (different indexing coverage;
OpenAlex generally runs higher). A threshold fit on S2 corpus counts and applied
to the OpenAlex serving path is **miscalibrated**, and it would surface as the
OpenAlex graph carrying systematically more landmarks than the S2 one — exactly
the scenario-dependence the whole design is meant to buy out.

The options considered:

1. **Two curves** — `T_s2[]` from the corpus (huge sample, free) and
   `T_openalex[]` from an OpenAlex collection run. **Chosen: most correct.**
   Roughly doubles Phases 0–1.
2. *(Rejected)* One curve + a measured correction factor — fit on S2, then
   measure the OpenAlex/S2 count ratio on papers present in both and scale.
   Cheaper, but a single scalar cannot capture a ratio that varies by field,
   era, and venue type.
3. *(Rejected)* One curve, accept the drift — fastest, but reintroduces
   provider-dependent graph density.

**This choice and the narrow target range reinforce each other.** A 20–40
landmark band (below) leaves little slack: a miscalibrated provider would push
seeds out of range far more readily than it would out of a wider band. Two
properly fitted curves make the tight band attainable; a correction factor
probably would not.

Practical consequence for Phase 0: **two collection runs**, not one. The S2 half
comes from the corpus via DuckDB (fast, unlimited); the OpenAlex half needs a
throttled API run, which is what `cite_budget/collect.py` already does — it just
has to stop discarding `cited_by_count`. `S(median seed) = 1` is pinned
*per curve*, so each provider's `T[]` reads on its own scale.

---

## What the data situation actually is

Findings from inspecting the repo on 2026-07-20:

- **No existing corpus has per-citer citation counts.** All three
  `ml_pipelines/*/corpus.csv` files store `cited_by_count` for the **seed**
  only; `latest_gap`'s `citer_years` column is years-only. Every rule to date
  has been year-only, so the counts were never collected. **The new rule needs a
  new collection run.**
- **The offline S2 corpus has exactly the field needed.**
  `corpus/ingest.py:74` declares `'citationcount': 'BIGINT'` on the `papers`
  table, and the citations edge table already joins to it
  (`corpus/source.py:333` does `ORDER BY p.citationcount DESC`). Per-citer
  counts are one SQL join away, locally.
- **The fitted artifacts are git-tracked**, so the corpus dependency is
  fit-time only:

  ```
  src/ml_pipelines/cite_budget/model.joblib      tracked
  src/ml_pipelines/latest_gap/model.joblib       tracked
  src/ml_pipelines/*/corpus.csv                  tracked
  ```

  Fit on Windows → commit the artifact → every machine serves it. Nothing about
  *serving* needs the corpus. This is already the established pattern.
- **`cite_budget/collect.py` already requests the right field** —
  `select=id,display_name,publication_year,cited_by_count` (line 187) — and then
  discards the counts, keeping only years (`citer_years()`). One small edit from
  producing an OpenAlex fitting corpus, if option 1 or 2 above needs one.

### Why the Windows machine

The Mac's `config.json` has `storage.s2_corpus: null` — no corpus ingested. The
Windows box has the full citations corpus, and it is the better place to fit for
a reason beyond convenience: **sample size**. Fitting from OpenAlex means the
citers of ~64 seeds, throttled and slow. On the corpus you can sample
**thousands** of seeds and their complete citer sets in a couple of DuckDB
queries — no rate limits, no paging, no 9,000-citer ceiling. For fitting a
per-age curve *and* a seed-scale term jointly, that is the difference between a
curve you trust and one you hope generalizes.

---

## Build plan

Branch `citation-threshold` off `main`. Multi-session; Patrick reviews between
phases per the working agreement (browser test before any commit).

| Phase | Where | Work |
| --- | --- | --- |
| **0 — Data** | **Windows** | New `ml_pipelines/landmark_threshold/`. **Two collection runs** (calibration option 1): the S2 half samples seeds + their citers with `(year, citationcount)` from the corpus via DuckDB; the OpenAlex half extends `cite_budget/collect.py` to stop discarding `cited_by_count`. |
| **1 — Fit** | **Windows** | Research notebook under `research/`. Fit `T_s2[age]` and `T_openalex[age]`, plus `S()` and `FLOOR`, jointly against the 20–40 objective, `S(median) = 1` pinned per curve. **Report the achieved count spread**, not just the parameters. Also score the predicate against full-history STOP via `live_pool_validation` (see below). Commit both artifacts + `corpus.csv`. |
| **2 — Rule** | Either | `budget.py` → a small `threshold.py` predicate. Delete `bands.py`, `shape.py`'s adaptive machinery, `_decline_budget`, `cache_suffix()`. |
| **3 — Traversals** | Either | Rewire all three: OpenAlex gets a server-side `cited_by_count:>N` filter; corpus gets a SQL `WHERE`; live S2 pages and filters in memory. Latest becomes the complement. |
| **4 — Frontend** | Either | Sliders always visible, display-only trimming; drop the adaptive toggle from settings; `Field Landmarks` → `Landmarks` in the 6 strings above; update tour steps, legend, tooltips (the "in-app help tracks the UI" rule). |
| **5 — Docs** | Either | `landmark-vocabulary.md` and `predict-vs-compute.md` largely **delete**. Update `citation-coverage.md`, `constants.md`, `configuration.md`, package READMEs. Move the shipped item to `history.md`. This page becomes the record of *why*. |

### Fitting notes for Phase 1

- **The objective.** Fit so the **landmark count lands in a legible range for
  every seed** in the corpus — niche and blockbuster alike. This is a far
  better-posed objective than the per-year-cap sweep that produced
  `PER_YEAR_CAP = 12`. **Target range: 20–40 landmarks** (Patrick, 2026-07-20).

  An earlier proposal of 40–120 was rejected, and the reasoning matters because
  it is easy to re-derive the wrong number. 40–120 was chosen to bracket
  *today's* behavior — the retired cite-budget model's computed budgets averaged
  ~76 across the 58-seed validation corpus. But **that comparison is invalid
  under the new design**: today the landmark budget *is* the volume control,
  whereas under the predicate the **sliders** govern volume (display-only) and
  the threshold governs only the **split**. Tightening 76 → 30 does not shrink
  the graph; it reclassifies citers from Landmark into Latest.

  So the number is a **composition** target and must be chosen against the
  **default slider position**. If the default draws ~60 citer nodes and the
  threshold admits 76 landmarks, the user sees 60 landmarks and *zero* Latest —
  the second category is invisible at default settings. 20–40 leaves room for
  both halves to show. It also matches the semantic claim better: *Attention*
  has 180,215 citers, and the field-defining ones (BERT, GPT-3, ViT, T5,
  RoBERTa, Llama) number a few dozen. 76 is "notable papers"; 20–40 is
  "landmarks".

  **Fitting risk — report the achieved spread.** 20–40 is a 2× band where
  40–120 was 3×, and `S(seed)` must hold *every* seed inside it across ~3 orders
  of magnitude of seed size. With a single-parameter `S()` that only works if
  the citer citation distribution has a roughly constant power-law exponent
  across seeds — plausible, not guaranteed. Phase 1 must therefore report the
  **distribution of achieved landmark counts**, not just the fitted parameters.
  If a 2× band proves infeasible, that finding belongs at fit time, not in the
  browser; the fallbacks are a slightly wider band, a more flexible `S()`, or
  accepting a named set of outliers.
- **`T[]` and `S()` are degenerate unless one is pinned.** Only their *product*
  enters the rule, so the fit has a free scale parameter. **Pinned:
  `S(median seed) = 1`** (Patrick, 2026-07-20), which makes `T[age]` read as
  "the bar for a typical seed" and `S()` a pure multiplier. Pin it
  **per provider curve**, so `T_s2[]` and `T_openalex[]` each read on their own
  scale.
- **Fit on citers, not on all papers.** The corpus's `papers` table would give
  a `T[age]` curve over the whole literature in one `GROUP BY`, but that is the
  wrong population — citers of a notable seed skew higher-quality than the
  global paper population, and citers are what the rule classifies. Sample
  seeds, pull *their* citers, fit on those.
- **Keep the worked examples.** Hawking Radiation, DQN, QMIX, and *Attention*
  are carried through every study (`is_worked_example`) so an absurd number gets
  caught before an aggregate hides it. Do the same here.

---

## Open items

**None blocking.** All three former open items were settled by Patrick on
2026-07-20: provider calibration takes **option 1, two curves**; the target
range is **20–40 landmarks**; and **`S(median seed) = 1`** is pinned per curve.
Phase 0 can start.

Two things to decide *during* the build rather than before it:

1. **The default slider position.** The 20–40 target was chosen as a composition
   ratio against it, so the two numbers are coupled — pick the slider default in
   Phase 4 with the fitted landmark counts in hand, not independently.
2. **What to do if the 2× band proves infeasible** — see the fitting risk above.
   Phase 1 reports the achieved spread; decide then.

---

## Relationship to the spike

[`../OnePager.md`](../OnePager.md) → Citations & graph data carries **"Spike: is
the SKIP rule what we actually want?"** (Patrick, 2026-07-17), which asked
whether SKIP is a landmark band or padding, whether the truncated path needs an
honest UI label, and — as its option (3) — whether there is *"a defensible
middle — e.g. **SKIP with a citation floor**."*

This design is that middle, generalized: a citation floor that is age-adjusted
and seed-scaled, applied to *every* path rather than only the truncated one. It
answers the spike rather than needing it run.

One caveat carried forward from the spike's success criterion — *"whatever rule
the truncated pool ends up with should land as close as possible to what the
STOP rule would ship if the seed's full citation history were reachable"* — is
still worth measuring. `live_pool_validation` simulates the exact truncated pool
from the offline corpus, so the new predicate can be scored against the
full-history band with machinery that already exists. Phase 1 should do it.

---

## Receipts

- [`landmark-vocabulary.md`](landmark-vocabulary.md) — every term in the design
  being replaced (STOP, SKIP, pool, truncated, age origin, the three senses of
  "anchor"). Mostly deleted by this work; read it to understand what is going.
- [`predict-vs-compute.md`](predict-vs-compute.md) — why the budget model was
  retired, and the house pattern *"learn constants offline, execute rules
  online, predict only what you can't observe."* The new rule is that pattern
  again: `T[]`, `S()` and `FLOOR` are fitted offline; the predicate runs online.
- [`citation-coverage.md`](citation-coverage.md) — the dual-source citation
  decision. Read before touching provider logic.
- [`history.md`](history.md) — v4.5.0 (the model), v4.6.0 (the negative-R²
  latest-gap finding), v5.5.0 (the landmark hole that wrong turn #1 would have
  recreated), v5.11.0 / v5.13.0 (the compute paths taking over).
- `src/atlas/services/graph/budget.py`, `bands.py`, `shape.py` — the three
  modules this design rewrites or deletes.
