import { useState } from 'react'
import type { User } from '../api'
import { EMPTY_SYMBOL, useMarketData } from '../useMarketData'
import CandleChart from './CandleChart'
import SymbolHeader from './SymbolHeader'
import TopBar from './TopBar'
import Watchlist from './Watchlist'

interface DashboardProps {
  readonly user: User
  // Set when sign-out never reached the server: the user is still signed in.
  readonly signOutError: string | null
  readonly onSignOut: () => void
  // The api answered 401: the session cookie has expired.
  readonly onExpired: () => void
}

function Dashboard({ user, signOutError, onSignOut, onExpired }: DashboardProps) {
  const { symbols, market, error } = useMarketData(onExpired)
  const [selected, setSelected] = useState<string | null>(null)

  // Until the user picks one, show the first followed symbol.
  const active = selected ?? symbols[0] ?? null
  const activeState = active === null ? EMPTY_SYMBOL : (market[active] ?? EMPTY_SYMBOL)
  const statuses = symbols.map((symbol) => (market[symbol] ?? EMPTY_SYMBOL).status)

  return (
    <div className="dashboard">
      <TopBar user={user} statuses={statuses} onSignOut={onSignOut} />

      {signOutError !== null && (
        <p className="banner banner-error" role="alert">
          {signOutError}
        </p>
      )}

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
