"""Full paper text from ar5iv, for the agentic teacher to read into context.

Semantic Scholar gives abstracts + TL;DRs; when the Q&A agent needs specifics
(methods, results, numbers) it reads the full text. We reuse the ar5iv fetch that
``figures.py`` already relies on (arXiv's LaTeX→HTML render), strip the body to
readable text, and cache it in SQLite (same thin cache as graph snapshots).

Only papers with an arXiv id and an ar5iv render have full text; everything else
falls back to the abstract (handled by the caller). The extracted text is cached
whole; the caller truncates to a char budget at read time.
"""

from __future__ import annotations

import logging
from html.parser import HTMLParser

from . import cache, figures

log = logging.getLogger(__name__)

_FT_TTL = figures._FIG_TTL  # ar5iv renders are static; a month is plenty.
# Block-level tags whose text we keep (paragraphs, headings, list items).
_TEXT_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li"}
# Subtrees to drop entirely: math renders as noisy markup, and these aren't body.
_SKIP_TAGS = {"math", "script", "style", "figure", "nav", "cite"}


class _TextParser(HTMLParser):
    """Collect readable body text: the text of each block-level element, with
    math / scripts / figures / citations dropped. Blocks join with blank lines."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self._in_text = 0   # depth inside a kept block tag
        self._skip = 0      # depth inside a dropped subtree
        self._cur: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in _SKIP_TAGS:
            self._skip += 1
        elif tag in _TEXT_TAGS and not self._skip:
            self._in_text += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS and self._skip:
            self._skip -= 1
        elif tag in _TEXT_TAGS and self._in_text and not self._skip:
            self._in_text -= 1
            if self._in_text == 0:
                text = " ".join("".join(self._cur).split())
                if text:
                    self.blocks.append(text)
                self._cur = []

    def handle_data(self, data: str) -> None:
        if self._in_text and not self._skip:
            self._cur.append(data)


def get_fulltext(arxiv_id: str, *, refresh: bool = False) -> dict:
    """Return ``{"available": bool, "text": str}`` — the paper's body text from
    ar5iv, cached. ``available`` is false when ar5iv has no render for the paper."""
    arxiv_id = (arxiv_id or "").strip().split("v")[0]
    if not arxiv_id:
        return {"available": False, "text": ""}

    key = f"fulltext:{arxiv_id}"
    if not refresh:
        cached = cache.get(key, _FT_TTL)
        if cached is not None:
            return cached

    html = figures._fetch_html(arxiv_id)
    if html is None:
        result = {"available": False, "text": ""}
        cache.set(key, result)
        return result

    parser = _TextParser()
    parser.feed(html)
    result = {"available": True, "text": "\n\n".join(parser.blocks)}
    cache.set(key, result)
    return result
