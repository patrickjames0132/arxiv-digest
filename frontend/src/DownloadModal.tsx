import { useMemo, useState } from 'react'
import type { CategoryGroup } from './api'

// The single "Download papers" modal: choose the subjects AND the date range to
// pull from arXiv, then download. Groups every ingestion control (dates,
// categories, download, re-pull) in one place — deliberately separate from the
// main screen's view/filter date range, which only browses what's already saved.
export default function DownloadModal({
  groups,
  followed,
  saving,
  busy,
  dlStart,
  dlEnd,
  today,
  onDlStartChange,
  onDlEndChange,
  onDownload,
  onClose,
}: {
  groups: CategoryGroup[]
  followed: string[]
  saving: boolean
  busy: boolean
  dlStart: string
  dlEnd: string
  today: string
  onDlStartChange: (date: string) => void
  onDlEndChange: (date: string) => void
  onDownload: (codes: string[], opts: { force?: boolean }) => void
  onClose: () => void
}) {
  const [picked, setPicked] = useState<Set<string>>(new Set(followed))
  const [query, setQuery] = useState('')

  const q = query.trim().toLowerCase()
  const filteredGroups = useMemo(
    () =>
      groups
        .map((g) => ({
          group: g.group,
          categories: g.categories.filter(
            (c) =>
              !q ||
              c.code.toLowerCase().includes(q) ||
              c.name.toLowerCase().includes(q),
          ),
        }))
        .filter((g) => g.categories.length > 0),
    [groups, q],
  )

  function toggle(code: string) {
    setPicked((prev) => {
      const next = new Set(prev)
      if (next.has(code)) next.delete(code)
      else next.add(code)
      return next
    })
  }

  function clearAll() {
    setPicked(new Set())
  }

  function setMany(codes: string[], on: boolean) {
    setPicked((prev) => {
      const next = new Set(prev)
      for (const c of codes) {
        if (on) next.add(c)
        else next.delete(c)
      }
      return next
    })
  }

  const dlLabel = dlStart === dlEnd ? dlStart : `${dlStart} → ${dlEnd}`
  const disabled = saving || busy || picked.size === 0

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-label="Download papers"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-head">
          <div>
            <h2>Download papers</h2>
            <p className="muted">
              Pull papers from arXiv for these subjects and dates. (This is
              separate from the view date on the main screen, which only filters
              what you've already downloaded.)
            </p>
          </div>
          <button className="link-btn" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="download-dates">
          <label className="date-field">
            <span>From</span>
            <input
              type="date"
              value={dlStart}
              max={today}
              onChange={(e) => onDlStartChange(e.target.value)}
            />
          </label>
          <label className="date-field">
            <span>To</span>
            <input
              type="date"
              value={dlEnd}
              min={dlStart}
              max={today}
              onChange={(e) => onDlEndChange(e.target.value)}
            />
          </label>
        </div>

        <input
          className="cat-search"
          type="search"
          placeholder="Search code or name (e.g. cs.LG, robotics)…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoFocus
        />

        <div className="cat-groups">
          {filteredGroups.map((g) => {
            const codes = g.categories.map((c) => c.code)
            const allOn = codes.every((c) => picked.has(c))
            return (
              <section key={g.group} className="cat-group">
                <div className="cat-group-head">
                  <span className="cat-group-name">{g.group}</span>
                  <button
                    className="link-btn"
                    onClick={() => setMany(codes, !allOn)}
                  >
                    {allOn ? 'clear all' : 'select all'}
                  </button>
                </div>
                <div className="cat-grid">
                  {g.categories.map((c) => (
                    <label
                      key={c.code}
                      className="cat-option"
                      title={`${c.code} — ${c.name}`}
                    >
                      <input
                        type="checkbox"
                        checked={picked.has(c.code)}
                        onChange={() => toggle(c.code)}
                      />
                      <span className="cat-code">{c.code}</span>
                      <span className="cat-name">{c.name}</span>
                    </label>
                  ))}
                </div>
              </section>
            )
          })}
          {filteredGroups.length === 0 && (
            <p className="muted">No categories match “{query}”.</p>
          )}
        </div>

        <div className="modal-foot">
          <div className="modal-foot-info">
            <span className="muted">{picked.size} selected</span>
            <button
              className="link-btn"
              onClick={clearAll}
              disabled={saving || picked.size === 0}
            >
              Clear all
            </button>
          </div>
          <div className="modal-actions">
            <button className="btn secondary" onClick={onClose} disabled={saving}>
              Cancel
            </button>
            <button
              className="btn secondary"
              onClick={() => onDownload([...picked], { force: true })}
              disabled={disabled}
              title={`Re-fetch every day in ${dlLabel} from arXiv (catches late/cross-listed additions)`}
            >
              Re-pull all
            </button>
            <button
              className="btn"
              onClick={() => onDownload([...picked], { force: false })}
              disabled={disabled}
              title={`Pull new days in ${dlLabel} (skips days already downloaded for these categories)`}
            >
              {saving ? 'Saving…' : busy ? 'Downloading…' : `Download ${dlLabel}`}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
