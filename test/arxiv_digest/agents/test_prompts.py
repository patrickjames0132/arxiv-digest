"""Model-input parts: skill loading, passage rendering, and history
conversion. (Joining the parts into one prompt is PydanticAI's job — agents
pass ``instructions=[SYSTEM_PROMPT, *skills]`` and it joins with blank
lines.)"""

from __future__ import annotations

import pytest
from pydantic_ai.messages import ModelRequest, ModelResponse

from arxiv_digest.agents import prompts


def test_skill_loads_prompt_ready_markdown():
    assert prompts.skill("teaching-voice").startswith("# Teaching voice")


def test_unknown_skill_fails_loudly():
    with pytest.raises(FileNotFoundError):
        prompts.skill("no-such-skill")


def test_format_passages_tags_source_and_page():
    hits = [
        {"source_title": "Deep Learning", "page": 243, "text": "Momentum   helps\nconverge."},
        {"source_title": "A Web Page", "page": None, "text": "Regularization notes."},
    ]
    rendered = prompts.format_passages(hits)
    assert "[Deep Learning, p.243] Momentum helps converge." in rendered
    assert "[A Web Page] Regularization notes." in rendered


def test_history_converts_turns_and_skips_malformed():
    turns = [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
        {"role": "system", "content": "not a chat role"},
        {"role": "user", "content": 42},
        {"content": "no role"},
    ]
    messages = prompts.history(turns)
    assert [type(message) for message in messages] == [ModelRequest, ModelResponse]
    assert prompts.history(None) == []
