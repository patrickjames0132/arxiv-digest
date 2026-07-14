/**
 * Seed search: find a paper to drop into the graph — live across Semantic
 * Scholar, or instantly from the local snapshot cache — with optional
 * date / field-of-study filters on the live search.
 */

import type { GraphNode, Provider } from './graph'

/**
 * The `/api/search` response: the echoed query plus its hits. Hits are full
 * graph-node shapes (the same type a graph neighbor has) — when the query
 * named a known paper, LLM-recalled + S2-verified matches lead the list.
 */
export interface LiveSearchResponse {
  q: string
  count: number
  papers: GraphNode[]
}

/**
 * Optional filters on the seed search. All fields are optional — an empty
 * filter set means "search everything", and filters never apply to an
 * explicit arXiv id/URL lookup.
 */
export interface SearchFilters {
  /** Earliest publication year (inclusive), or null for no floor. */
  yearFrom: number | null
  /** Latest publication year (inclusive), or null for no ceiling. */
  yearTo: number | null
  /** S2 fields of study to restrict to (any-of); empty = all fields. */
  fields: string[]
}

/** The no-op filter set (everything passes). */
export const EMPTY_FILTERS: SearchFilters = { yearFrom: null, yearTo: null, fields: [] }

/**
 * Append a filter set to a query string (omitting inactive filters).
 *
 * @param params  The query string being built (mutated in place).
 * @param filters The active filters, or undefined for none.
 */
function applyFilters(params: URLSearchParams, filters?: SearchFilters): void {
  if (!filters) return
  if (filters.yearFrom != null) params.set('year_from', String(filters.yearFrom))
  if (filters.yearTo != null) params.set('year_to', String(filters.yearTo))
  if (filters.fields.length) params.set('fields', filters.fields.join(','))
}

/**
 * Relevance search across Semantic Scholar to find a seed paper.
 *
 * Accepts keywords, a title, an author, or an arXiv id/URL — the backend
 * resolves ids/URLs directly to that exact paper (ignoring filters), and
 * expands free-text queries through the query analyst before the lexical
 * search runs.
 *
 * @param q        The search query.
 * @param limit    Maximum hits to return (default 25).
 * @param filters  Optional date/field filters (see {@link SearchFilters}).
 * @param provider Which backend to search ('s2' / 'openalex') — matches the
 *                 graph provider so a hit explores under the backend that found it.
 * @returns The echoed query plus its hits, best matches first.
 * @throws When the request fails — seed search has no graceful fallback; the
 *         caller surfaces the error in the search UI.
 */
export async function searchLive(
  q: string,
  limit = 25,
  filters?: SearchFilters,
  provider: Provider = 's2',
): Promise<LiveSearchResponse> {
  const params = new URLSearchParams({ q, limit: String(limit), provider })
  applyFilters(params, filters)
  const res = await fetch(`/api/search?${params.toString()}`)
  if (!res.ok) throw new Error(`Search failed (${res.status})`)
  return res.json()
}

/**
 * A paper found in the local snapshot cache — instant, and available even
 * when the live APIs are rate-limiting us.
 */
export interface LocalHit {
  /** A provider node id, always usable as a graph seed under that provider. */
  id: string
  arxiv_id: string | null
  title: string
  authors: string | null
  year: number | null
  citation_count: number | null
  url?: string | null
  /** A fresh snapshot exists under the selected provider — explores instantly. */
  has_graph: boolean
}

/**
 * Instant search over papers already seen on previous graphs, scoped to the
 * selected provider.
 *
 * Only the chosen backend's cached snapshots are searched (snapshots are cached
 * per provider), so a hit — and its "instant" badge — reflects what can
 * actually be explored instantly *under the provider the user has selected*.
 *
 * Failures degrade to "no local hits" (an empty array) rather than throwing —
 * this must never block the live search running alongside it. The year
 * filter applies; the field filter doesn't (cached nodes are matched purely
 * on text).
 *
 * @param q        The search query.
 * @param limit    Maximum hits to return (default 10).
 * @param filters  Optional filters — only the year window applies locally.
 * @param provider The selected backend — only its cached snapshots are searched.
 * @returns The cached hits (empty on any failure).
 */
export async function searchLocal(
  q: string,
  limit = 10,
  filters?: SearchFilters,
  provider: Provider = 's2',
): Promise<LocalHit[]> {
  try {
    const params = new URLSearchParams({ q, limit: String(limit), provider })
    applyFilters(params, filters)
    params.delete('fields') // not supported locally
    const res = await fetch(`/api/local_search?${params.toString()}`)
    if (!res.ok) return []
    const data = await res.json()
    return (data.papers as LocalHit[]) ?? []
  } catch {
    return []
  }
}

/** One field-of-study option for the search filter picker: `id` is the filter
 *  value sent to the backend, `name` the label shown. For S2 the id is the field
 *  name itself; for OpenAlex it's the numeric field id (`topics.field.id`). */
export interface Field {
  id: string
  name: string
}

/**
 * Fetch the selected provider's field vocabulary (`/api/taxonomy/<provider>`)
 * for the search filter's field picker — S2's ~20 fields of study or OpenAlex's
 * 26 top-level fields. Both come back as `{id, name}` pairs, so the picker is
 * provider-agnostic (show `name`, send `id`).
 *
 * Never throws — failures degrade to an empty list, which simply renders the
 * picker without options.
 *
 * @param provider Which backend's vocabulary to fetch ('s2' / 'openalex').
 * @returns The field options (empty on any failure).
 */
export async function getFields(provider: Provider): Promise<Field[]> {
  try {
    const res = await fetch(`/api/taxonomy/${provider}`)
    if (!res.ok) return []
    return ((await res.json()) as { fields: Field[] }).fields ?? []
  } catch {
    return []
  }
}
