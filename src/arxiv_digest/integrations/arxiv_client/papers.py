"""Normalizing an ``arxiv.Result`` into the app's paper dict."""

from __future__ import annotations

import arxiv


def _short_id(result: arxiv.Result) -> str:
    """Extract a stable arXiv id from a result.

    Args:
        result: An ``arxiv.Result`` from the client.

    Returns:
        The bare id with any version suffix stripped (e.g. ``"2406.12345"``,
        never ``"2406.12345v2"``), so the same paper always keys identically.
    """
    return result.get_short_id().split("v")[0]


def to_paper(result: arxiv.Result) -> dict:
    """Map an ``arxiv.Result`` to the app's paper dict.

    Args:
        result: An ``arxiv.Result`` from the client.

    Returns:
        A dict with keys ``arxiv_id, title, authors, categories, abstract,
        url, published`` — whitespace collapsed, version stripped from the
        id. ``published`` is the paper's own submission day (GMT) as an ISO
        ``YYYY-MM-DD`` string.
    """
    arxiv_id = _short_id(result)
    return {
        "arxiv_id": arxiv_id,
        "title": " ".join(result.title.split()),
        "authors": ", ".join(author.name for author in result.authors),
        "categories": " ".join(result.categories),
        "abstract": " ".join(result.summary.split()),
        "url": f"https://arxiv.org/abs/{arxiv_id}",
        # The paper's own submission day (GMT), shown in the search results
        # and filterable via year_from/year_to.
        "published": result.published.date().isoformat(),
    }
