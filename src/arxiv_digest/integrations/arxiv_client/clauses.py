"""Building the pieces of an arXiv query: id detection, date range, and
category filter clauses.

Named ``clauses`` rather than ``query`` deliberately — ``search_arxiv``'s own
parameter is named ``query`` (the search string), and a module of that name
would shadow it right where both are needed.
"""

from __future__ import annotations

import re

# A bare arXiv id (new-style "2406.12345" / "2406.12345v2", or old-style
# "hep-th/9901001"), optionally wrapped in an arxiv.org URL. Lets a search box
# accept a pasted id or link and fetch that exact paper instead of a keyword
# hunt. Also used by services/graph.py and routes/graph.py to detect an id
# pasted directly into a re-seed action, outside of search entirely.
ID_RE = re.compile(
    r"(?:https?://)?(?:arxiv\.org/(?:abs|pdf)/)?"
    r"(\d{4}\.\d{4,5}(?:v\d+)?|[a-z-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?)",
    re.IGNORECASE,
)


def date_clause(year_from: int | None, year_to: int | None) -> str | None:
    """Build arXiv's ``submittedDate`` range clause for a year window.

    arXiv's query syntax wants both bounds (``[from TO to]``), so an open
    end is filled with arXiv's launch year (1991) or a far-future ceiling.

    Args:
        year_from: Earliest submission year (inclusive), or None.
        year_to: Latest submission year (inclusive), or None.

    Returns:
        ``submittedDate:[YYYY01010000 TO YYYY12312359]`` — or None when both
        bounds are absent.
    """
    if not year_from and not year_to:
        return None
    date_from = f"{year_from or 1991}01010000"
    date_to = f"{year_to or 2099}12312359"
    return f"submittedDate:[{date_from} TO {date_to}]"


def category_clause(categories: list[str] | None) -> str | None:
    """Build arXiv's category filter clause.

    Args:
        categories: Category codes (e.g. ``["cs.LG", "cs.CV"]``) — already
            validated by the caller; falsy entries are dropped.

    Returns:
        ``(cat:cs.LG OR cat:cs.CV)`` — a paper matches when it carries ANY of
        the selected categories — or None when the list is empty.
    """
    valid_categories = [category for category in (categories or []) if category]
    if not valid_categories:
        return None
    return "(" + " OR ".join(f"cat:{category}" for category in valid_categories) + ")"
