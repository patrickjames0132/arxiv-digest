# Workflow: lecture

**Intent:** `lecture` — the user pressed the Lecture button on an open
graph.

**Input:** seed paper, the visible graph nodes, a mode
(`history` | `intuition` | `evolution` | `frontier` | `bridge`), and — bridge
mode only — a target paper.

**Steps:**

1. Scope the visible nodes to the mode's part of the story
   (`_story_nodes`), one graph relation each: history narrates the seed's
   **references**, evolution the **landmark citers** (`citation`), frontier the
   **Latest Publications** (`latest`) — each keeps only the seed plus nodes
   carrying that tag, sorted oldest-first. Intuition stays on the **seed
   alone**; bridge sees everything. A lecture never expands nodes — pulling new
   papers in is the researcher's job, on explicit questions.
2. Delegate to the **lecturer** with the scoped node set, mode, and
   target. Stream its `Beat` events — each carries a heading, one tight
   narration paragraph, and the node ids to light up — as they arrive.
3. Emit `Done` (or `Error` if the lecturer failed).

**Events, in order:** `Beat`+ `Done` | `Error`
