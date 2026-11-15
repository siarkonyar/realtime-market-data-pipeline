import { useState } from 'react'
import type { Session } from '../session'
import { EMPTY_SYMBOL, useMarketData } from '../useMarketData'
import CandleChart from './CandleChart'
import SymbolHeader from './SymbolHeader'
import TopBar from './TopBar'
import Watchlist from './Watchlist'

const SESSION_EXPIRED = 'Your session has expired. Please sign in again.'

interface DashboardProps {
  readonly session: Session
  // null: the user chose to sign out, so no message on the login page.
  readonly onSignOut: (notice: string | null) => void
}

function Dashboard({ session, onSignOut }: DashboardProps) {
  const { symbols, market, error } = useMarketData(session.token, () =>
    onSignOut(SESSION_EXPIRED),
  )
  const [selected, setSelected] = useState<string | null>(null)

  // Until the user picks one, show the first followed symbol.
  const active = selected ?? symbols[0] ?? null
  const activeState = active === null ? EMPTY_SYMBOL : (market[active] ?? EMPTY_SYMBOL)
  const statuses = symbols.map((symbol) => (market[symbol] ?? EMPTY_SYMBOL).status)

  return (
    <div className="dashboard">
      <TopBar session={session} statuses={statuses} onSignOut={() => onSignOut(null)} />

      {error !== null && (
        <p className="banner banner-error" role="alert">
          {error}
        </p>
      )}

      <div className="workspace">
        <Watchlist symbols={symbols} market={market} selected={active} onSelect={setSelected} />

        <main className="detail panel">
          {active === null ? (
            <p className="detail-empty">Loading your symbols…</p>
          ) : (
            <>
              <SymbolHeader symbol={active} state={activeState} />
              <CandleChart symbol={active} candles={activeState.candles} />
            </>
          )}
        </main>
      </div>
    </div>
  )
}

export default Dashboard
