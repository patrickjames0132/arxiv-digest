# `src/teacher/figures`

The inline-figure pipeline for the assistant's chat bubbles: pairing the
`<<FIG n>>` markers the researcher streams in its prose with the figures it
attached, and rendering each as a card. A single-parent cluster nested per
the hybrid structure rule — only `teacher/transcript/` renders these.

```
figures/
  split.ts    — the interleaver: pairs <<FIG n>> markers with attached figures
  FigCard.tsx — one figure card: proxied image + caption, click to enlarge
```

## `split.ts` — the interleaver's edge cases

`splitAnswer(text, figures)` returns the prose split into interleaved
text/figure parts, plus the `leftover` figures whose marker never appeared
(those render at the bubble's end — the pre-inline fallback, which also
covers old saved sessions whose figures carry no slot). The details that
earn their keep:

- **`FIG_TAIL` holds back a partial marker** at the end of streaming prose
  (`<<FI`, `<<FIG 1`) so a marker split across token chunks never flashes
  raw before completing.
- **An invented slot's marker vanishes cleanly** — text accumulates in a
  buffer so a marker with no matching figure disappears without gluing its
  surrounding paragraphs together.
- **A slot renders at most once** — duplicate markers for the same figure
  are dropped after the first.

## `FigCard` — deliberately dumb

Image (already proxied same-origin by the backend — the frontend never
hotlinks ar5iv), figure number, optional source-paper title and caption
(both through `MathText` — captions carry LaTeX), and an `onEnlarge`
callback the parent wires to the shared `figures/Lightbox` (root-level —
promoted out of here once the detail panel became a second consumer;
`FigCard` itself stays teacher-only).

## Who uses it

`teacher/transcript/ChatMessage.tsx` (answer prose interleaving) and
`teacher/transcript/BeatList.tsx` (a lecture beat's single attached figure,
adapted to the same `AnswerFigure` shape).

## How it's verified

`tsc --noEmit` strict + oxlint; streaming behavior (no raw marker flashes,
figures landing mid-prose) is a browser-milestone item.
