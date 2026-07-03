import { useCallback, useMemo, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import {
  streamAsk,
  streamLecture,
  type Beat,
  type GraphResponse,
  type LectureMode,
  type TeacherNode,
  type TraceEvent,
} from './api'

// The AI teacher panel: a streaming lecture over the visible graph plus a
// grounded Q&A chat. Both light up graph nodes via `onHighlight` — the lecture
// per-beat, Q&A on the papers an answer cites. Phase 3a: grounded in the
// on-screen neighborhood only (no agentic traversal yet).

type ChatMsg = {
  role: 'user' | 'assistant'
  text: string
  cited?: string[]
  trace?: TraceEvent[] // agent steps (papers read) for an assistant turn
}

const MODES: { key: LectureMode; label: string }[] = [
  { key: 'history', label: 'How we got here' },
  { key: 'intuition', label: "This paper's intuition" },
]

function toTeacherNodes(graph: GraphResponse): TeacherNode[] {
  return graph.nodes.map((n) => ({
    id: n.id,
    title: n.title,
    year: n.year,
    citation_count: n.citation_count,
    authors: n.authors,
    tldr: n.tldr,
    abstract: n.abstract,
    rels: n.rels,
  }))
}

export default function Teacher({
  graph,
  onHighlight,
}: {
  graph: GraphResponse
  onHighlight: (ids: Set<string>) => void
}) {
  const [beats, setBeats] = useState<Beat[]>([])
  const [activeBeat, setActiveBeat] = useState<number | null>(null)
  const [teaching, setTeaching] = useState(false)
  const [chat, setChat] = useState<ChatMsg[]>([])
  const [input, setInput] = useState('')
  const [asking, setAsking] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const sessionId = useRef(
    (crypto.randomUUID?.() as string) || String(Math.random()).slice(2),
  )
  const abortRef = useRef<AbortController | null>(null)
  const seed = useMemo(() => ({ title: graph.seed.title, id: graph.seed.id }), [graph])

  const stopActive = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
  }, [])

  const highlightBeat = useCallback(
    (i: number, beat: Beat) => {
      setActiveBeat(i)
      onHighlight(new Set(beat.node_ids))
    },
    [onHighlight],
  )

  const runLecture = useCallback(
    async (mode: LectureMode) => {
      stopActive()
      const ctrl = new AbortController()
      abortRef.current = ctrl
      setBeats([])
      setActiveBeat(null)
      setError(null)
      setTeaching(true)
      onHighlight(new Set())
      try {
        await streamLecture(
          { seed, nodes: toTeacherNodes(graph), mode },
          {
            signal: ctrl.signal,
            onBeat: (beat) =>
              setBeats((prev) => {
                const next = [...prev, beat]
                // Light up each beat as it arrives.
                highlightBeat(next.length - 1, beat)
                return next
              }),
            onError: (m) => setError(m),
          },
        )
      } catch (e) {
        if (!ctrl.signal.aborted)
          setError(e instanceof Error ? e.message : String(e))
      } finally {
        if (abortRef.current === ctrl) abortRef.current = null
        setTeaching(false)
      }
    },
    [graph, seed, onHighlight, highlightBeat, stopActive],
  )

  const onAsk = useCallback(
    async (e: FormEvent) => {
      e.preventDefault()
      const q = input.trim()
      if (!q || asking) return
      stopActive()
      const ctrl = new AbortController()
      abortRef.current = ctrl
      setInput('')
      setError(null)
      setAsking(true)
      onHighlight(new Set())
      setChat((prev) => [...prev, { role: 'user', text: q }, { role: 'assistant', text: '' }])
      try {
        await streamAsk(
          { question: q, session_id: sessionId.current, seed, nodes: toTeacherNodes(graph) },
          {
            signal: ctrl.signal,
            onToken: (text) =>
              setChat((prev) => {
                const next = [...prev]
                next[next.length - 1] = {
                  ...next[next.length - 1],
                  text: next[next.length - 1].text + text,
                }
                return next
              }),
            onTrace: (t) =>
              setChat((prev) => {
                const next = [...prev]
                const last = next[next.length - 1]
                next[next.length - 1] = { ...last, trace: [...(last.trace ?? []), t] }
                return next
              }),
            onDiscard: () =>
              setChat((prev) => {
                const next = [...prev]
                next[next.length - 1] = { ...next[next.length - 1], text: '' }
                return next
              }),
            onCited: (ids) => {
              onHighlight(new Set(ids))
              setChat((prev) => {
                const next = [...prev]
                next[next.length - 1] = { ...next[next.length - 1], cited: ids }
                return next
              })
            },
            onError: (m) => setError(m),
          },
        )
      } catch (err) {
        if (!ctrl.signal.aborted)
          setError(err instanceof Error ? err.message : String(err))
      } finally {
        if (abortRef.current === ctrl) abortRef.current = null
        setAsking(false)
      }
    },
    [input, asking, graph, seed, onHighlight, stopActive],
  )

  return (
    <section className="teacher">
      <div className="teacher-head">
        <span className="teacher-title">AI teacher</span>
        <div className="teacher-modes">
          {MODES.map((m) => (
            <button
              key={m.key}
              className="teach-btn"
              onClick={() => runLecture(m.key)}
              disabled={teaching}
            >
              {teaching ? '…' : m.label}
            </button>
          ))}
        </div>
      </div>

      <div className="teacher-scroll">
        {beats.length > 0 && (
          <ol className="beats">
            {beats.map((b, i) => (
              <li
                key={i}
                className={`beat ${activeBeat === i ? 'active' : ''}`}
                onClick={() => highlightBeat(i, b)}
              >
                {b.heading && <div className="beat-heading">{b.heading}</div>}
                <p>{b.text}</p>
                {b.node_ids.length > 0 && (
                  <div className="beat-nodes">
                    {b.node_ids.length} paper{b.node_ids.length > 1 ? 's' : ''} ✦
                  </div>
                )}
              </li>
            ))}
          </ol>
        )}

        {chat.map((m, i) => (
          <div key={`c${i}`} className={`chat ${m.role}`}>
            {m.trace && m.trace.length > 0 && (
              <div className="chat-trace">
                {m.trace.map((t, j) => (
                  <div key={j} className={`trace-line ${t.ok ? '' : 'fail'}`}>
                    📖 {t.ok ? 'Read' : 'Tried'}{' '}
                    <b>{t.title || `paper #${t.index}`}</b>
                    <em>{t.detail === 'full' ? 'full text' : 'summary'}</em>
                  </div>
                ))}
              </div>
            )}
            {m.text ||
              (m.role === 'assistant' && asking && !m.trace?.length ? '…' : '')}
            {m.cited && m.cited.length > 0 && (
              <div className="chat-cited">grounded in {m.cited.length} paper(s)</div>
            )}
          </div>
        ))}

        {beats.length === 0 && chat.length === 0 && !teaching && (
          <div className="teacher-hint">
            Play a lecture, or ask a question about the papers on the graph.
          </div>
        )}
        {error && <div className="teacher-error">{error}</div>}
      </div>

      <form className="teacher-ask" onSubmit={onAsk}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about the papers on screen…"
          aria-label="Ask the teacher a question"
        />
        <button type="submit" disabled={asking || !input.trim()}>
          {asking ? '…' : 'Ask'}
        </button>
      </form>
    </section>
  )
}
