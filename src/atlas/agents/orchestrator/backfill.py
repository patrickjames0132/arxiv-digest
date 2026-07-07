"""The lecture backfill walks: enrich the graph before a lecture so the
story can open at the field's roots (history) or reach the current frontier
(evolution). Two directions of one walk.

Deterministic — no LLM ever touches this. A modern seed's graph rarely
reaches either extreme, so the walk launches NOT from the seed (its own
references/citations are already on screen) but from the papers sitting
closest to the target end: the OLDEST visible papers for the backward walk,
the NEWEST for the forward one. Each hop pulls their neighbors along the
walk's relation (references backward, citations forward — day-cached via
``agents.traversal``), keeps the most-cited new papers, and carries the
frontier-most additions into the next hop.

* **Backward** (``history_backfill``) marches toward the past, stopping at
  the hop budget, an exhausted frontier, or once the story reaches
  ``lookback_years`` before the seed.
* **Forward** (``forward_backfill``) marches toward the present, stopping at
  the hop budget or an exhausted frontier — there's no year ceiling, since a
  paper can't be cited by the future.

All knobs live in ``config.graph.backfill``; the backward algorithm is walked
step by step in this package's README.

S2 errors on a hop are noted and skipped, never raised: a failed hop must
not abort the lecture.
"""

from __future__ import annotations

from typing import Iterator, Literal

from ...config import config
from ...integrations import semantic_scholar as s2
from ...services.graph import Edge, Node
from .. import events, traversal

# The two directions of the walk, each as (relation to hop along, edge-type
# tag stored on discoveries). Backward hops references (ancestors); forward
# hops citations (descendants). Edge DIRECTION is handled in ``_walk`` — a
# citation edge always points citing -> cited, but which endpoint is the
# frontier paper flips with the walk.
_RELATION: dict[str, traversal.Relation] = {"back": "references", "forward": "citations"}
_REL_TAG: dict[str, Literal["reference", "citation"]] = {
    "back": "reference",
    "forward": "citation",
}


def _seed_year(nodes: list[Node], seed_id: str) -> int | None:
    """The seed's publication year: its own when present, else the newest
    visible year (the seed is almost always the most recent paper), else
    None when no node carries a year at all."""
    for node in nodes:
        if node.id == seed_id and node.year is not None:
            return node.year
    years = [node.year for node in nodes if node.year is not None]
    return max(years) if years else None


