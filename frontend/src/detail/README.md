# `src/detail`

The selected paper: the right-hand detail panel and the selection state
behind it.

```
detail/
  useSelection.ts — selection id, lazy hydration/figures/code, click gesture
  DetailPanel.tsx — the panel (badges, summary, actions, code links, figures)
  detail.css      — styles (ported light-touch)
```

## Design decisions worth knowing

- **Everything about a paper loads lazily, and each thing exactly once.**
  Graph neighbors arrive summary-light; opening one hydrates its
  abstract/TL;DR on first click (cached per paper). Figures (ar5iv) fetch
  on first open, with failures cached as `unavailable` so a flaky ar5iv
  isn't re-hit; code links (HF Papers) use a requested-set for the same
  guarantee. A new graph invalidates all three caches and selects its seed.
- **Hydration works for non-arXiv papers** (fixed in this port): the fetch
  uses `arxiv_id ?? id` — the old code's arXiv gate left journal papers
  abstract-less forever, the client half of the hydration bug fixed
  server-side in Phase 5. Figures and code links stay arXiv-gated on
  purpose: ar5iv and HF Papers are arXiv-keyed services.
- **The click gesture:** single click selects; a quick (<350 ms) second
  click on the same node re-seeds the whole graph on it — wandering the
  literature node-to-node. Re-seeding uses the S2 paperId so journal
  papers work as seeds too.
- **`DetailPanel` is purely presentational**, and its `CodeRow`/
  `CodeSection` children are single-parent — nested in the parent's file
  per the hybrid structure rule. The HF section caps rows (3 models /
  2 datasets / 2 Spaces) with the totals linking out to HF Papers; the
  PDF link renders only for arXiv papers (it rewrites `/abs/` → `/pdf/`).

## Who uses it, and how/why (traced from the old app)

The shell (`Atlas.tsx`, for now) owns the `useSelection` instance, hands
its `onNodeClick` to `GraphCanvas`, renders `DetailPanel` when `selected`
is non-null, and passes `selectedId` back to the canvas for the selection
ring. The teacher's "papers I cited" chips also drive `setSelectedId`.

## How it's verified

`tsc --noEmit` strict + oxlint; the lazy-load/caching behavior and the
double-click re-seed are browser-milestone items (click a journal paper —
its abstract should now appear).
