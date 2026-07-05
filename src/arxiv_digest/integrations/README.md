# `integrations`

External-service clients — every module that talks to a remote API. Modules
here own their own HTTP plumbing, rate-limit etiquette, and caching keys;
the `services` package (Phase 3) composes them into domain logic.

- **`semantic_scholar/`** — the S2 Academic Graph + Recommendations client
  (the paper-data backbone). Its own package; see its own README.
- **`arxiv_client/`** — seed search against arXiv itself (finds the starting
  paper; `semantic_scholar` builds the graph around it once picked). Its
  own package; see its own README.
- **`fulltext.py`, `figures.py`, `huggingface.py`, `taxonomy.py`** — not yet
  ported (rest of Phase 2).
