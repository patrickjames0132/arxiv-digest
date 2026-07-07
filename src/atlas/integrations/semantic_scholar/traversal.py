"""Hydrating known papers and walking the citation graph from a seed:
batch detail lookup, references, citations, and similarity recommendations.
"""

from __future__ import annotations

import urllib.parse

from ...config import config
from . import client, nodes

_BATCH_MAX = 500  # S2 caps /paper/batch at 500 ids per call.

# S2's /citations and /references endpoints take no `sort` param — they come
# back in whatever order S2's index has them, which in practice skews toward
# the most recently ingested (i.e. most recently published) neighbor, not the
# most cited one. For a heavily-cited seed, that means a small `limit` fills
# up entirely with this year's obscure citing papers before a single famous,
# decades-old citing paper is ever seen. So we over-fetch up to this many
# candidates in one call (S2 accepts it; still one request) and rank locally
# by citation count before trimming to the caller's `limit`.
_RANK_POOL = 1000


def get_papers(paper_ids: list[str], fields: str = nodes.DETAIL_FIELDS) -> dict[str, dict]:
    """Hydrate paper details for many ids via ``POST /paper/batch``.

    The batch endpoint is used deliberately: the single-paper GET 429s almost
    immediately unauthenticated, while batch is lenient and bulk-friendly.

    Args:
        paper_ids: S2 paperIds or prefixed ids like ``ARXIV:1706.03762``.
            Falsy entries are dropped. Chunked to respect the 500-id batch cap.
        fields: Comma-separated S2 field list to request.

    Returns:
        A map of the *requested* id to its normalized node dict. Ids S2 can't
        resolve are omitted.

    Raises:
        client.S2Error: When a batch request fails after retries.
    """
    paper_ids = [paper_id for paper_id in paper_ids if paper_id]
    if not paper_ids:
        return {}
    out: dict[str, dict] = {}
    url = f"{config.s2.graph_url}/paper/batch?fields={urllib.parse.quote(fields)}"
    for start in range(0, len(paper_ids), _BATCH_MAX):
        chunk = paper_ids[start : start + _BATCH_MAX]
        data = client.request(url, method="POST", body={"ids": chunk})
        # S2 returns a list aligned to the input ids, with null for unknowns
        # (anything else — request() types its JSON as object — means no rows).
        papers = data if isinstance(data, list) else []
        for requested_id, paper in zip(chunk, papers):
            node = nodes.node(paper)
            if node:
                out[requested_id] = node
    return out


def get_paper(paper_id: str) -> dict | None:
    """Fetch details for a single paper.

    Args:
        paper_id: An S2 paperId or a prefixed id like ``ARXIV:1706.03762``.

    Returns:
        The normalized node dict, or None when S2 has no such paper.

    Raises:
        client.S2Error: When the underlying batch request fails after retries.
    """
    return get_papers([paper_id]).get(paper_id)


def _neighbors(path: str, key: str, limit: int) -> list[dict]:
    """Shared traversal for the references/citations endpoints.

    Fetches a larger pool than ``limit`` (see ``_RANK_POOL``) and ranks it by
    citation count before trimming, since S2 doesn't offer server-side sorting
    here and its default order skews toward the most recently published
    neighbor rather than the most cited one.

    Args:
        path: The endpoint path under ``/paper/`` (quoted id + relation).
        key: The nested paper key in each result item — ``"citedPaper"`` for
            references, ``"citingPaper"`` for citations.
        limit: Maximum neighbors to return.

    Returns:
        A list of ``{"node": <node dict>, "influential": bool}`` entries,
        skipping papers S2 couldn't resolve, most-cited first.

    Raises:
        client.S2Error: When the request fails after retries.
    """
    fetch_limit = max(limit, _RANK_POOL)
    url = (
        f"{config.s2.graph_url}/paper/{path}"
        f"?fields={urllib.parse.quote(nodes.NEIGHBOR_FIELDS)}&limit={fetch_limit}"
    )
    data = client.request(url)
    # (citation_count, entry) pairs so the sort key doesn't need to dig back
    # into entry["node"] — its value type is erased to `object` once "node"
    # and "influential" (a dict and a bool) share one dict literal.
    hits: list[tuple[int, dict]] = []
    for item in (data.get("data") or []) if isinstance(data, dict) else []:
        node = nodes.node(item.get(key))
        if node:
            entry = {"node": node, "influential": bool(item.get("isInfluential"))}
            hits.append((node.get("citation_count") or 0, entry))
    hits.sort(key=lambda hit: hit[0], reverse=True)
    return [entry for _, entry in hits[:limit]]


def references(paper_id: str, limit: int) -> list[dict]:
    """Fetch the papers this one CITES (its intellectual ancestors).

    Args:
        paper_id: An S2 paperId or prefixed id.
        limit: Maximum references to return.

    Returns:
        A list of ``{"node": <node dict>, "influential": bool}`` entries.

    Raises:
        client.S2Error: When the request fails after retries.
    """
    return _neighbors(f"{client.quote(paper_id)}/references", "citedPaper", limit)


def citations(paper_id: str, limit: int) -> list[dict]:
    """Fetch the papers that CITE this one (its descendants).

    Args:
        paper_id: An S2 paperId or prefixed id.
        limit: Maximum citations to return.

    Returns:
        A list of ``{"node": <node dict>, "influential": bool}`` entries.

    Raises:
        client.S2Error: When the request fails after retries.
    """
    return _neighbors(f"{client.quote(paper_id)}/citations", "citingPaper", limit)


def recommendations(paper_id: str, limit: int, pool: str | None = None) -> list[dict]:
    """Fetch embedding-based related papers (similarity neighbors).

    Args:
        paper_id: An S2 paperId or prefixed id.
        limit: Maximum recommendations to return.
        pool: The candidate set — ``"all-cs"`` or ``"recent"``. Defaults to
            ``config.graph.recs_pool`` (``all-cs``; the ``recent`` pool
            returns nothing for older seeds).

    Returns:
        A list of ``{"node": <node dict>}`` entries (no influence flag — the
        recommendations endpoint doesn't report one).

    Raises:
        client.S2Error: When the request fails after retries.
    """
    pool = pool or config.graph.recs_pool
    url = (
        f"{config.s2.recs_url}/papers/forpaper/{client.quote(paper_id)}"
        f"?fields={urllib.parse.quote(nodes.NEIGHBOR_FIELDS)}&limit={limit}&from={pool}"
    )
    data = client.request(url)
    recommended_papers = data.get("recommendedPapers") if isinstance(data, dict) else None
    return nodes.from_papers(recommended_papers or [])
