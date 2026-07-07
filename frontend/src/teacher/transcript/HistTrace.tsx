/** A lecture's backfill hops, shown above the beats as the story traces a
 * field back to its roots (history) or forward to its frontier (evolution)
 * before narrating. */

import type { BackfillTrace } from '../../api'

export default function HistTrace({ trace }: { trace: BackfillTrace[] }) {
  if (trace.length === 0) return null
  return (
    <div className="chat-trace hist-trace">
      {trace.map((hop, index) => {
        const forward = hop.direction === 'forward'
        // Backward hops report the oldest year reached, forward hops the newest.
        const year = forward ? hop.newest : hop.oldest
        return (
          <div key={index} className={`trace-line ${hop.found ? '' : 'fail'}`}>
            {forward ? '⏩ Traced forward' : '⏳ Traced back'}
            {year ? <> to <b>{year}</b></> : null}
            <em>
              {hop.found
                ? `+${hop.found} paper${hop.found > 1 ? 's' : ''}`
                : hop.error
                  ? 'rate-limited'
                  : forward
                    ? 'nothing newer found'
                    : 'nothing older found'}
            </em>
          </div>
        )
      })}
    </div>
  )
}
