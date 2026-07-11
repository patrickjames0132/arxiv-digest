# `latest_gap` — closing the landmark→latest gap (write-up)

The exploratory notebook behind the adaptive latest-band feature
(`graph.adaptive_latest_band`). It's the **argument**; the shipped, re-runnable
version lives in `ml_pipelines/latest_gap/`, and the app loads the model that
pipeline produces (served by `atlas.services.graph.bands`).

## The question

A seed's *Latest Publications* relation fills recent years evenly, one
`cited_by_count` query per year, over a **fixed** span (`latest_band_years=5`).
For an old seed whose *Field Landmarks* tail off years before that fixed start,
the timeline shows a dead stretch between the last landmark and the first band.
Where should the bands *start*, per seed, so that gap closes?

## What `analyze.ipynb` shows

1. **The gap is real, and old-seed-specific.** ~10 of 64 seeds show a ≥ 3-year
   visible gap under the fixed span — all old papers whose landmark cluster ends
   well before the fixed window.
2. **Seed features can't predict the fix.** Reusing the `cite_budget` recipe
   (regress on age + log-citations) scores a *negative* CV R²: the boundary
   depends on the *shape* of each seed's landmark distribution, not its
   age/citations. So the model operates on the distribution directly — which the
   build already has in hand (landmarks are fetched before the bands).
3. **A robust quantile, clamped and capped.** Start the bands at the `q`-quantile
   of the landmark years, clamped to only widen (young seeds unchanged) and
   capped at `max_span` years (bounded query cost). The knee lands at
   **q=0.85, max_span=9**; the anchors behave sensibly (Hawking/DQN widen back to
   meet their clusters, QMIX/Attention unchanged), and two misdated-future citers
   don't move the boundary.

The notebook reads the corpus from `ml_pipelines/latest_gap/corpus.csv` (the
single copy) and reproduces the analysis inline for the write-up.

## Re-running

```bash
uv run --group research jupyter nbconvert --execute --to notebook \
    --inplace research/latest_gap/analyze.ipynb
```

To refresh the underlying data or the shipped model, use the pipeline
(`python -m ml_pipelines.latest_gap.train --refresh`), then re-execute this
notebook so the write-up matches. The productionized method, parameters, and
tests are documented in `ml_pipelines/latest_gap/README.md`.
