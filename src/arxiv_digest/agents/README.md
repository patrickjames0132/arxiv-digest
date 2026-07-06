# `agents`

The AI teacher, rebuilt as a crew of agents: one **orchestrator** delegating to
focused **sub-agents**, every agent defined by Pydantic objects (PydanticAI
`Agent`s wired from `config.llm.agents` entries) instead of the old repo's
hand-rolled Anthropic SDK loops.

**Status: workflow definitions only.** This README and the `skills/` drafts
define every workflow *before* any agent code is written. The sub-agent
packages land next, one at a time.

## Where this came from — the old `teacher/` package, mapped

Every LLM workflow in the old repo lived in `teacher/` (nothing else in the
app talked to a model). Here's where each piece goes:

| Old (`teacher/`)                        | New (`agents/`)                                   |
| --------------------------------------- | ------------------------------------------------- |
| `lecture.py` — `lecture_beats`          | `lecturer/` sub-agent                             |
| `lecture.py` — `history_backfill`       | orchestrator tool (deterministic, no LLM)         |
| `agentic.py` + `tools.py`               | `tutor/` sub-agent                                |
| `qa.py` — non-agentic grounded Q&A      | **deleted** — the tutor is always available now   |
| `sources_chat.py`                       | `librarian/` sub-agent                            |
| *(new — the `_expand_query` seam)*      | `query_analyst/` sub-agent                        |
| `neighbors.py` — cached S2 hops/search  | `traversal.py` (shared, root level)               |
| `common.py` — numbered-papers plumbing  | `events.py` + the `numbered-papers` skill         |
| `common.py` — `<<CITED>>` sentinel      | **deleted** — citations are structured output     |
| `backends.py` — API/CLI + fallback      | **deleted** — API-only through PydanticAI         |
| `routes/teacher.py` — session history   | stays in the routes layer (Phase 5), passed in    |

## Decisions log (locked before design)

1. **Hybrid orchestration with intent hints.** Routes always call the
   orchestrator, passing the UI's intent (`lecture` / `q&a` / `librarian`).
   Known intents dispatch straight to the matching sub-agent per its
   `skills/workflows/` playbook — no routing LLM call. The orchestrator's
   own model engages only when intent is ambiguous or a workflow needs
   multi-step coordination.
2. **API-only.** The claude-CLI backend (subscription streaming) is gone —
   it existed to power tool-free fallbacks, and PydanticAI can't drive it.
   `backends.py` and the before-first-token fallback dance die with it.
3. **The non-agentic grounded Q&A is deleted, not ported.** It was the CLI
   backend's consolation prize. One tutor, always with tools; easy questions
   simply won't trigger tool calls.
4. **Structured outputs everywhere.** Lecture beats stream as typed objects
   (no newline-delimited-JSON parsing); cited papers are a field of the
   answer (no `<<CITED>>` sentinel, no hold-back streaming, no `discard`
   events). The one string protocol that survives is `<<FIG n>>` — a figure
   marker is *positional within prose*, which structured output can't
   express.

## Architecture

```
agents/
  README.md          ← this document
  events.py          ← shared: the typed event stream every workflow emits
  traversal.py       ← shared: day-cached S2 hops + free-text search (plumbing)
  skills/            ← shared: skills.md files any sub-agent's config may load
    numbered-papers.md      the index-not-id grounding protocol
    teaching-voice.md       the "sharp, friendly teacher" persona rules
    citation-discipline.md  ground only in provided/read material; never invent
    figures.md              real figures only; <<FIG n>> marker placement
    workflows/              ← the orchestrator's playbooks, one per intent
      lecture.md              backfill → lecturer
      q&a.md                  the tutor Q&A
      librarian.md            the librarian RAG chat
  orchestrator/      ← an agent: main.py, tools.py, config.py, README.md
  lecturer/          ← an agent:    "        "         "          "
  tutor/             ← an agent:    "        "         "          "
  librarian/         ← an agent:    "        "         "          "
  query_analyst/     ← an agent:    "        "         "          "
```

### Layout rules

- **The package root *is* the shared directory.** Anything sitting directly
  at the root (`events.py`, `traversal.py`, `skills/`) is shared
  infrastructure available to every agent. Every sub-package *is* an agent.
- **`tools.py` appears only inside an agent** and only ever means "this
  agent's model-callable tool surface" — functions registered on the
  PydanticAI agent whose signatures become schemas the LLM sees. Shared
  *plumbing* (code tools call into, which no model ever sees) lives at the
  root as ordinary modules; it is never called "tools."
- **Every sub-agent package carries its own `README.md`** documenting its
  workflow, tools, budgets, and events.

### The sub-agent contract

Each sub-agent package is exactly:

- **`main.py`** — the PydanticAI `Agent`: its deps type, output type, and
  construction from the agent's `config.llm.agents` entry (looked up by id).
- **`tools.py`** — tools only *this* agent exposes to its model. Absent when
  the agent has none.
- **`config.py`** — the agent's system prompt, the list of skills it loads
  from `agents/skills/`, and its budget knobs. The central
  `config.llm.agents` entry supplies the model string and tunables; the
  package's `config.py` supplies the words.
- **`README.md`** — the agent's own documentation.

### Skills

A skill is a markdown file in `agents/skills/` holding prompt-ready
instructions. Each sub-agent's `config.py` names the skills it loads; a
shared loader reads them and appends their content to the agent's system
prompt. Two kinds live side by side:

- **Behavior skills** (the files at the `skills/` root: `numbered-papers`,
  `teaching-voice`, `citation-discipline`, `figures`) — reusable
  instruction blocks shared by whichever agents opt in.
