import { directionOf, summarize, type Direction } from '../candles'
import {
  formatChange,
  formatClock,
  formatDayAndMinute,
  formatPercent,
  formatPrice,
  formatVolume,
} from '../format'
import type { LiveStatus } from '../liveSocket'
import type { SymbolState } from '../useMarketData'
import { usePriceTick } from '../usePriceTick'

interface SymbolHeaderProps {
  readonly symbol: string
  readonly state: SymbolState
}

const STATUS_TEXT: Readonly<Record<LiveStatus, string>> = {
  live: 'Live',
  connecting: 'Connecting…',
  reconnecting: 'Reconnecting…',
  unauthorized: 'Signed out',
}

const ARROWS: Readonly<Record<Direction, string>> = { up: '▲', down: '▼', flat: '' }

interface StatProps {
  readonly label: string
  readonly value: string
  readonly tone?: Direction
}

function Stat({ label, value, tone }: StatProps) {
  return (
    <div className="stat">
      <dt>{label}</dt>
      <dd className={tone === undefined ? 'numeric' : `numeric tone-${tone}`}>{value}</dd>
    </div>
  )
}

// When the last change came in: a live tick if there was one this visit,
// otherwise the newest minute from history.
function updatedText(state: SymbolState): string {
  if (state.lastTickAt !== null) {
    return `Updated ${formatClock(state.lastTickAt)}`
  }
  const newest = state.candles.at(-1)
  return newest === undefined ? 'No trades yet' : `Last trade ${formatDayAndMinute(newest.time)}`
}

function SymbolHeader({ symbol, state }: SymbolHeaderProps) {
  const summary = summarize(state.candles)
  const tick = usePriceTick(summary?.last)
  const newest = state.candles.at(-1)
  const dash = '—'

  return (
    <section className="symbol-header" aria-label={`${symbol} price`}>
      <div className="symbol-title">
        <h1>{symbol}</h1>
        <span className="connection">
          <span className={`status-dot status-${state.status}`} />
          {STATUS_TEXT[state.status]}
        </span>
        <span className="symbol-updated">{updatedText(state)}</span>
      </div>

      <div className="symbol-quote">
        {summary === null ? (
          <span className="symbol-price numeric symbol-price-empty">{dash}</span>
        ) : (
          <>
            {/* A new key on every tick restarts the flash animation. */}
            <span key={tick.count} className={`symbol-price numeric flash-${tick.direction}`}>
              {formatPrice(summary.last)}
            </span>
            <span className={`change-chip numeric tone-${summary.direction}`}>
              {ARROWS[summary.direction]} {formatChange(summary.change)} (
              {formatPercent(summary.changeRatio)})
            </span>
            <span className="range-label">over the last 24h</span>
          </>
        )}
      </div>

      <dl className="stats">
        <Stat label="Open" value={summary === null ? dash : formatPrice(summary.open)} />
        <Stat label="High" value={summary === null ? dash : formatPrice(summary.high)} />
        <Stat label="Low" value={summary === null ? dash : formatPrice(summary.low)} />
        <Stat label="Volume" value={summary === null ? dash : formatVolume(summary.volume)} />
        <Stat
          label="This minute"
          value={newest === undefined ? dash : formatChange(newest.close - newest.open)}
          tone={newest === undefined ? 'flat' : directionOf(newest.close - newest.open)}
        />
      </dl>
    </section>
  )
}

export default SymbolHeader
