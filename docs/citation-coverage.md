# Citation coverage: preprints, completeness, and S2 vs OpenAlex

Why the graph talks to **two** academic-data sources (Semantic Scholar +
OpenAlex), what "citation completeness" actually means, and how the two
sources compare on it — with real measured numbers. Written to settle a
recurring question: *could we drop S2 and go OpenAlex-only?* Read this
before touching `services/graph/build.py`'s dual-source citation logic or the
`integrations/` clients.

## The concepts

### Preprint

A **preprint** is a paper made public *before* (or without) formal peer
review. **arXiv is a preprint server** — every arXiv paper is a preprint.
Many preprints are later published in a peer-reviewed venue (journal or
conference) as the **version of record** (VoR), often with a *different
title*, revised content, and a **DOI**. So the same intellectual work
routinely exists as **two records**:

- the **arXiv preprint** (id like `1512.03385`), and
- the **published version** (a DOI, e.g. in CVPR / Nature / PRL).

This one-work-two-records fact is the root of almost every citation-count
discrepancy below.

### References vs. citations — the direction matters

- **References** = the papers a seed *cites* (outbound; its own
  bibliography). Both databases get this reliably in principle — it's parsed
  from the seed's own reference list.
- **Citations** = the papers that *cite the seed* (inbound; "who pointed at
  this"). This is the hard one: to know it, a database must have indexed
  **every** citing paper in existence and correctly parsed *their* reference
  lists.

**"Citation completeness" is almost entirely about the inbound count** — how
many of the papers that actually cite the seed a database knows about. Two
databases disagree because of corpus coverage, citation-extraction quality,
and — the big one — the preprint split.

### Why preprints break citation aggregation

Say a paper exists as both an arXiv preprint and a CVPR publication. Some
later papers cite `arXiv:1512.03385`; others cite `CVPR 2016, doi:…`. A
citation database only aggregates those into **one** number if it **merges**
the two records into a single work. If it *doesn't* merge them, the citations
**split** across two records and each alone looks under-cited. That's the
**duplicate-works problem**, and OpenAlex is more prone to it than S2.

## Measured comparison (snapshot: 2026-07-12)

A spread of arXiv seeds — CS / physics / math, old and new — through each
source's live API. `OA via arXiv-DOI` is the app's *current* cheapest-first
resolution (`resolve_work` tries the arXiv DOI before a title search);
`OA via title` forces a title search sorted by `cited_by_count:desc`, i.e.
OpenAlex's *best-case* canonical record.

| Seed | S2 | OA via arXiv-DOI | OA via title (most-cited) |
|---|--:|--:|--:|
| ResNet (CS, 2015) | 233,242 | 4,734 | **222,747** |
| QMIX (CS/RL, 2018) | 2,055 | 352 | 479 |
| Llama 2 (CS, 2023) | 17,548 | 2,635 | 2,635 |
| LIGO GW150914 (physics, 2016) | 3,560 | 8 | **14,324** |
| Maldacena AdS/CFT (physics, 1997) | 19,917 | 17 | **14,567** |
| Perelman (math, 2002) | 3,283 | — | — (title search found nothing) |

(Counts drift over time; the *pattern* is the point, not the exact numbers.)

## What the numbers say

1. **arXiv-DOI resolution lands on the preprint stub.** For ResNet / LIGO /
   Maldacena the DOI column resolves to the citation-poor **preprint record**
   (4,734 / 8 / 17) instead of the canonical published work. The hybrid
   currently **masks** this: `build.py` takes `max(S2, OA)` for the citation
   count, so the graph shows S2's correct 233k. **Drop S2 without also fixing
   resolution and ResNet's node would read 4,734 citations, LIGO's would read
   8.** A latent landmine, not a gradual regression.

2. **Best-case OA coverage is bimodal.**
   - *Established / physics papers* — OA is competitive-to-better (ResNet 95%
     of S2; LIGO and Maldacena *higher* than S2). The problem there is
     resolution, not coverage.
   - *Recent ML preprints* — OA genuinely lags: Llama 2 **15%** of S2, QMIX
     **23%**. These are exactly the CS/ML arXiv papers this app is most used
     on.
   - *Old / LaTeX-titled papers* — resolution is fragile: Perelman's title
     search returned nothing (old-style math id; the title cleaner doesn't
     strip TeX like Maldacena's `$N$`).

3. **OpenAlex-only doesn't escape dedup.** OA has its *own* preprint/published
   duplication (why the DOI and title columns disagree), and references
   fragment too — QMIX's reference list lives on the preprint record (77
   refs) while its most-cited record has 0. OA-only trades *cross-source*
   dedup for *intra-OA canonical-record* picking — smaller, but not zero.

## Implication for the "drop S2, go OpenAlex-only" question

S2 is quietly doing **two** jobs: supplying the correct high citation counts
(via the `max`) **and** anchoring OpenAlex resolution (the app resolves the
seed through S2, then finds the OA work). So OA-only is viable **only if** you
first:

- rewrite OA resolution to prefer the **canonical / most-cited** record and
  merge preprint ↔ published (otherwise famous papers read as near-zero), and
- accept that **recent-ML-preprint citation counts drop hard** (~15–25% of
  S2).

If the app is about **graph structure** (who-cites-whom, shape, discovery),
that undercount is largely cosmetic and OA-only is a real simplification win
(no rate-limit pain, delete the hybrid glue). If **citation counts drive the
UX** (node size, "landmark" ranking, lecture figure-pool ranking), it's a
visible regression right where exploration concentrates.

See also the OpenAlex-single-source tradeoff notes and the "drop Similar
relation" ticket in [`../OnePager.md`](../OnePager.md); the raw comparison was
produced by a throwaway script against the live APIs.
