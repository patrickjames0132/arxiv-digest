"""Semantic Scholar's fields of study — the coarse subject vocabulary S2 filters by.

Where ``categories.py`` holds arXiv's ~155 fine-grained codes (for arXiv papers),
this holds S2's own much coarser list of ~20 top-level fields (Computer Science,
Mathematics, …). It's what powers the S2 seed-search filter: S2's
``/paper/search`` accepts a ``fieldsOfStudy`` filter over exactly these values.

Fixed, S2-defined vocabulary, and small enough to inline (no bundled JSON like
the arXiv side). Each value is already human-readable — the field *is* its own
label — so there's no ``code → name`` mapping here. The casing is Title Case
with spaces, matching what S2 returns in a paper's ``fieldsOfStudy`` and accepts
in the search filter (per the S2 Academic Graph API docs).
"""

from __future__ import annotations

# S2's fieldsOfStudy values, alphabetical. If S2 ever changes the vocabulary or
# the casing turns out different live, this one tuple is the only thing to edit.
S2_FIELDS: tuple[str, ...] = (
    "Agricultural and Food Sciences",
    "Art",
    "Biology",
    "Business",
    "Chemistry",
    "Computer Science",
    "Economics",
    "Education",
    "Engineering",
    "Environmental Science",
    "Geography",
    "Geology",
    "History",
    "Law",
    "Linguistics",
    "Materials Science",
    "Mathematics",
    "Medicine",
    "Philosophy",
    "Physics",
    "Political Science",
    "Psychology",
    "Sociology",
)


def all_fields() -> list[str]:
    """List the S2 fields of study.

    Named ``all_fields`` (not ``fields``) so it doesn't shadow this ``fields``
    module when re-exported at the package root.

    Returns:
        The fields in a stable (alphabetical) order, for populating the search
        filter's picker.
    """
    return list(S2_FIELDS)


def valid_fields() -> frozenset[str]:
    """Collect the valid S2 fields of study.

    Returns:
        A frozenset of the field names, for validating a submitted filter (an
        unknown field can only come from a stale/forged client).
    """
    return frozenset(S2_FIELDS)
