import { useEffect, useMemo, useRef, useState } from 'react'
import {
  fetchPapers,
  fetchSummary,
  fetchCategories,
  saveCategories,
  refresh,
  searchPapers,
  searchArxiv,
  addArxivPaper,
  notebookLmExportUrl,
  type Paper,
  type ArxivHit,
  type CategoryGroup,
} from './api'
import DownloadModal from './DownloadModal'
import CategoryFilter, { type FilterOption } from './CategoryFilter'
import './App.css'

const PAGE_SIZE = 20

// Local-time YYYY-MM-DD (so the date picker matches the user's calendar day).
function todayISO(): string {
  const now = new Date()
  const tz = now.getTimezoneOffset() * 60000
  return new Date(now.getTime() - tz).toISOString().slice(0, 10)
}

// The calendar day before `iso` (YYYY-MM-DD), computed in local time. Built from
// numeric parts so we never trip over UTC parsing shifting the date.
function prevDay(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number)
  const dt = new Date(y, m - 1, d)
  dt.setDate(dt.getDate() - 1)
  const mm = String(dt.getMonth() + 1).padStart(2, '0')
  const dd = String(dt.getDate()).padStart(2, '0')
  return `${dt.getFullYear()}-${mm}-${dd}`
}

// Every day in [start, end] inclusive, newest first (so the table grows
// newest→oldest, matching the stored ordering).
function daysDescending(start: string, end: string): string[] {
  const days: string[] = []
  for (let cur = end; cur >= start; cur = prevDay(cur)) days.push(cur)
  return days
}

