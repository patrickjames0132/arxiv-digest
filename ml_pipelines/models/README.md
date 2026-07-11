# `ml_pipelines/models/` — trained model artifacts

The serialized output of the training pipelines, **committed** so a fresh
checkout serves predictions without anyone having to train first. Each pipeline
writes two files here:

- **`<name>.joblib`** — the joblib bundle the app loads: the fitted model (a
  scikit-learn estimator, or a fitted rule's parameters) plus its contract
  marker, any clamp bounds, and training metadata.
- **`<name>.metadata.json`** *(sidecar)* — the same metadata in human-readable
  JSON (the fitted params/coefficients, fit metrics, seed count, training date).
  The app never loads it; it's for eyeballing and for a git diff to show what a
  retrain moved.

## Current artifacts

- **`cite_budget.joblib`** / **`cite_budget.metadata.json`** — the adaptive
  landmark-budget model (`graph.adaptive_cite_limit`), loaded by
  `atlas.services.graph.budget`. Produced by `ml_pipelines/cite_budget/train.py`;
  see that package's README.
- **`latest_gap.joblib`** / **`latest_gap.metadata.json`** — the adaptive
  latest-band boundary (`graph.adaptive_latest_band`): the fitted density
  threshold `tau` + `max_span` cost cap deciding where a seed's Latest-Publications
  bands start (the recent edge of its landmark cluster). Loaded by
  `atlas.services.graph.bands`. Produced by `ml_pipelines/latest_gap/train.py`;
  see that package's README.

## Notes

- **Regenerated, not edited.** Never hand-edit these — rerun the pipeline. The
  git diff on a retrain is the record of what changed.
- **Loaded defensively.** The app tolerates a missing, corrupt, or
  contract-mismatched artifact by falling back to the non-adaptive default (the
  flat `cite_limit`, or the fixed `latest_band_years` span), so a bad or absent
  model degrades gracefully rather than breaking a graph build.
- **Version skew.** A `.joblib` carrying a pickled scikit-learn estimator
  (`cite_budget`) can fail to load if the runtime's scikit-learn diverges far
  enough; the graceful fallback then kicks in — retrain to refresh the pickle.
