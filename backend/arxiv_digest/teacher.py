"""AI teacher: streaming lecture + grounded Q&A over the on-screen graph.

Phase 3a — narration is grounded **only** in the papers currently visible on the
user's graph (the seed plus its references / citations / similar work). There is
no agentic traversal or full-text reading yet; the teacher cannot jump to papers
that aren't on screen. That agentic layer — a tool-use loop with a hop budget and
a visited-set to kill reference cycles — is Phase 3b.

Two Claude backends (set via TEACHER_BACKEND): the Anthropic API (``anthropic``
SDK) or the ``claude`` CLI under a Pro/Max subscription (no API billing). Both are
consumed here as a **stream** of text so the frontend can reveal the lecture
beat-by-beat and light up graph nodes in sync with the story.

Two products:
  * ``lecture_beats(...)`` — an ordered sequence of *beats*. Each beat is a short
    paragraph bound to a set of graph nodes to highlight. The model emits
    newline-delimited JSON, so we can parse and stream one beat at a time.
  * ``answer_stream(...)`` — a conversational reply to a question, grounded in the
    visible graph, streamed token-by-token, ending with the nodes it cited.

To keep node references robust, the model never handles the long Semantic Scholar
paperIds: we present the visible papers as a numbered list and the model refers
to them by index, which we map back to ids on the way out.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
import time
from typing import Iterator, Optional

from . import config, fulltext
from . import semantic_scholar as s2

log = logging.getLogger(__name__)

# Sentinel the Q&A model prints after its prose, followed by the JSON list of
# node indices it drew from. Kept out of the visible answer.
_CITED = "<<CITED>>"


# --- Streaming backends ------------------------------------------------------
def _stream_api(system: str, messages: list[dict], max_tokens: int) -> Iterator[str]:
    """Stream text deltas from the Anthropic API."""
    import anthropic

    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError(
            "TEACHER_BACKEND=api but ANTHROPIC_API_KEY is not set. Add it to .env "
            "or set TEACHER_BACKEND=claude_cli to use your Pro/Max subscription."
        )
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    with client.messages.stream(
        model=config.TEACHER_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            yield text


def _flatten(messages: list[dict]) -> str:
    """Collapse a message list into one prompt string for the headless CLI.

    A lecture is a single user turn; a Q&A carries prior turns, which we label so
    the model still sees the conversation."""
    if len(messages) == 1:
        return messages[0]["content"]
    parts = []
    for m in messages:
        who = "User" if m["role"] == "user" else "Assistant"
        parts.append(f"{who}: {m['content']}")
    parts.append("Assistant:")
    return "\n\n".join(parts)


def _stream_cli(system: str, messages: list[dict], max_tokens: int) -> Iterator[str]:
    """Stream text deltas from the ``claude`` CLI (subscription, no API billing).

    Parses the CLI's ``stream-json`` events (``content_block_delta`` with a
    ``text_delta``); skips thinking deltas. Runs in a throwaway temp cwd so the
    CLI doesn't load this repo's CLAUDE.md / project context (which would bloat
    every call by thousands of cached tokens and muddy the output)."""
    cmd = [
        config.CLAUDE_CLI_PATH,
        "-p",
        _flatten(messages),
        "--system-prompt",
        system,
        "--output-format",
        "stream-json",
        "--include-partial-messages",
        "--verbose",
    ]
    if config.TEACHER_CLI_MODEL:
        cmd += ["--model", config.TEACHER_CLI_MODEL]

    # Use the subscription login, not API billing (mirrors summarizer.py).
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("ANTHROPIC_AUTH_TOKEN", None)

    with tempfile.TemporaryDirectory() as tmp:
        stderr_f = tempfile.TemporaryFile(mode="w+")
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=stderr_f,
            text=True,
            env=env,
            cwd=tmp,
        )
        saw_text = False
        result_fallback: Optional[str] = None
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    evt = json.loads(line)
                except json.JSONDecodeError:
                    continue
                etype = evt.get("type")
                if etype == "stream_event":
                    e = evt.get("event", {})
                    if e.get("type") == "content_block_delta":
                        d = e.get("delta", {})
                        if d.get("type") == "text_delta" and d.get("text"):
                            saw_text = True
                            yield d["text"]
                elif etype == "result":
                    # Emitted once at the end; keep as a fallback if no deltas
                    # streamed (e.g. partial messages disabled by a CLI update).
                    if isinstance(evt.get("result"), str):
                        result_fallback = evt["result"]
            proc.wait(timeout=config.TEACHER_CLI_TIMEOUT)
        finally:
            if proc.poll() is None:
                proc.kill()
        if proc.returncode not in (0, None):
            stderr_f.seek(0)
            err = stderr_f.read().strip()
            raise RuntimeError(
                f"claude CLI failed (exit {proc.returncode}): {err[:300]}"
            )
        if not saw_text and result_fallback:
            yield result_fallback


def _stream(system: str, messages: list[dict], max_tokens: int) -> Iterator[str]:
    """Stream a completion, trying the primary backend then the fallback.

    Fallback only helps for failures **before the first token** (missing key, CLI
    not on PATH, spawn error) — the common case. Once streaming has begun we can't
    cleanly switch, so a mid-stream failure surfaces.
    """
    primary = config.TEACHER_BACKEND
    fallback = config.TEACHER_FALLBACK_BACKEND or None
    backends = [primary]
    if fallback and fallback != primary:
        backends.append(fallback)

    last_err: Optional[Exception] = None
    for backend in backends:
        fn = _stream_api if backend == "api" else _stream_cli
        try:
            gen = fn(system, messages, max_tokens)
            first = next(gen)  # trips init/spawn errors before we commit
        except StopIteration:
            return  # backend produced nothing, but didn't error
        except Exception as exc:  # noqa: BLE001 — try the fallback
            last_err = exc
            log.warning("teacher backend %r failed to start: %s", backend, exc)
            continue
        yield first
        yield from gen
        return
    raise RuntimeError(f"all teacher backends failed ({last_err})")


# --- Shared node formatting --------------------------------------------------
def _number_nodes(nodes: list[dict]) -> list[dict]:
    """Attach a 1-based ``idx`` to each visible node (input order preserved)."""
    return [{**n, "idx": i + 1} for i, n in enumerate(nodes)]


def _node_lines(numbered: list[dict]) -> str:
    """Render the numbered papers for the prompt. One line per paper: index,
    year, title, citation count, and a summary snippet when we have one."""
    lines = []
    for n in numbered:
        year = n.get("year") or "n.d."
        cites = n.get("citation_count")
        cite_str = f", {cites} citations" if isinstance(cites, int) else ""
        summary = n.get("tldr") or n.get("abstract") or ""
        if summary:
            summary = " — " + summary.strip().replace("\n", " ")[:240]
        rels = ",".join(n.get("rels", [])) or "?"
        lines.append(f"[{n['idx']}] ({year}{cite_str}; {rels}) {n.get('title', '')}{summary}")
    return "\n".join(lines)


def _idx_to_id(numbered: list[dict], indices: object) -> list[str]:
    """Map model-emitted 1-based indices back to Semantic Scholar node ids,
    ignoring anything out of range or non-integer."""
    out: list[str] = []
    if not isinstance(indices, list):
        return out
    by_idx = {n["idx"]: n["id"] for n in numbered if n.get("id")}
    for i in indices:
        if isinstance(i, bool):
            continue
        if isinstance(i, int) and i in by_idx:
            out.append(by_idx[i])
    return out


# --- Lecture -----------------------------------------------------------------
_LECTURE_SYSTEM = (
    "You are an expert teacher narrating the intellectual history and intuition of "
    "a research area to a curious graduate student. You are given a SEED paper and "
    "the papers currently visible on an interactive citation graph (its references, "
    "citations, and similar work), presented as a numbered list. Produce a short, "
    "vivid lecture as an ordered sequence of BEATS. Each beat is one tight paragraph "
    "(2–4 sentences) that advances the story and points at specific papers so they "
    "can light up on the graph as you speak.\n\n"
    "OUTPUT FORMAT: emit ONE JSON object per line (newline-delimited JSON) and "
    "NOTHING else — no prose, no markdown, no code fences, no wrapping array. Each "
    'object is exactly: {"heading": "<3–6 word signpost>", "text": "<the narration '
    'paragraph>", "nodes": [<indices from the numbered list this beat is about>]}\n\n'
    "RULES:\n"
    "- 5–9 beats total.\n"
    "- 'nodes' must be integer indices from the numbered list; reference 1–4 papers "
    "per beat. Use [] only for a pure framing/closing beat.\n"
    "- Explain intuition and significance in plain English; avoid hype and jargon; "
    "do not merely list titles.\n"
    "- Ground claims in the titles, years, and summaries provided. Don't invent "
    "specifics the data doesn't support."
)

_MODE_INTENT = {
    "history": (
        "Mode: HOW WE GOT HERE. Tell the story chronologically — from the oldest "
        "roots among the references, through the key ideas that made each next step "
        "possible, to the SEED paper and the work it went on to spawn (its citations)."
    ),
    "intuition": (
        "Mode: INTUITION OF THIS PAPER. Center the SEED paper: what problem it "
        "solved, the core idea, and why it works — using the surrounding papers only "
        "for context and contrast."
    ),
    "bridge": (
        "Mode: BRIDGE. Build a conceptual bridge between the SEED paper and the "
        "TARGET paper, tracing the ideas that connect two areas that may look "
        "unrelated at first."
    ),
}


def _lecture_prompt(
    seed: dict, numbered: list[dict], mode: str, target: Optional[dict]
) -> str:
    intent = _MODE_INTENT.get(mode, _MODE_INTENT["history"])
    seed_title = seed.get("title", "(the seed paper)")
    header = f"SEED paper: {seed_title}"
    if mode == "bridge" and target:
        header += f"\nTARGET paper: {target.get('title', '')}"
    return (
        f"{intent}\n\n"
        f"{header}\n\n"
        f"Papers on the graph (numbered):\n{_node_lines(numbered)}\n\n"
        f"Now deliver the lecture as newline-delimited JSON beats."
    )


def _parse_beat(line: str, numbered: list[dict]) -> Optional[dict]:
    """Parse one JSONL line into a beat dict, or None if it isn't a valid beat.

    Tolerates stray code fences / blank lines the model might emit around the
    JSONL despite instructions."""
    line = line.strip().strip("`").strip()
    if not line or not line.startswith("{"):
        return None
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return None
    text = obj.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    return {
        "heading": (obj.get("heading") or "").strip(),
        "text": text.strip(),
        "node_ids": _idx_to_id(numbered, obj.get("nodes")),
    }


def lecture_beats(
    seed: dict, nodes: list[dict], mode: str = "history", target: Optional[dict] = None
) -> Iterator[dict]:
    """Yield lecture beats ``{heading, text, node_ids}`` one at a time as the model
    streams newline-delimited JSON."""
    numbered = _number_nodes(nodes)
    prompt = _lecture_prompt(seed, numbered, mode, target)
    messages = [{"role": "user", "content": prompt}]

    buf = ""
    for chunk in _stream(_LECTURE_SYSTEM, messages, config.TEACHER_MAX_TOKENS):
        buf += chunk
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            beat = _parse_beat(line, numbered)
            if beat:
                yield beat
    beat = _parse_beat(buf, numbered)
    if beat:
        yield beat


# --- Q&A ---------------------------------------------------------------------
_QA_SYSTEM = (
    "You are a sharp, friendly research teacher answering a student's question, "
    "grounded ONLY in the papers currently visible on their citation graph (the "
    "numbered list below). Answer conversationally and concretely, in a few short "
    "paragraphs at most. If the answer isn't supported by the visible papers, say "
    "so briefly and suggest where on the graph to look — do NOT invent facts or "
    "cite papers that aren't listed.\n\n"
    "After your answer, on a new final line, emit exactly " + _CITED + " followed "
    "by a JSON array of the indices of the papers you drew from, e.g. "
    + _CITED + " [1, 4]. Use " + _CITED + " [] if you cited none. Output nothing "
    "after that line."
)


def _qa_context(seed: dict, numbered: list[dict]) -> str:
    return (
        f"SEED paper: {seed.get('title', '')}\n\n"
        f"Papers on the graph (numbered):\n{_node_lines(numbered)}"
    )


def answer_stream(
    question: str,
    seed: dict,
    nodes: list[dict],
    history: Optional[list[dict]] = None,
) -> Iterator[tuple[str, object]]:
    """Answer a question grounded in the visible graph.

    Yields ``("token", text)`` events as the prose streams, then a final
    ``("cited", node_ids)`` event. The ``<<CITED>>`` sentinel and everything after
    it is stripped from the visible answer and parsed into node ids.
    """
    numbered = _number_nodes(nodes)
    messages: list[dict] = []
    for turn in history or []:
        role = turn.get("role")
        content = turn.get("content")
        if role in ("user", "assistant") and isinstance(content, str):
            messages.append({"role": role, "content": content})
    # The graph context rides on the current question so it always reflects the
    # latest on-screen neighborhood, even as the user pans/expands between turns.
    messages.append(
        {"role": "user", "content": f"{_qa_context(seed, numbered)}\n\nQuestion: {question}"}
    )

    buf = ""
    full = ""
    cut = False  # once we hit the sentinel, stop emitting prose
    # Hold back a tail so a sentinel split across chunks never leaks to the user.
    hold = len(_CITED)
    for chunk in _stream(_QA_SYSTEM, messages, config.TEACHER_MAX_TOKENS):
        full += chunk
        if cut:
            continue
        buf += chunk
        if _CITED in buf:
            visible, _ = buf.split(_CITED, 1)
            if visible:
                yield ("token", visible)
            cut = True
            buf = ""
            continue
        # Emit everything except a trailing window that might start the sentinel.
        if len(buf) > hold:
            emit, buf = buf[:-hold], buf[-hold:]
            if emit:
                yield ("token", emit)
    if not cut and buf:
        yield ("token", buf)

    yield ("cited", _parse_citations(full, numbered))


def _parse_citations(full: str, numbered: list[dict]) -> list[str]:
    """Pull the ``<<CITED>> [..]`` index list out of the full answer text."""
    if _CITED not in full:
        return []
    tail = full.split(_CITED, 1)[1].strip()
    start = tail.find("[")
    end = tail.find("]", start)
    if start == -1 or end == -1:
        return []
    try:
        indices = json.loads(tail[start : end + 1])
    except json.JSONDecodeError:
        return []
    return _idx_to_id(numbered, indices)


# --- Agentic Q&A (Phase 3b) --------------------------------------------------
# The agent answers by READING the visible papers (tool use) instead of reasoning
# over titles alone. Guardrails (config.AGENT_*): a total-step cap, per-kind read
# budgets, and a wall-clock ceiling. Requires the Anthropic API — the claude CLI
# can't take our custom tools, so the CLI backend falls back to answer_stream.
_AGENT_SYSTEM = (
    "You are a sharp, friendly research teacher answering a student's question "
    "about the papers on their citation graph (numbered below). You have a tool to "
    "READ those papers, so answer from their actual content rather than guessing.\n\n"
    "Use read_paper to pull in what you need: detail='summary' for a quick "
    "abstract + TL;DR, detail='full' for the full text when the question needs "
    "specifics (methods, results, numbers). Read only what you need — you have a "
    "limited budget. Do NOT narrate that you're about to use a tool; just call it. "
    "When you have enough, write the answer in at most a few short paragraphs, "
    "grounded in what you read. Begin with the answer itself — do NOT preface it "
    "with remarks about your reading process (no \"I found the sections\"). If the "
    "visible papers don't support an answer, say so briefly. Never invent facts or "
    "cite papers that aren't listed."
)

_TOOLS = [
    {
        "name": "read_paper",
        "description": (
            "Read one of the numbered papers on the graph to ground your answer. "
            "detail='summary' returns its abstract + TL;DR (cheap); detail='full' "
            "returns the full text via ar5iv (use sparingly — limited budget)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "index": {
                    "type": "integer",
                    "description": "The [n] index of the paper from the numbered list.",
                },
                "detail": {
                    "type": "string",
                    "enum": ["summary", "full"],
                    "description": "summary = abstract + TL;DR; full = full text.",
                },
            },
            "required": ["index", "detail"],
        },
    }
]


def agentic_available() -> bool:
    """True when we can run the tool-use agent (Anthropic API + key)."""
    return config.TEACHER_BACKEND == "api" and bool(config.ANTHROPIC_API_KEY)


def _node_by_idx(numbered: list[dict], idx: object) -> Optional[dict]:
    if not isinstance(idx, int) or isinstance(idx, bool):
        return None
    for n in numbered:
        if n.get("idx") == idx:
            return n
    return None


def _paper_text(node: dict, detail: str) -> str:
    """Assemble the text handed back to the agent for one paper read."""
    title = node.get("title") or "(untitled)"
    year = node.get("year")
    arxiv_id = node.get("arxiv_id")
    abstract = node.get("abstract")
    tldr = node.get("tldr")
    # Neighbor nodes arrive without abstract/tldr — hydrate on demand.
    if abstract is None and tldr is None:
        lookup = f"ARXIV:{arxiv_id}" if arxiv_id else node.get("id")
        hydrated = s2.get_paper(lookup) if lookup else None
        if hydrated:
            abstract = hydrated.get("abstract")
            tldr = hydrated.get("tldr")

    header = f"Title: {title}" + (f" ({year})" if year else "")
    if detail == "full" and arxiv_id:
        ft = fulltext.get_fulltext(arxiv_id)
        if ft.get("available") and ft.get("text"):
            body = ft["text"][: config.FULLTEXT_MAX_CHARS]
            tail = "\n\n[...truncated]" if len(ft["text"]) > config.FULLTEXT_MAX_CHARS else ""
            return f"{header}\nTL;DR: {tldr or '—'}\n\nFull text:\n{body}{tail}"

    parts = [header]
    if tldr:
        parts.append(f"TL;DR: {tldr}")
    parts.append(f"Abstract: {abstract}" if abstract else "Abstract: (unavailable)")
    if detail == "full" and not arxiv_id:
        parts.append("(No arXiv full text for this paper — summary only.)")
    return "\n".join(parts)


def _run_read(block, numbered: list[dict], budgets: dict, read_cache: dict) -> tuple[str, dict, Optional[str]]:
    """Execute a read_paper tool call. Returns (tool_result_text, trace, node_id)."""
    inp = getattr(block, "input", None) or {}
    idx = inp.get("index")
    detail = "full" if inp.get("detail") == "full" else "summary"
    node = _node_by_idx(numbered, idx)
    if node is None:
        return (f"No paper at index {idx}.", {"action": "read", "ok": False, "index": idx, "title": None, "detail": detail}, None)

    title = node.get("title")
    # Downgrade a full read to summary when the full budget is spent.
    if detail == "full" and budgets["full"] <= 0:
        detail = "summary"
    if budgets[detail] <= 0:
        return (
            "Read budget exhausted — answer now with what you've already gathered.",
            {"action": "read", "ok": False, "index": idx, "title": title, "detail": detail},
            node.get("id"),
        )

    ck = (node.get("id"), detail)
    if ck in read_cache:
        text = read_cache[ck]
    else:
        text = _paper_text(node, detail)
        read_cache[ck] = text
        budgets[detail] -= 1
    return (text, {"action": "read", "ok": True, "index": idx, "title": title, "detail": detail}, node.get("id"))


def answer_agentic(
    question: str,
    seed: dict,
    nodes: list[dict],
    history: Optional[list[dict]] = None,
) -> Iterator[tuple[str, object]]:
    """Agentic Q&A: Claude reads the visible papers via tool use, then answers.

    Yields ``("trace", {...})`` as it reads papers, ``("token", str)`` for the
    streamed answer, ``("discard", None)`` if streamed preamble must be dropped
    (the turn turned out to be a tool call), and a final ``("cited", node_ids)``
    (the papers it actually read)."""
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    numbered = _number_nodes(nodes)

    messages: list[dict] = []
    for turn in history or []:
        if turn.get("role") in ("user", "assistant") and isinstance(turn.get("content"), str):
            messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append(
        {"role": "user", "content": f"{_qa_context(seed, numbered)}\n\nQuestion: {question}"}
    )

    budgets = {"full": config.AGENT_MAX_FULL_READS, "summary": config.AGENT_MAX_SUMMARY_READS}
    read_cache: dict = {}
    cited: list[str] = []
    start = time.time()

    for _ in range(config.AGENT_MAX_STEPS):
        use_tools = (time.time() - start) < config.AGENT_WALLCLOCK
        turn_text = ""
        tool_turn = False
        with client.messages.stream(
            model=config.AGENT_MODEL,
            max_tokens=config.TEACHER_MAX_TOKENS,
            system=_AGENT_SYSTEM,
            messages=messages,
            tools=_TOOLS if use_tools else [],
        ) as stream:
            for event in stream:
                et = getattr(event, "type", "")
                if et == "content_block_start" and getattr(event.content_block, "type", "") == "tool_use":
                    if not tool_turn:
                        tool_turn = True
                        if turn_text.strip():
                            yield ("discard", None)  # streamed preamble wasn't the answer
                elif et == "content_block_delta" and getattr(event.delta, "type", "") == "text_delta":
                    turn_text += event.delta.text
                    if not tool_turn:
                        yield ("token", event.delta.text)
            final = stream.get_final_message()

        if final.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": final.content})
            results = []
            for b in final.content:
                if getattr(b, "type", "") == "tool_use" and b.name == "read_paper":
                    content, trace, read_id = _run_read(b, numbered, budgets, read_cache)
                    yield ("trace", trace)
                    if read_id and read_id not in cited:
                        cited.append(read_id)
                    results.append({"type": "tool_result", "tool_use_id": b.id, "content": content})
            messages.append({"role": "user", "content": results})
            continue
        # end_turn: the answer already streamed as tokens.
        yield ("cited", cited)
        return

    # Step budget spent mid-investigation — force a tool-free answer.
    messages.append({"role": "user", "content": "Answer now with what you've gathered."})
    with client.messages.stream(
        model=config.AGENT_MODEL,
        max_tokens=config.TEACHER_MAX_TOKENS,
        system=_AGENT_SYSTEM,
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            yield ("token", text)
    yield ("cited", cited)
