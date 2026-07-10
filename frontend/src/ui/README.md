# `src/ui`

Small cross-cutting UI utilities with multiple consumers and no feature
home — the root-level case of the hybrid structure rule. One module today:

```
ui/
  useResizablePanel.ts — drag-to-resize for a right-docked panel, width
                         remembered in localStorage
```

## `useResizablePanel`

Both the detail panel and the assistant panel dock on the right (border on
their left edge), so the drag handle lives on that inner-left edge:
dragging *left* widens, *right* narrows. The hook owns only the width
number + the pointer bookkeeping; the caller renders the panel with
`style={{ width }}` and drops a handle element wired to
`onHandlePointerDown`.

- **`defaultWidth` must match the panel's CSS width** so nothing shifts on
  first paint (the stored width, once one exists, wins).
- Each consumer passes its own `storageKey`, so the two panels remember
  their widths independently.
- Bounds clamp to 280–680px by default, overridable per panel.

## Who uses it

`detail/DetailPanel.tsx` and `teacher/Teacher.tsx` — the two right-docked
panels. (A second consumer is exactly why this lives at the root rather
than nested in either feature folder.)

## How it's verified

`tsc --noEmit` strict + oxlint; drag behavior and width persistence are
browser-milestone items.
