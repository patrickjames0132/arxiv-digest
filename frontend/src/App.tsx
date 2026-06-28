import { useEffect, useState } from 'react'
import {
  fetchPapers,
  fetchSummary,
  fetchCategories,
  saveCategories,
  refresh,
  notebookLmExportUrl,
  type Paper,
  type CategoryGroup,
} from './api'
import CategoryPicker from './CategoryPicker'
import './App.css'

const PAGE_SIZE = 20

// Local-time YYYY-MM-DD (so the date picker matches the user's calendar day).
function todayISO(): string {
  const now = new Date()
  const tz = now.getTimezoneOffset() * 60000
  return new Date(now.getTime() - tz).toISOString().slice(0, 10)
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

export default function App() {
  const today = todayISO()
  const [papers, setPapers] = useState<Paper[]>([])
  const [pulledDates, setPulledDates] = useState<string[]>([])
  const [followed, setFollowed] = useState<string[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [activeDate, setActiveDate] = useState<string>(today)
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState<string>('')
  const [page, setPage] = useState(1)
  const [catGroups, setCatGroups] = useState<CategoryGroup[]>([])
  const [catOpen, setCatOpen] = useState(false)
  const [catSaving, setCatSaving] = useState(false)

  async function load(date: string) {
    setLoading(true)
    try {
      const data = await fetchPapers(date)
      setPapers(data.papers)
      setPulledDates(data.dates)
      setFollowed(data.followed_categories ?? [])
    } catch (e) {
      setStatus(String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load(activeDate)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function onDateChange(date: string) {
    if (!date) return
    setActiveDate(date)
    setSelected([])
    setPage(1)
    setStatus('')
    load(date)
  }

  function toggleCategory(cat: string) {
    setPage(1)
    setSelected((cur) =>
      cur.includes(cat) ? cur.filter((c) => c !== cat) : [...cur, cat],
    )
  }

  async function openCategories() {
    try {
      const data = await fetchCategories()
      setCatGroups(data.groups)
      setFollowed(data.followed)
      setCatOpen(true)
    } catch (e) {
      setStatus(String(e))
    }
  }

  async function onSaveCategories(codes: string[]) {
    setCatSaving(true)
    try {
      const saved = await saveCategories(codes)
      setFollowed(saved)
      // Drop any active filter chips that are no longer followed.
      setSelected((cur) => cur.filter((c) => saved.includes(c)))
      setPage(1)
      setCatOpen(false)
      setStatus(
        `Categories updated (${saved.length} followed). ` +
          `Click Refresh papers to pull ${activeDate} with the new set.`,
      )
    } catch (e) {
      setStatus(e instanceof Error ? e.message : String(e))
    } finally {
      setCatSaving(false)
    }
  }

  async function onRefresh() {
    setBusy(true)
    setStatus(`Fetching papers submitted on ${activeDate} from arXiv…`)
    try {
      const result = await refresh(activeDate)
      if (!result.ok) {
        setStatus(`Error: ${result.error}`)
      } else {
        await load(activeDate)
        setPage(1)
        setStatus(
          `Done — ${result.papers_new} new paper(s) pulled for ${activeDate}.`,
        )
      }
    } catch (e) {
      setStatus(String(e))
    } finally {
      setBusy(false)
    }
  }

  // Show papers that carry at least one selected category; no selection = all.
  const visiblePapers =
    selected.length === 0
      ? papers
      : papers.filter((p) =>
          p.categories.split(/\s+/).some((c) => selected.includes(c)),
        )

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
            Your daily CS/ML papers, summarized by Claude.
          </p>
        </div>
        <div className="controls">
          <label className="date-field">
            <span>Date</span>
            <input
              type="date"
              value={activeDate}
              max={today}
              list="pulled-dates"
              onChange={(e) => onDateChange(e.target.value)}
            />
            <datalist id="pulled-dates">
              {pulledDates.map((d) => (
                <option key={d} value={d} />
              ))}
            </datalist>
          </label>
          <button className="btn secondary" onClick={openCategories}>
            Categories{followed.length > 0 ? ` (${followed.length})` : ''}
          </button>
          <a className="btn secondary" href={notebookLmExportUrl(activeDate)}>
            Export for NotebookLM
          </a>
          <button className="btn" onClick={onRefresh} disabled={busy}>
            {busy ? 'Fetching…' : 'Refresh papers'}
          </button>
        </div>
      </header>

      {catOpen && (
        <CategoryPicker
          groups={catGroups}
          followed={followed}
          saving={catSaving}
          onSave={onSaveCategories}
          onClose={() => setCatOpen(false)}
        />
      )}

      {status && <div className="status">{status}</div>}

      {followed.length > 0 && papers.length > 0 && (
        <div className="filters">
          <span className="filters-label">Filter:</span>
          {followed.map((cat) => (
            <button
              key={cat}
              className={`filter-chip${selected.includes(cat) ? ' active' : ''}`}
              onClick={() => toggleCategory(cat)}
            >
              {cat}
            </button>
          ))}
          {selected.length > 0 && (
            <button className="link-btn" onClick={() => setSelected([])}>
              clear
            </button>
          )}
        </div>
      )}

      {loading ? (
        <p className="muted">Loading…</p>
      ) : papers.length === 0 ? (
        <div className="empty">
          <p>No papers have been pulled for {activeDate} yet.</p>
          <p className="muted">
            Click <strong>Refresh papers</strong> to fetch this day's
            submissions from arXiv in the categories you follow.
          </p>
          <button className="btn" onClick={onRefresh} disabled={busy}>
            {busy ? 'Fetching…' : 'Refresh papers'}
          </button>
        </div>
      ) : (
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
      )}

      <footer>
        <span>
          {visiblePapers.length}
          {selected.length > 0 ? ` of ${papers.length}` : ''} papers
        </span>
        <span> · {activeDate}</span>
      </footer>
    </div>
  )
}