function PaperRow({ paper }: { paper: Paper }) {
  const [open, setOpen] = useState(false)
  const [summary, setSummary] = useState<string | null>(paper.summary)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function getSummary() {
    setLoading(true)
    setError('')
    try {
      setSummary(await fetchSummary(paper.arxiv_id))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <tr>
      <td className="title-cell">
        <a href={paper.url} target="_blank" rel="noreferrer">
          {paper.title}
        </a>
        <div className="authors">{paper.authors}</div>
      </td>
      <td className="cats">
        {paper.categories
          .split(/\s+/)
          .filter(Boolean)
          .map((c) => (
            <span className="cat-chip" key={c}>
              {c}
            </span>
          ))}
      </td>
      <td className="summary-cell">
        {summary ? (
          summary
        ) : (
          <button className="btn small" onClick={getSummary} disabled={loading}>
            {loading ? 'Summarizing…' : 'Get summary'}
          </button>
        )}
        {error && <div className="error-text">{error}</div>}
        {paper.abstract && (
          <button className="link-btn" onClick={() => setOpen((o) => !o)}>
            {open ? 'Hide abstract' : 'Show abstract'}
          </button>
        )}
        {open && <div className="abstract">{paper.abstract}</div>}
      </td>
      <td className="link-col">
        <a href={paper.url} target="_blank" rel="noreferrer">
          abs
        </a>
        <a
          href={paper.url.replace('/abs/', '/pdf/')}
          target="_blank"
          rel="noreferrer"
        >
          pdf
        </a>
      </td>
    </tr>
  )
}

// One live arXiv search result, with an Add-to-library action.
function ArxivHitRow({
  hit,
  onAdd,
  adding,
  added,
}: {
  hit: ArxivHit
  onAdd: () => void
  adding: boolean
  added: boolean
}) {
  const [open, setOpen] = useState(false)
  const inLibrary = hit.in_library || added
  return (
    <div className="arxiv-hit">
      <div className="arxiv-hit-main">
        <a
          href={hit.url}
          target="_blank"
          rel="noreferrer"
          className="arxiv-hit-title"
        >
          {hit.title}
        </a>
        <div className="authors">{hit.authors}</div>
        <div className="arxiv-hit-meta">
          <span className="muted">{hit.digest_date}</span>
          {hit.categories
            .split(/\s+/)
            .filter(Boolean)
            .slice(0, 4)
            .map((c) => (
              <span className="cat-chip" key={c}>
                {c}
              </span>
            ))}
        </div>
        {hit.abstract && (
          <button className="link-btn" onClick={() => setOpen((o) => !o)}>
            {open ? 'Hide abstract' : 'Show abstract'}
          </button>
        )}
        {open && <div className="abstract">{hit.abstract}</div>}
      </div>
      <div className="arxiv-hit-actions">
        {inLibrary ? (
          <span className="in-library" title="Already in your library">
            ✓ In library
          </span>
        ) : (
          <button className="btn small" onClick={onAdd} disabled={adding}>
            {adding ? 'Adding…' : 'Add'}
          </button>
        )}
        <a
          className="link-btn"
          href={hit.url.replace('/abs/', '/pdf/')}
          target="_blank"
          rel="noreferrer"
        >
          pdf
        </a>
      </div>
    </div>
  )
}

export default function App() {
  const today = todayISO()
  const [papers, setPapers] = useState<Paper[]>([])
  const [followed, setFollowed] = useState<string[]>([])
  const [selected, setSelected] = useState<string[]>([])
  // View range: what's shown from the DB and searched/filtered. Separate from the
  // download range below, which only controls what gets pulled from arXiv.
  const [startDate, setStartDate] = useState<string>(today)
  const [endDate, setEndDate] = useState<string>(today)
  // Download range: the dates the "Download papers" modal pulls from arXiv.
  const [dlStart, setDlStart] = useState<string>(today)
  const [dlEnd, setDlEnd] = useState<string>(today)
  const [query, setQuery] = useState('')
  const [searchResults, setSearchResults] = useState<Paper[]>([])
  const [searchMode, setSearchMode] = useState<'hybrid' | 'lexical'>('lexical')
  const [searching, setSearching] = useState(false)
  // Live "search all of arXiv" results (separate from the local library search).
  const [arxivHits, setArxivHits] = useState<ArxivHit[]>([])
  const [arxivSearching, setArxivSearching] = useState(false)
  const [arxivSearched, setArxivSearched] = useState(false)
  const [arxivError, setArxivError] = useState<string | null>(null)
  const [addingIds, setAddingIds] = useState<Set<string>>(new Set())
  const [addedIds, setAddedIds] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  // Day-by-day pull progress (null when idle): which day we're on of how many,
  // and how many papers have streamed into the table so far.
  const [progress, setProgress] = useState<{
    done: number
    total: number
    papers: number
  } | null>(null)
  const [status, setStatus] = useState<string>('')
  const [page, setPage] = useState(1)
  const [catGroups, setCatGroups] = useState<CategoryGroup[]>([])
  const [downloadOpen, setDownloadOpen] = useState(false)
  const [catSaving, setCatSaving] = useState(false)

  // A single day shows as "2026-06-26"; a span as "2026-06-24 → 2026-06-26".
  const rangeLabel =
    startDate === endDate ? startDate : `${startDate} → ${endDate}`

  // Mirror the active range in a ref so async loads/pulls can drop stale results
  // from a range the user has since navigated away from.
  const rangeKey = (s: string, e: string) => `${s}|${e}`
  const activeRangeRef = useRef(rangeKey(startDate, endDate))
  useEffect(() => {
    activeRangeRef.current = rangeKey(startDate, endDate)
  }, [startDate, endDate])

  async function load(start: string, end: string): Promise<Paper[]> {
    const key = rangeKey(start, end)
    setLoading(true)
    try {
      const data = await fetchPapers(start, end)
      if (activeRangeRef.current !== key) return data.papers // stale; don't apply
      setPapers(data.papers)
      setFollowed(data.followed_categories ?? [])
      return data.papers
    } catch (e) {
      if (activeRangeRef.current === key) setStatus(String(e))
      return []
    } finally {
      if (activeRangeRef.current === key) setLoading(false)
    }
  }

  // Pull the range one day at a time, streaming each day's papers into the table
  // as it arrives so a wide range fills in progressively instead of blocking on
  // one giant request. Aborts cleanly if the user changes the range mid-pull.
  async function pull(
    start: string,
    end: string,
    opts: { force?: boolean; categories?: string[] } = {},
  ) {
    // The category set the skip decision is about. Defaults to current state, but
    // callers (Download) pass the just-saved set, since setFollowed is async and
    // this closure would otherwise see the stale value.
    const activeCats = opts.categories ?? followed
    const key = rangeKey(start, end)
    const span = start === end ? start : `${start} → ${end}`
    const allDays = daysDescending(start, end)
    // Take ownership of this range for the duration of the pull, then fetch a
    // fresh baseline for it (existing papers to keep visible + per-day coverage
    // to decide which days to skip). We do NOT read the `papers`/`coverage` state
    // here: the download range can differ from what the view was showing, so
    // those would be stale — the baseline must come from this range's own data.
    activeRangeRef.current = key
    setBusy(true)
    setPage(1)
    let baseline: Paper[] = []
    let baseCoverage: Record<string, string[]> = {}
    if (!opts.force) {
      try {
        const data = await fetchPapers(start, end)
        if (activeRangeRef.current !== key) {
          setBusy(false)
          return
        }
        baseline = data.papers
        baseCoverage = data.coverage ?? {}
      } catch {
        // Baseline load failed; treat the range as empty and pull everything.
      }
    }
    // Show the range's existing papers immediately (empty for a force rebuild).
    setPapers(baseline)

    // By default only fetch days not yet covered for every followed category —
    // re-pulling an overlapping range shouldn't re-download (slowly) what's
    // already here, but adding a new category must re-fetch days that hold papers
    // from other categories yet were never pulled for the new one. `force`
    // re-fetches every day (to catch late/cross-listed arXiv additions).
    const isCovered = (d: string) => {
      const have = baseCoverage[d]
      if (!have) return false
      return activeCats.every((c) => have.includes(c))
    }
    const days = opts.force ? allDays : allDays.filter((d) => !isCovered(d))

    if (days.length === 0) {
      setStatus(
        `Every day in ${span} is already downloaded for these categories — ` +
          `nothing new to pull. Use “Re-pull all” to re-fetch from arXiv.`,
      )
      setBusy(false)
      return
    }

    const skipped = allDays.length - days.length
    // Seed with the range's existing papers (unless forcing a clean rebuild), so
    // they stay visible while the new days stream in.
    const acc: Paper[] = opts.force ? [] : [...baseline]
    setProgress({ done: 0, total: days.length, papers: acc.length })
    setStatus(
      skipped > 0
        ? `Fetching ${days.length} new day(s) in ${span} — ${skipped} already downloaded…`
        : `Fetching papers submitted ${span} from arXiv…`,
    )
    try {
      for (let i = 0; i < days.length; i++) {
        const day = days[i]
        const result = await refresh(day, day)
        if (activeRangeRef.current !== key) return // user navigated away; abort
        if (!result.ok) {
          setStatus(`Error on ${day}: ${result.error}`)
          return
        }
        const data = await fetchPapers(day, day)
        if (activeRangeRef.current !== key) return
        // Replace any existing rows for this day with the freshly pulled set,
        // then keep the table sorted newest-day-first.
        const merged = acc
          .filter((p) => p.digest_date !== day)
          .concat(data.papers)
        merged.sort((a, b) => (a.digest_date < b.digest_date ? 1 : -1))
        acc.length = 0
        acc.push(...merged)
        setPapers([...acc])
        setProgress({ done: i + 1, total: days.length, papers: acc.length })
      }
      setStatus(
        acc.length > 0
          ? `Pulled ${days.length} day(s) for ${span} — ${acc.length} paper(s) loaded.`
          : `No papers found on arXiv for ${span} in your followed categories.`,
      )
    } catch (e) {
      if (activeRangeRef.current === key) setStatus(String(e))
    } finally {
      // Downloads are modal-gated so only one pull runs at a time — always clear
      // the busy/progress flags when this pull ends, even if it was aborted by a
      // mid-pull view change (otherwise busy would stick on).
      setBusy(false)
      setProgress(null)
    }
  }

  // Load whatever's already stored for the selected range. Empty ranges are not
  // auto-pulled — the user pulls explicitly via the Download modal (or the empty
  // state's "Download papers" button).
  useEffect(() => {
    load(startDate, endDate)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startDate, endDate])

  // Load the taxonomy once so filter chips can show natural-language names.
  useEffect(() => {
    fetchCategories()
      .then((d) => {
        setCatGroups(d.groups)
        setFollowed(d.followed)
      })
      .catch(() => {})
  }, [])

  // Full-text search, debounced. Runs whenever the query or date range changes;
  // an empty query clears results (reverting to the range view). searchSeq drops
  // responses from a superseded keystroke so results never arrive out of order.
  const searchSeq = useRef(0)
  useEffect(() => {
    const q = query.trim()
    if (!q) {
      setSearchResults([])
      setSearching(false)
      return
    }
    const seq = ++searchSeq.current
    setSearching(true)
    const timer = setTimeout(async () => {
      try {
        const data = await searchPapers(q, startDate, endDate)
        if (searchSeq.current === seq) {
          setSearchResults(data.papers)
          setSearchMode(data.mode)
        }
      } catch {
        if (searchSeq.current === seq) setSearchResults([])
      } finally {
        if (searchSeq.current === seq) setSearching(false)
      }
    }, 250)
    return () => clearTimeout(timer)
  }, [query, startDate, endDate])

  // The list everything downstream (filters, table, pagination, footer) renders
  // from: search results when searching, otherwise the range-loaded papers.
  const searchActive = query.trim().length > 0
  const basePapers = searchActive ? searchResults : papers

  // --- Live "search all of arXiv" (fetch/add papers not yet in the library) ---
  const arxivSeq = useRef(0)

  async function runArxivSearch() {
    const q = query.trim()
    if (!q) return
    const seq = ++arxivSeq.current
    setArxivSearching(true)
    setArxivSearched(true)
    setArxivError(null)
    try {
      const data = await searchArxiv(q)
      if (arxivSeq.current === seq) setArxivHits(data.papers)
    } catch (e) {
      if (arxivSeq.current === seq) {
        setArxivHits([])
        setArxivError(e instanceof Error ? e.message : String(e))
      }
    } finally {
      if (arxivSeq.current === seq) setArxivSearching(false)
    }
  }

  // Drop any live arXiv results (used when the query changes or the user dismisses
  // the panel); bumping the seq also invalidates an in-flight search.
  function clearArxiv() {
    arxivSeq.current++
    setArxivHits([])
    setArxivSearched(false)
    setArxivSearching(false)
    setArxivError(null)
  }

  async function addPaper(hit: ArxivHit) {
    setAddingIds((prev) => new Set(prev).add(hit.arxiv_id))
    try {
      await addArxivPaper(hit.arxiv_id)
      setAddedIds((prev) => new Set(prev).add(hit.arxiv_id))
      // Refresh the library view so the new paper joins coverage + local search.
      load(startDate, endDate)
    } catch (e) {
      setStatus(e instanceof Error ? e.message : String(e))
    } finally {
      setAddingIds((prev) => {
        const next = new Set(prev)
        next.delete(hit.arxiv_id)
        return next
      })
    }
  }

  function onStartChange(date: string) {
    if (!date || date === startDate) return
    setStartDate(date)
    // Keep the range valid: never let start run past end.
    if (date > endDate) setEndDate(date)
    setSelected([])
    setPage(1)
    setStatus('')
  }

  function onEndChange(date: string) {
    if (!date || date === endDate) return
    setEndDate(date)
    // Keep the range valid: never let end fall before start.
    if (date < startDate) setStartDate(date)
    setSelected([])
    setPage(1)
    setStatus('')
  }

  // Map every category code to its natural-language name (from the taxonomy),
  // so filters read "Machine Learning" rather than "cs.LG".
  const nameMap = useMemo(() => {
    const m = new Map<string, string>()
    for (const g of catGroups) for (const c of g.categories) m.set(c.code, c.name)
    return m
  }, [catGroups])

  // Map each paper's tags to natural-language names; the names dedupe codes that
  // mean the same subject (e.g. cs.LG + stat.ML → "Machine Learning").
  function paperNames(p: Paper): string[] {
    return p.categories
      .split(/\s+/)
      .filter(Boolean)
      .map((c) => nameMap.get(c) ?? c)
  }

  // Filter options = the subjects present in the loaded day, grouped by name
  // (mirrored tags merged into one), each with a deduped paper count and the
  // underlying codes, most common first.
  const categoryOptions = useMemo<FilterOption[]>(() => {
    const counts = new Map<string, number>()
    const codes = new Map<string, Set<string>>()
    for (const p of basePapers) {
      const names = new Set<string>()
      for (const c of p.categories.split(/\s+/).filter(Boolean)) {
        const name = nameMap.get(c) ?? c
        names.add(name)
        let set = codes.get(name)
        if (!set) {
          set = new Set()
          codes.set(name, set)
        }
        set.add(c)
      }
      for (const name of names) counts.set(name, (counts.get(name) ?? 0) + 1)
    }
    return [...counts.entries()]
      .map(([name, count]) => ({
        key: name,
        label: name,
        codes: [...(codes.get(name) ?? [])].sort(),
        count,
      }))
      .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label))
  }, [basePapers, nameMap])

  const presentCategories = useMemo(
    () => categoryOptions.map((o) => o.key),
    [categoryOptions],
  )

  // Drop any active filter that's no longer present in the loaded day.
  useEffect(() => {
    setSelected((cur) => {
      const next = cur.filter((c) => presentCategories.includes(c))
      return next.length === cur.length ? cur : next
    })
  }, [presentCategories])

  function toggleCategory(cat: string) {
    setPage(1)
    setSelected((cur) =>
      cur.includes(cat) ? cur.filter((c) => c !== cat) : [...cur, cat],
    )
  }

  // Open the Download modal. Optionally preset the download range (e.g. the empty
  // state offers to pull the range you're currently viewing).
  async function openDownload(preset?: { start: string; end: string }) {
    try {
      const data = await fetchCategories()
      setCatGroups(data.groups)
      setFollowed(data.followed)
      if (preset) {
        setDlStart(preset.start)
        setDlEnd(preset.end)
      }
      setDownloadOpen(true)
    } catch (e) {
      setStatus(String(e))
    }
  }

  function onDlStartChange(date: string) {
    if (!date) return
    setDlStart(date)
    if (date > dlEnd) setDlEnd(date)
  }

  function onDlEndChange(date: string) {
    if (!date) return
    setDlEnd(date)
    if (date < dlStart) setDlStart(date)
  }

  // Persist any category change, then pull the download range. After the pull the
  // view range follows the download range so you immediately see what you pulled;
  // from there you can narrow the view independently without re-downloading.
  async function runDownload(codes: string[], opts: { force?: boolean } = {}) {
    let saved = followed
    const unchanged =
      codes.length === followed.length &&
      codes.every((c) => followed.includes(c))
    if (!unchanged) {
      setCatSaving(true)
      try {
        saved = await saveCategories(codes)
        setFollowed(saved)
      } catch (e) {
        setStatus(e instanceof Error ? e.message : String(e))
        setCatSaving(false)
        return
      }
      setCatSaving(false)
    }
    setDownloadOpen(false)
    setSelected([])
    const dlKey = rangeKey(dlStart, dlEnd)
    // pull owns the range (sets activeRangeRef) and streams into the table.
    await pull(dlStart, dlEnd, { ...opts, categories: saved })
    // Sync the view to what we just downloaded — unless the user navigated to a
    // different range mid-download, in which case respect their choice.
    if (activeRangeRef.current === dlKey) {
      setStartDate(dlStart)
      setEndDate(dlEnd)
    }
  }

  // Show papers carrying at least one selected subject (by name); none = all.
  const visiblePapers =
    selected.length === 0
      ? basePapers
      : basePapers.filter((p) => {
          const names = new Set(paperNames(p))
          return selected.some((n) => names.has(n))
        })

  const totalPages = Math.max(1, Math.ceil(visiblePapers.length / PAGE_SIZE))
  const safePage = Math.min(page, totalPages)
  const pageStart = (safePage - 1) * PAGE_SIZE
  const pagePapers = visiblePapers.slice(pageStart, pageStart + PAGE_SIZE)

  return (
    <div className="app">
      <header>
        <div>
          <h1>arXiv Digest</h1>
          <p className="subtitle">
            Your daily arxiv papers, summarized by Claude.
          </p>
        </div>
        <div className="controls">
          <span className="controls-label" title="Filters the papers you've already downloaded — does not fetch from arXiv">
            View
          </span>
          <label className="date-field">
            <span>From</span>
            <input
              type="date"
              value={startDate}
              max={today}
              onChange={(e) => onStartChange(e.target.value)}
            />
          </label>
          <label className="date-field">
            <span>To</span>
            <input
              type="date"
              value={endDate}
              min={startDate}
              max={today}
              onChange={(e) => onEndChange(e.target.value)}
            />
          </label>
          <button
            className="btn"
            onClick={() => openDownload()}
            disabled={busy}
            title="Pull papers from arXiv (choose subjects + dates)"
          >
            {busy ? 'Downloading…' : '⬇ Download'}
          </button>
          <a
            className="btn secondary"
            href={notebookLmExportUrl(startDate, endDate, searchActive ? query : undefined)}
            title={
              searchActive
                ? `Export the ${searchResults.length} search result(s) for “${query.trim()}”`
                : `Export every paper in ${rangeLabel}`
            }
          >
            {searchActive ? 'Export results' : 'Export for NotebookLM'}
          </a>
        </div>
      </header>

      <div className="search-bar">
        <span className="search-icon" aria-hidden>
          ⌕
        </span>
        <input
          className="search-input"
          type="text"
          value={query}
          placeholder={`Search by meaning or keywords in ${rangeLabel}…`}
          onChange={(e) => {
            setQuery(e.target.value)
            setPage(1)
            clearArxiv()
          }}
        />
        {searching ? (
          <span className="search-meta muted">Searching…</span>
        ) : searchActive ? (
          <span className="search-meta muted">
            {searchResults.length} result{searchResults.length === 1 ? '' : 's'}
            {searchResults.length > 0 && (
              <span className="search-mode" title={
                searchMode === 'hybrid'
                  ? 'Keyword (BM25) + semantic (embeddings), rank-fused'
                  : 'Keyword only — semantic index unavailable'
              }>
                {' '}· {searchMode === 'hybrid' ? 'hybrid' : 'keyword'}
              </span>
            )}
          </span>
        ) : null}
        {query.trim() && (
          <button
            className={`btn small arxiv-btn${
              searchActive && !searching && searchResults.length === 0
                ? ' emphasized'
                : ''
            }`}
            onClick={runArxivSearch}
            disabled={arxivSearching}
            title="Search all of arXiv (not just your library) and add papers on the fly"
          >
            {arxivSearching ? 'Searching arXiv…' : 'Search all of arXiv →'}
          </button>
        )}
        {query && (
          <button
            className="search-clear"
            onClick={() => {
              setQuery('')
              setPage(1)
              clearArxiv()
            }}
            aria-label="Clear search"
            title="Clear search"
          >
            ×
          </button>
        )}
      </div>

      {arxivSearched && (
        <div className="arxiv-results">
          <div className="arxiv-results-head">
            <span className="arxiv-results-title">
              From arXiv
              {!arxivSearching &&
                ` — ${arxivHits.length} result${
                  arxivHits.length === 1 ? '' : 's'
                } for “${query.trim()}”`}
            </span>
            <button className="link-btn" onClick={clearArxiv}>
              Dismiss
            </button>
          </div>
          {arxivSearching ? (
            <p className="muted">Searching all of arXiv…</p>
          ) : arxivError ? (
            <p className="error-text">
              arXiv search failed: {arxivError}. arXiv rate-limits rapid
              requests — wait a few seconds and{' '}
              <button className="link-btn inline" onClick={runArxivSearch}>
                try again
              </button>
              .
            </p>
          ) : arxivHits.length === 0 ? (
            <p className="muted">
              Nothing on arXiv matched “{query.trim()}”. Try different terms, or
              paste an arXiv id or link.
            </p>
          ) : (
            <div className="arxiv-hit-list">
              {arxivHits.map((h) => (
                <ArxivHitRow
                  key={h.arxiv_id}
                  hit={h}
                  adding={addingIds.has(h.arxiv_id)}
                  added={addedIds.has(h.arxiv_id)}
                  onAdd={() => addPaper(h)}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {downloadOpen && (
        <DownloadModal
          groups={catGroups}
          followed={followed}
          saving={catSaving}
          busy={busy}
          dlStart={dlStart}
          dlEnd={dlEnd}
          today={today}
          onDlStartChange={onDlStartChange}
          onDlEndChange={onDlEndChange}
          onDownload={runDownload}
          onClose={() => setDownloadOpen(false)}
        />
      )}

      {status && <div className="status">{status}</div>}

      {basePapers.length > 0 && categoryOptions.length > 0 && (
        <CategoryFilter
          options={categoryOptions}
          selected={selected}
          onToggle={toggleCategory}
          onClear={() => setSelected([])}
        />
      )}

      {busy && progress && (
        <div className="progress">
          <div className="progress-track">
            <div
              className="progress-fill"
              style={{
                width: `${Math.round((progress.done / progress.total) * 100)}%`,
              }}
            />
          </div>
          <p className="progress-text muted">
            Fetching from arXiv — day {progress.done}/{progress.total} ·{' '}
            {progress.papers} paper{progress.papers === 1 ? '' : 's'} loaded
          </p>
        </div>
      )}

      {basePapers.length > 0 ? (
        <>
          <table>
            <thead>
              <tr>
                <th>Title &amp; authors</th>
                <th>Categories</th>
                <th>AI summary</th>
                <th>Links</th>
              </tr>
            </thead>
            <tbody>
              {pagePapers.map((p) => (
                <PaperRow key={p.arxiv_id} paper={p} />
              ))}
            </tbody>
          </table>

          {totalPages > 1 && (
            <div className="pagination">
              <button
                className="btn secondary"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={safePage <= 1}
              >
                ← Prev
              </button>
              <span className="page-info">
                Page {safePage} of {totalPages}
              </span>
              <button
                className="btn secondary"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={safePage >= totalPages}
              >
                Next →
              </button>
            </div>
          )}
        </>
      ) : searchActive ? (
        searching ? (
          <p className="muted">Searching…</p>
        ) : (
          <div className="empty">
            <p>No papers match “{query.trim()}”.</p>
            <p className="muted">
              Searching your saved papers for {rangeLabel}. Try different terms,
              or widen the date range to search more of what you've pulled.
            </p>
          </div>
        )
      ) : loading && !busy ? (
        <p className="muted">Loading…</p>
      ) : busy ? null : (
        <div className="empty">
          <p>No papers for {rangeLabel}.</p>
          <p className="muted">
            You haven't downloaded anything for this range yet. Open{' '}
            <button
              className="link-btn inline"
              onClick={() => openDownload({ start: startDate, end: endDate })}
            >
              Download
            </button>{' '}
            to pull it from arXiv (and pick your subjects there).
          </p>
          <button
            className="btn"
            onClick={() => openDownload({ start: startDate, end: endDate })}
            disabled={busy}
          >
            Download papers for {rangeLabel}
          </button>
        </div>
      )}

      <footer>
        <span>
          {visiblePapers.length}
          {selected.length > 0 ? ` of ${basePapers.length}` : ''} papers
        </span>
        <span> · {rangeLabel}</span>
        {searchActive && <span> · matching “{query.trim()}”</span>}
      </footer>
    </div>
  )
}