- **Workflow skills** (`skills/workflows/`) — the orchestrator's playbooks:
  one per intent, defining inputs, steps, delegation, and the event stream.
  For a known intent the dispatch is deterministic code that *implements*
  the skill; when the orchestrator's model engages, the skills are its
  instructions.

## The workflows

### `orchestrator`

The front door. Input: an intent hint + the request payload. For the three
known intents it runs the matching workflow skill deterministically; its
model engages only for ambiguous or multi-step requests. Its `tools.py`
holds the sub-agent delegations plus **`history_backfill`** — the
deterministic reference-walk ported from the old `lecture.py`: launch from
the oldest visible papers, hop backward through day-cached references, add
the most-cited new ancestors per hop, stop at a year floor or the hop
budget, emit `Trace`/`Discovery` events per productive hop. Not an agent —
no LLM ever touches it.

### `lecturer` — the streamed graph lecture

- **Input:** seed, visible nodes (numbered), mode
  (`history` / `intuition` / `bridge`), target paper (bridge only). History
  mode receives the backfill-enriched node set from the orchestrator.
- **Tools:** none.
- **Output:** a streamed sequence of typed `Beat` objects
  (`heading`, `text`, `node_indices` → mapped back to node ids) so the
  frontend reveals the story beat-by-beat and lights up graph nodes in sync.
  Structured output replaces the old NDJSON protocol and its fence-stripping
  parser.
- **Skills:** `numbered-papers`, `teaching-voice`, `citation-discipline`.
- **Config:** the three mode-intent paragraphs; beat count bounds (5–9).

### `tutor` — agentic Q&A over the graph

The flagship. Reads, expands, and searches via tool use, then answers
grounded in what it actually read.

- **Input:** question, seed, visible nodes, conversation history, optional
  library scope (`source_ids`: `None` = whole library, present list =
  pinned to exactly those, empty list = source search disabled).
- **Tools** (its `tools.py`):
  - `read_paper` — summary (abstract + TL;DR, hydrated from S2 on demand)
    or full text via ar5iv; a full read also lists the paper's figures.
  - `expand_node` — one hop of references / citations / similar for a
    numbered paper; new papers get numbered and streamed to the graph.
  - `search_papers` — free-text S2 search with a year window; hits get
    numbered and added (nodes only, no edges — a topic search links to no
    specific paper).
  - `show_figure` — attach a real ar5iv figure; the model places a
    `<<FIG n>>` marker in its prose where the image belongs.
  - `search_sources` — semantic search over the user's library; registered
    only when a library exists (checked before the embedding model loads).
- **Budgets:** total steps, wall clock, full/summary reads, hops, searches,
  source searches, figures — from its agents entry. Visited-sets, the read
  cache, and remaining budgets live in the run's deps.
- **Output:** streamed answer prose, with `cited` (the papers it read plus
  any it named) as a structured field of the final result.
- **Events:** `Trace` (each tool step), `Discovery` (nodes/edges to merge
  into the live graph), `Figure`, `Token`, `Cited`.
- **Skills:** `numbered-papers`, `teaching-voice`, `citation-discipline`,
  `figures`.

### `librarian` — offline library chat

Graph-free RAG over the user's own uploaded sources.

- **Input:** question, conversation history, optional scope. Retrieval
  (`services.sources.search` — RRF over FTS5 + vectors) runs *before* the
  agent, deterministically; the passages go in as context.
- **Tools:** none.
- **Output:** streamed prose citing inline by title and page, e.g.
  "(Deep Learning, p.243)". A `Trace` event names the retrieved sources
  first; empty retrieval yields a friendly "nothing found" answer without
  engaging the model.
- **Skills:** `teaching-voice`, `citation-discipline`.

### `query_analyst` — seed-search query expansion

A one-shot micro-agent, new in this rewrite (the old repo left a seam for
it).

- **Input:** the raw search query from the seed-search box.
- **Output:** structured `{expanded_query}` — acronyms and jargon expanded
  ("DQN" → "DQN deep Q-network deep Q-learning") so S2's lexical search can
  find seminal papers that never spell the acronym out.
- **Tools:** none. **Skills:** none.
- **Note:** invoked from `services/search`'s `_expand_query` seam, *not*
  through the orchestrator — it's infrastructure for search, not a teacher
  workflow. It must degrade to a passthrough on any failure: search can
  never break because the LLM hiccuped.

## Shared modules

- **`events.py`** — the typed event stream (Pydantic models): `Beat`,
  `Token`, `Trace`, `Discovery`, `Figure`, `Cited`, `Done`, `Error`.
  Replaces the old ad-hoc `("kind", data)` tuples; the routes layer
  serializes these to SSE frames. One vocabulary for every workflow, so the
  frontend speaks a single protocol.
- **`traversal.py`** — day-cached S2 hops (`references` / `citations` /
  `similar`) and free-text search, shared by the orchestrator's backfill
  and the tutor's `expand_node` / `search_papers` tools. This is the
  *cached, agent-budget-tuned* layer over
  `integrations.semantic_scholar.traversal` (which talks to the live API and
  caches nothing) — same name, different job, and the cache is the point:
  repeated expansion within a session must not hammer the rate-limited API.

## Testing

Agent loops are tested with PydanticAI's `TestModel` / `FunctionModel`
(scripted model behavior, no network) — replacing the old `fake_claude`
fixture built from raw Anthropic SDK events. Deterministic pieces
(`traversal.py`, `history_backfill`, skill loading, event models) get plain
unit tests. As everywhere in this repo: no live API calls, ever.
