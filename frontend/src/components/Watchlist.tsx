import { summarize } from '../candles'
import { formatPercent, formatPrice } from '../format'
import { EMPTY_SYMBOL, type MarketState, type SymbolState } from '../useMarketData'
import { usePriceTick } from '../usePriceTick'
import Sparkline from './Sparkline'

interface WatchlistProps {
  readonly symbols: readonly string[]
  readonly market: MarketState
  readonly selected: string | null
  readonly onSelect: (symbol: string) => void
}

interface RowProps {
  readonly symbol: string
  readonly state: SymbolState
  readonly isSelected: boolean
  readonly onSelect: (symbol: string) => void
}

function WatchlistRow({ symbol, state, isSelected, onSelect }: RowProps) {
  const summary = summarize(state.candles)
  const tick = usePriceTick(summary?.last)
  const direction = summary?.direction ?? 'flat'

  return (
    <li>
      <button
        className="watchlist-row"
        type="button"
        aria-current={isSelected ? 'true' : undefined}
        onClick={() => onSelect(symbol)}
      >
        <span className="watchlist-symbol">
          <span className={`status-dot status-${state.status}`} title={state.status} />
          {symbol}
        </span>
        <Sparkline candles={state.candles} direction={direction} />
        <span className="watchlist-numbers">
          {/* A new key on every tick restarts the flash animation. */}
          <span key={tick.count} className={`watchlist-price numeric flash-${tick.direction}`}>
            {summary === null ? '—' : formatPrice(summary.last)}
          </span>
          <span className={`watchlist-change numeric tone-${direction}`}>
            {summary === null ? 'no trades' : formatPercent(summary.changeRatio)}
          </span>
        </span>
      </button>
    </li>
  )
}

function Watchlist({ symbols, market, selected, onSelect }: WatchlistProps) {
  return (
    <nav className="watchlist panel" aria-label="Symbols">
      <div className="panel-title">
        Watchlist <span className="panel-hint">24h</span>
      </div>
      <ul className="watchlist-rows">
        {symbols.length === 0 ? (
          <li className="watchlist-empty">Loading symbols…</li>
        ) : (
          symbols.map((symbol) => (
            <WatchlistRow
              key={symbol}
              symbol={symbol}
              state={market[symbol] ?? EMPTY_SYMBOL}
              isSelected={symbol === selected}
              onSelect={onSelect}
            />
          ))
        )}
      </ul>
    </nav>
  )
}

export default Watchlist
