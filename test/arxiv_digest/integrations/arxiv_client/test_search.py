"""search_arxiv: id-vs-keyword branching, query construction, and the
shared client.

The module-private _client is swapped for a stub that records every Search
it's given — no network.
"""

from __future__ import annotations

from datetime import datetime, timezone

import arxiv
import pytest

from arxiv_digest.integrations.arxiv_client import search


class _StubClient:
    """Stand-in for arxiv.Client: records every Search it's given, returns
    canned results."""

    def __init__(self, results: list[arxiv.Result]):
        self.results_to_return = results
        self.searches: list[arxiv.Search] = []

    def results(self, search: arxiv.Search):
        self.searches.append(search)
        return iter(self.results_to_return)


class _NeverCalledClient:
    """A client stub that fails the test if it's ever actually queried."""

    def results(self, search: arxiv.Search):
        pytest.fail("should not be called")


def _result(**overrides) -> arxiv.Result:
    """A minimal valid arxiv.Result, with overrides for the fields under test."""
    fields = {
        "entry_id": "http://arxiv.org/abs/1706.03762v5",
        "title": "Attention Is All You Need",
        "authors": [arxiv.Result.Author("Ashish Vaswani")],
        "categories": ["cs.CL"],
        "summary": "The dominant sequence transduction models...",
        "published": datetime(2017, 6, 12, tzinfo=timezone.utc),
    }
    fields.update(overrides)
    return arxiv.Result(**fields)


def test_search_arxiv_blank_query_short_circuits(monkeypatch):
    monkeypatch.setattr(search, "_client", _NeverCalledClient())
    assert search.search_arxiv("   ") == []


def test_search_arxiv_with_an_id_does_an_id_lookup(monkeypatch):
    stub = _StubClient([_result()])
    monkeypatch.setattr(search, "_client", stub)

    papers = search.search_arxiv("1706.03762")

    assert stub.searches[0].id_list == ["1706.03762"]
    assert papers[0]["arxiv_id"] == "1706.03762"


def test_search_arxiv_with_a_url_strips_and_matches(monkeypatch):
    stub = _StubClient([_result()])
    monkeypatch.setattr(search, "_client", stub)

    search.search_arxiv("https://arxiv.org/abs/1706.03762/")

    assert stub.searches[0].id_list == ["1706.03762"]


def test_search_arxiv_keyword_query_boosts_title_and_ands_filters(monkeypatch):
    stub = _StubClient([_result()])
    monkeypatch.setattr(search, "_client", stub)

    search.search_arxiv("attention", year_from=2017, categories=["cs.LG"], max_results=10)

    query = stub.searches[0].query
    assert '(ti:"attention" OR abs:(attention))' in query
    assert "(cat:cs.LG)" in query
    assert "submittedDate:[201701010000 TO 209912312359]" in query
    assert stub.searches[0].max_results == 10


def test_search_arxiv_strips_quotes_and_parens_from_query(monkeypatch):
    """A user's raw quotes/parens must not break the query syntax we build."""
    stub = _StubClient([_result()])
    monkeypatch.setattr(search, "_client", stub)

    search.search_arxiv('some "quoted" (text)')

    query = stub.searches[0].query
    # Exactly the two quotes we add ourselves around ti:"..." — none from the
    # user's input survived.
    assert query.count('"') == 2
    assert "quoted" in query and "text" in query
