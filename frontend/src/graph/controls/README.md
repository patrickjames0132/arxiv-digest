# `src/graph/controls`

The DOM chrome over the canvas — the declutter panel and the color legend.
Two components, nested here per the hybrid structure rule: their only
parent is `graph/GraphExplorer.tsx`.

```
controls/
  GraphControls.tsx — layout toggle, per-relation chips + count sliders,
                      the dual-knob year slider, count readout,
                      release/fit/refresh actions, the gesture hint line
  Legend.tsx        — the color legend (agent entries appear on first use)
```

Both are purely presentational (the Phase 6 state directive): every set,
count, and id arrives as a prop from `GraphExplorer`; every interaction
fires a callback upward. Both read `../theme.ts` (`REL_COLOR` /
`REL_LABEL` / `REL_TYPES`) so the chrome can never disagree with the
canvas about what "a reference" looks like, and both style via
`../graph.css`.

## `GraphControls` — points worth knowing

- **Per-relation sliders are reveals, not queries.** The backend ships each
  relation's whole ranked pool; a slider shows ranks `0..limit-1`, so
  dragging it never re-fetches. `counts` is the pool size (the slider max),
  `limits` the visible count.
- **The year slider only renders when the graph spans more than one
  year** — a single-year graph gets nothing to filter. Its two knobs clamp
  against each other (`lo ≤ hi`).
- **The hint line teaches per-layout gestures** — drag-to-pin in Force,
  left→right-by-year in Timeline; double-click-to-reseed in both.
- **Refresh** busts the seed's day-cached snapshot server-side; the button
  disables while a load is in flight.

## `Legend` — never explain marks that aren't on screen

The five relation entries are static; the two agent-related entries are
conditional: "Discovered by teacher" (dashed ring) appears only once the
agent has actually pulled a paper in mid-conversation, "Found by search"
(pink) only once an ungrounded topic-search hit landed. The flags come from
the workspace slice's selectors (`selectHasDiscovered` /
`selectHasSearchHits`), via `GraphExplorer`.

## How it's verified

`tsc --noEmit` strict + oxlint; slider/chip/legend behavior is a standing
item of the end-of-phase browser milestone.
