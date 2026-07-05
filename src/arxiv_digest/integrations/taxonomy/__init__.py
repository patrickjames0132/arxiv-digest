"""The app's controlled subject vocabularies — two, at two granularities.

* **arXiv categories** — the ~155 fine-grained arXiv codes (``cs.LG``,
  ``math.PR``, …) in 8 areas, each a ``{code, name}`` pair. arXiv-specific, kept
  for labelling an arXiv paper's own category tags (same spirit as the ar5iv
  side of the ``arxiv`` package). Bundled as ``taxonomy.json``.
* **S2 fields of study** — Semantic Scholar's own much coarser ~20 fields
  (``Computer Science``, ``Mathematics``, …). This is what the S2 seed-search
  filter uses; S2's ``/paper/search`` filters on exactly these.

Modules:

* ``loader``     — loads + memoizes the bundled ``taxonomy.json`` (arXiv data).
* ``categories`` — the arXiv query API: ``groups()`` (the areas tree) and
  ``valid_codes()`` (the validation set).
* ``fields``     — the S2 fields-of-study list: ``all_fields()`` and
  ``valid_fields()`` (a small inline vocabulary, no JSON).

The odd one out among the integrations: static/inline data, no HTTP, no cache —
but split into a package like its neighbours so they all read alike.
"""

from __future__ import annotations

from .categories import groups, valid_codes
from .fields import all_fields, valid_fields

__all__ = ["all_fields", "groups", "valid_codes", "valid_fields"]
