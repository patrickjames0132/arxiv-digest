"""Seed search against the arXiv API (via the `arxiv` package).

A relevance-ranked hunt across all of arXiv to find the paper you want to drop
into the graph (by keywords, title, author, or a pasted id / URL). Its id is
then handed to the Semantic Scholar graph builder.

Split by concern:

* ``clauses`` — id detection (``ID_RE``) and the date-range/category filter
  clauses arXiv's query syntax expects.
* ``papers``  — normalizing an ``arxiv.Result`` into the app's paper dict.
* ``search``  — the shared ``arxiv.Client`` and the public entry point,
  ``search_arxiv``, that ties the other two together.

Everything callers need is re-exported here, so ``from ..integrations import
arxiv_client`` and ``arxiv_client.search_arxiv(...)`` / ``arxiv_client.ID_RE``
work exactly as if this were still one file.
"""

from __future__ import annotations

from .clauses import ID_RE
from .search import search_arxiv

__all__ = ["ID_RE", "search_arxiv"]