def _walk(
    seed: Node, nodes: list[Node], *, direction: str
) -> Iterator[events.BackfillTrace | events.Discovery]:
    """Walk the graph one direction, yielding papers to enrich it with.

    Shared by ``history_backfill`` (``direction="back"``) and
    ``forward_backfill`` (``direction="forward"``). The two are mirror images:
    the backward walk launches from the oldest visible papers, hops
    references, and marches to the past under a year floor; the forward walk
    launches from the newest, hops citations, and marches to the present with
    no floor. Everything else — the dedup ledger, per-hop most-cited
    selection, dangling-edge filtering, honest empty trace — is identical.

    Args:
        seed: The seed paper (a blank id makes the walk a no-op).
        nodes: The visible graph nodes.
        direction: ``"back"`` (ancestors) or ``"forward"`` (descendants).

    Yields:
        Per productive hop, one ``BackfillTrace`` (hop number, papers found,
        the boundary year reached — ``oldest`` backward / ``newest`` forward)
        then one ``Discovery`` (the new nodes + the edges whose endpoints both
        landed on the graph). Discovered nodes carry ``idx=None`` — the walk
        runs *before* the lecturer numbers anything. When nothing was found at
        all, one final trace says so, with ``error=True`` if any hop failed.
    """
    knobs = config.graph.backfill
    if not seed.id:
        return
    backward = direction == "back"

    # --- The dedup ledger. ``known`` holds every paper id that is (or has
    # become) part of the graph — the visible nodes plus each hop's kept
    # additions. It serves two distinct jobs below: candidate filtering (a
    # paper already on the graph is never "discovered" again) and edge
    # filtering (an edge is only worth sending if BOTH its endpoints are on
    # the graph).
    known = {node.id for node in nodes}
    known.add(seed.id)

    # --- The stopping line (backward only). The march back through time ends
    # once a hop's additions reach ``lookback_years`` (~a career length)
    # before the seed — older work stops being interpretable context. The
    # forward walk has no ceiling: a paper can't be cited by the future, so
    # the frontier simply runs out. No seed year at all -> no floor.
    seed_year = _seed_year(nodes, seed.id) if backward else None
    year_floor = seed_year - knobs.lookback_years if seed_year else None

    # --- Frontier ordering. The walk launches from, and marches along, the
    # papers closest to the target end: the OLDEST for backward (nearest the
    # roots), the NEWEST for forward (nearest the frontier). Papers with no
    # year sort to the far end away from the target so they never lead.
    def frontier_key(year: int | None) -> int:
        if year is not None:
            return year
        return 9999 if backward else -1

    def frontier_first(papers: list, year_of) -> list:
        """Sort papers frontier-most first (oldest backward, newest forward)."""
        return sorted(papers, key=lambda paper: frontier_key(year_of(paper)), reverse=not backward)

    # --- Launch from the frontier-most visible papers, never the seed.
    # Expanding the seed can only re-find its own neighbors — already on the
    # graph by definition. (Seed-as-frontier is only the degenerate fallback
    # when the graph shows nothing but the seed.)
    launch = frontier_first(
        [node for node in nodes if node.id and not node.is_seed],
        lambda node: node.year,
    )
    frontier = [node.id for node in launch[: knobs.frontier]] or [seed.id]

    relation = _RELATION[direction]
    rel_tag = _REL_TAG[direction]
    total_added = 0
    errored = False

    for hop in range(knobs.hops):
        if not frontier:
            break

        # --- Fetch phase: pull every frontier paper's neighbors along the
        # walk's relation (one day-cached S2 call each — ``fetch_limit`` caps
        # the fan-out). ``candidates`` collects papers not yet on the graph,
        # first-seen wins; ``edges`` collects EVERY edge we saw, even to
        # papers that may not make the cut — the keep-or-drop decision can't
        # be made until ranking picks this hop's additions.
        candidates: dict[str, dict] = {}
        edges: list[Edge] = []
        for paper_id in frontier:
            try:
                hits = traversal.neighbors(paper_id, relation, knobs.fetch_limit)
            except s2.S2Error:
                # A failed hop is noted (for the final trace's error flag)
                # and skipped — the lecture happens with or without it.
                errored = True
                continue
            for hit in hits:
                neighbor = hit["node"]
                neighbor_id = neighbor.get("id")
                if not neighbor_id or neighbor_id == paper_id:
                    continue
                # Edge direction encodes citation semantics (same rule as
                # build_graph): the edge always points citing -> cited. On a
                # backward hop the frontier paper is the citer (it cites its
                # references); on a forward hop the neighbor is the citer (it
                # cites the frontier paper).
                citer, cited = (paper_id, neighbor_id) if backward else (neighbor_id, paper_id)
                edges.append(
                    Edge(
                        source=citer,
                        target=cited,
                        type=rel_tag,
                        influential=hit.get("influential", False),
                    )
                )
                if neighbor_id not in known and neighbor_id not in candidates:
                    candidates[neighbor_id] = neighbor
        if not candidates:
            break  # every neighbor we can reach is already on the graph

        # --- Selection phase: keep the most-cited candidates, capped at
        # ``per_hop``. Citation count is the proxy for "landmark" — the walk
        # surfaces the papers a lecture should dwell on (the seminal roots
        # backward, the influential follow-ups forward), not every stray
        # neighbor. The cap keeps each hop's graph growth digestible.
        ranked = sorted(
            candidates.values(),
            key=lambda candidate: candidate.get("citation_count") or 0,
            reverse=True,
        )
        # idx stays None: numbering is positional and happens later, when
        # the orchestrator hands the enriched node set to the lecturer.
        additions = [
            events.DiscoveredNode(**candidate, rels=[rel_tag], is_seed=False)
            for candidate in ranked[: knobs.per_hop]
        ]
        known.update(addition.id for addition in additions)

        # --- Edge filter: only edges whose endpoints BOTH landed on the
        # graph. A candidate that lost the ranking never became a node, so
        # its edges would dangle — the frontend would either drop them or,
        # worse, invent phantom nodes for them.
        kept_edges = [
            edge for edge in edges if edge.source in known and edge.target in known
        ]

        years = [addition.year for addition in additions if addition.year is not None]
        # The boundary year this hop reached — oldest backward, newest forward.
        boundary = (min(years) if backward else max(years)) if years else None
        total_added += len(additions)
        # Trace first (e.g. backward "hop 2: found 4, oldest 1986"; forward
        # "hop 2: found 4, newest 2025"), then the payload the frontend
        # merges — same order the user watches it happen.
        if backward:
            yield events.BackfillTrace(hop=hop + 1, found=len(additions), oldest=boundary)
        else:
            yield events.BackfillTrace(
                hop=hop + 1, found=len(additions), newest=boundary, direction="forward"
            )
        yield events.Discovery(nodes=additions, edges=kept_edges)

        # --- March phase: the frontier-most additions become the next
        # frontier — each hop launches from the furthest-along papers found so
        # far, so the walk moves monotonically toward its target end instead
        # of wandering sideways through contemporaries. All additions are
        # on-graph now, so the next hop's edges will connect to visible papers.
        frontier = [
            addition.id
            for addition in frontier_first(additions, lambda addition: addition.year)[: knobs.frontier]
        ]
        if year_floor and boundary is not None and boundary <= year_floor:
            break  # reached the field's prehistory — the story has its roots

    # --- Honest empty result. Zero additions across all hops gets ONE
    # explicit trace instead of silence, and ``errored`` distinguishes "the
    # graph already reaches the end" (found nothing, fine) from "S2 was down
    # and we couldn't look" (found nothing, suspect).
    if total_added == 0:
        if backward:
            yield events.BackfillTrace(hop=1, found=0, oldest=None, error=errored)
        else:
            yield events.BackfillTrace(
                hop=1, found=0, newest=None, direction="forward", error=errored
            )


def history_backfill(
    seed: Node, nodes: list[Node]
) -> Iterator[events.BackfillTrace | events.Discovery]:
    """Walk backward through references, yielding ancestors for the graph.

    The "How we got here" enrichment — see ``_walk`` for the algorithm.

    Args:
        seed: The seed paper (a blank id makes the walk a no-op).
        nodes: The visible graph nodes.

    Yields:
        ``BackfillTrace`` + ``Discovery`` per productive hop; one final empty
        trace when nothing older was found.
    """
    return _walk(seed, nodes, direction="back")


def forward_backfill(
    seed: Node, nodes: list[Node]
) -> Iterator[events.BackfillTrace | events.Discovery]:
    """Walk forward through citations, yielding descendants for the graph.

    The "What's evolved since" enrichment: from the newest visible papers,
    hop forward through citations toward the current frontier — the work that
    built on the seed. See ``_walk`` for the algorithm.

    Args:
        seed: The seed paper (a blank id makes the walk a no-op).
        nodes: The visible graph nodes.

    Yields:
        ``BackfillTrace`` + ``Discovery`` per productive hop; one final empty
        trace when nothing newer was found.
    """
    return _walk(seed, nodes, direction="forward")
