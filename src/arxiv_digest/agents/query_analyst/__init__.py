"""Seed-search query expansion: acronyms and jargon spelled out so S2's
lexical search can find the papers that never use them.

* ``main``   — the ``Agent``, its ``Expansion`` output model, and
  ``expand_query`` (the passthrough-on-failure entry point).
* ``config`` — the agent id, system prompt, and (empty) skill list.

``expand_query`` is re-exported here — callers use
``query_analyst.expand_query(...)`` without reaching into submodules.
"""

from __future__ import annotations

from .main import Expansion, agent, expand_query

__all__ = ["Expansion", "agent", "expand_query"]
