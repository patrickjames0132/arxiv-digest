# `frontend/test`

The frontend test suite: **Vitest** (+ React Testing Library for the DOM
cases), mirroring `src/` the way the backend's `test/` mirrors `src/atlas/` —
a test lives in the folder matching the module under test.

```
test/
  graph/
    model.test.ts             — formatPubDate/primaryRel/nodeRadius/cleanNode/
                                countRels/ID_RE (the pure view-model helpers)
    controls/Legend.test.tsx  — the legend's conditional agent entries
  notation/
    splitMath.test.ts         — math vs. currency vs. mid-stream tolerance
    latexToUnicode.test.ts    — the canvas-label LaTeX approximation
  teacher/
    figures/split.test.ts     — the <<FIG n>> interleaver's edge cases
    transcript/remarkCite.test.ts — [n] markers → citeref nodes, on mdast
  ui/
    useResizablePanel.test.tsx — width seeding, drag direction, clamping,
                                 the pointer-up persist
```

## The discipline (the backend's, mirrored)

- **Fully offline** — no live backend, no network. Everything covered so far
  is pure logic or self-contained DOM; when API-touching code gets tests,
  its `fetch`/SSE layer gets stubbed, never called.
- **Environment: node by default, jsdom by opt-in.** Config lives in
  `vite.config.ts`'s `test` block (`test/**/*.test.{ts,tsx}`). Pure-logic
  tests run in node; component/hook tests declare
  `// @vitest-environment jsdom` as their first line (both RTL files do).
- **No globals** — `describe`/`it`/`expect` are imported from `vitest`
  explicitly, so the tests type-check without ambient type wiring.

## Running

- `npm test --prefix frontend` — one-shot (`vitest run`); what the gate runs.
- `npm run test:watch --prefix frontend` — watch mode while developing.
- `uv run nox -s vitest` — the same one-shot, as part of the repo-wide gate
  (`uv run nox` runs it after the backend tests; it skips cleanly when npm
  isn't on PATH, the Trivy pattern).

## What deliberately isn't tested (yet)

The force-graph canvas and the sim hooks (`graph/hooks/`) — their behavior
is mutation-heavy and visual (pins surviving filters, discoveries settling
near anchors), which the end-of-phase browser milestone exercises by hand;
jsdom has no canvas. The streaming teacher pipeline (`useConversation`) is
the next natural target: its SSE handlers can be driven with scripted
events, the same idea as the backend's `fake_claude`.
