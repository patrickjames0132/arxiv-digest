# `src/teacher/transcript`

Rendering the assistant's conversation: lecture beats and chat turns, with
Markdown + math + clickable citations. A single-parent cluster nested per
the hybrid structure rule — only `teacher/Teacher.tsx` renders the two
top-level components.

```
transcript/
  BeatList.tsx       — lecture beats (click to light their papers)
  ChatMessage.tsx    — one turn: retrieval line, trace chips, prose+figures
  AnswerMarkdown.tsx — Markdown + KaTeX + [n]-citation rendering for answers
  remarkCite.ts      — the remark plugin that turns [n] markers into chips
```

## The pieces

- **`BeatList`** — each beat is a card: heading, prose, optionally one real
  paper figure (adapted to the `AnswerFigure` shape `FigCard` renders).
  Click a beat to light its papers on the graph; click the active one again
  to clear. Which beat is lit is panel-local UI state — only the resulting
  highlight ids are global (the store's highlight slice).
- **`ChatMessage`** — one turn end-to-end: the library-retrieval summary
  (graph-free mode), the researcher's live trace chips (reads / expansions
  / searches — a failed search explains *why* in plain words:
  `searchFailReason` maps the backend's `reason` codes), the prose
  interleaved with its `<<FIG n>>` figures (via `../figures/split`), and
  the cited-papers footer — clickable to re-light the answer's whole
  grounding set.
- **`AnswerMarkdown`** — the researcher and librarian reply in Markdown
  with `$…$` math and inline `[n]` citations; this renders all three for
  real: remark-gfm for structure, remark-math + rehype-katex for math (the
  same KaTeX the rest of the app reaches through `MathText` — beats, the
  detail panel, and search hits keep `MathText`; only answers get the
  fuller Markdown treatment), and `remarkCite` for the markers. Links
  always open a new tab — an answer lives in a docked panel.
- **`remarkCite`** — rewrites `[n]` text nodes into a synthetic `citeref`
  element the renderer maps to a chip. It only rewrites the *shape*;
  whether a given `[n]` resolves to a paper (and so becomes clickable,
  spotlighting that node) is decided at render time from the answer's
  `refs` map — an unresolvable marker renders inert, never broken. Runs on
  mdast text nodes only, so markers inside inline code or math are left
  untouched.

## Who uses it

`teacher/Teacher.tsx` renders `BeatList` and `ChatMessage`; the click
callbacks dispatch into the store's highlight slice. `AnswerMarkdown` and
`remarkCite` are internal to this cluster.

## How it's verified

`tsc --noEmit` strict + oxlint; beats lighting as they stream, trace chips,
and clickable `[n]` citations are standing browser-milestone items.
