"""papers.to_paper: normalizing an arxiv.Result into the app's paper dict.

arxiv.Result objects are built directly — the package's real class, no fakes
needed.
"""

from __future__ import annotations

from datetime import datetime, timezone

import arxiv

from arxiv_digest.integrations.arxiv_client import papers


def _result(**overrides) -> arxiv.Result:
    """A minimal valid arxiv.Result, with overrides for the fields under test."""
    fields = {
        "entry_id": "http://arxiv.org/abs/1706.03762v5",
        "title": "Attention  Is\nAll You Need",
        "authors": [arxiv.Result.Author("Ashish Vaswani"), arxiv.Result.Author("Noam Shazeer")],
        "categories": ["cs.CL", "cs.LG"],
        "summary": "The dominant sequence   transduction models...",
        "published": datetime(2017, 6, 12, tzinfo=timezone.utc),
    }
    fields.update(overrides)
    return arxiv.Result(**fields)


def test_short_id_strips_version_suffix():
    assert papers._short_id(_result(entry_id="http://arxiv.org/abs/2406.12345v2")) == (
        "2406.12345"
    )


def test_short_id_handles_old_style_ids():
    assert papers._short_id(_result(entry_id="http://arxiv.org/abs/hep-th/9901001v1")) == (
        "hep-th/9901001"
    )


def test_to_paper_normalizes_a_result():
    paper = papers.to_paper(_result())
    assert paper["arxiv_id"] == "1706.03762"
    assert paper["title"] == "Attention Is All You Need"  # whitespace collapsed
    assert paper["authors"] == "Ashish Vaswani, Noam Shazeer"
    assert paper["categories"] == "cs.CL cs.LG"
    assert paper["abstract"] == "The dominant sequence transduction models..."
    assert paper["url"] == "https://arxiv.org/abs/1706.03762"
    assert paper["published"] == "2017-06-12"
