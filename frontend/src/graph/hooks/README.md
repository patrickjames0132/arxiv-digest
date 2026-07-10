# `src/graph/hooks`

The three hooks that manage a live force simulation without fighting it.
They cluster here purely to keep `graph/` scannable (the original nesting
precedent the hybrid structure rule cites); all three are consumed only by
`graph/GraphExplorer.tsx`. Everything below is shaped by the core
constraint documented in `../README.md`: react-force-graph MUTATES the
node objects, so these hooks mutate in place and signal by version, never
by identity.

```
hooks/
  useDiscovery.ts — the sim-side discovery merge, in place
  usePinning.ts   — user pins (drag / toggle / release), timeline-aware
  useTimeline.ts  — the Timeline layout: year pinning, collide, axis painting
```

## `useDiscovery` — the graph grows mid-conversation

Merges the papers a workflow pulls in (the researcher's expand/search
tools) into the live graph:

- **In-place append** with id/edge-key dedupe (an edge key is
  `source|target|type`) — the store re-feeds full discovery arrays, and the
  dedupe makes that safe.
- **Anchored spawning:** a new paper starts near the paper it was
  discovered from, so it doesn't fly in from the canvas origin when the sim
  reheats; ungrounded topic-search hits (no edge) anchor on the seed with a
  wider scatter so they settle into a loose cluster instead of stacking.
- **Year-range widening:** a discovery older/newer than anything visible
  widens both the base range and the active year filter — a discovered
  paper must never arrive invisible.
- **Reheat without camera yank:** `d3ReheatSimulation`, never `zoomToFit` —
  the user may be reading the chat, not watching the graph.
- **Changes signal by version:** the hook bumps a `graphVersion` counter
  whenever it appends to `base.nodes`/`links`, so React dependents recompute
  even though `base` is the same object. Deliberate, load-bearing, and the
  opposite of idiomatic-React immutability — RFG's ownership of the objects
  rules the immutable-copy style out.
- `discoveredNodes` mirrors what was merged, kept separately so follow-up
  questions can extend the researcher's grounding without rebuilding
  `base`; on a restored session it's re-collected from the saved nodes'
  `discovered` flags.

## `usePinning` + `useTimeline` — two layouts, one pin vocabulary

Pins are just `fx`/`fy`, but their *semantics* are layout-aware:

- **Force mode:** drag pins where dropped; unpin frees the node entirely.
- **Timeline mode:** a node's x is ALWAYS its date column — dragging only
  sets height, unpinning restores the column pin, and `releaseAll` keeps
  the date structure. `nodeTimelineX` maps year + month fraction to x
  (papers sit *between* year gridlines by publication month; a paper with
  no year sits at the **seed's own exact x** — same year AND month
  fraction, so it's pixel-aligned with the seed's own column rather than
  parked in an "n.d." lane at the timeline's edge. S2 not knowing a date
  isn't evidence the paper predates everything else on the graph, and a
  node reached from the seed tends to be contemporaneous with it anyway.
  Falls back to the earliest year only if the seed itself has none; there's
  no day-level precision anywhere in this system, only year+month, so
  "exact" tops out at whatever precision the seed has).
- **Timeline physics:** pin every x, add a radius-sized collide force so a
  year column spreads out instead of clumping; `freezeSettledY` freezes
  heights once the sim settles so dragging one node can't re-relax the
  rest. The axis painter draws year gridlines/labels in graph coordinates,
  thinning labels when zoom would crowd them (≥28px apart on screen).

## How it's verified

`tsc --noEmit` strict + oxlint. The mutation-heavy behavior (pins surviving
filters, discoveries settling near anchors, timeline freezing) is exactly
what the end-of-phase browser milestone exercises by hand.
