// Typed client for the arXiv Digest backend API.

export interface Paper {
  arxiv_id: string
  title: string
  authors: string
  categories: string
  abstract: string
  url: string
  summary: string | null
  digest_date: string
}

export interface PapersResponse {
  date: string | null
  count: number
  papers: Paper[]
  dates: string[]
  followed_categories: string[]
}

export interface RefreshResult {
  ok: boolean
  error?: string
  emails_found?: number
  papers_parsed?: number
  papers_new?: number
  papers_summarized?: number
  digest_date?: string
}

export async function fetchPapers(date?: string): Promise<PapersResponse> {
  const qs = date ? `?date=${encodeURIComponent(date)}` : ''
  const res = await fetch(`/api/papers${qs}`)
  if (!res.ok) throw new Error(`Failed to load papers (${res.status})`)
  return res.json()
}

// Pull papers submitted on `date` (default: today) from arXiv. Summaries are
// generated per-row on demand, so this only fetches & stores the papers.
export async function refresh(
  date?: string,
  summarize = false,
): Promise<RefreshResult> {
  const res = await fetch('/api/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ date, summarize }),
  })
  return res.json()
}

// Generate (or fetch the cached) summary for a single paper.
export async function fetchSummary(arxivId: string): Promise<string> {
  const res = await fetch(
    `/api/papers/${encodeURIComponent(arxivId)}/summary`,
    { method: 'POST' },
  )
  const data = await res.json()
  if (!res.ok || !data.ok) {
    throw new Error(data.error || `Failed to summarize (${res.status})`)
  }
  return data.summary as string
}

export interface Category {
  code: string
  name: string
}

export interface CategoryGroup {
  group: string
  categories: Category[]
}

export interface CategoriesResponse {
  groups: CategoryGroup[]
  followed: string[]
}

// The full arXiv taxonomy plus the categories the user currently follows.
export async function fetchCategories(): Promise<CategoriesResponse> {
  const res = await fetch('/api/categories')
  if (!res.ok) throw new Error(`Failed to load categories (${res.status})`)
  return res.json()
}

// Replace the followed-category set; returns the saved (cleaned) list.
export async function saveCategories(followed: string[]): Promise<string[]> {
  const res = await fetch('/api/categories', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ followed }),
  })
  const data = await res.json()
  if (!res.ok || !data.ok) {
    throw new Error(data.error || `Failed to save categories (${res.status})`)
  }
  return data.followed as string[]
}

// Returns the URL that downloads a NotebookLM-ready Markdown digest.
export function notebookLmExportUrl(date?: string): string {
  const qs = date ? `?date=${encodeURIComponent(date)}` : ''
  return `/api/export/notebooklm${qs}`
}
