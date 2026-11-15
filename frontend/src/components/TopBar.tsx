import type { LiveStatus } from '../liveSocket'
import type { Session } from '../session'
import Logo from './Logo'

interface TopBarProps {
  readonly session: Session
  // One per followed symbol, in the watchlist's order.
  readonly statuses: readonly LiveStatus[]
  readonly onSignOut: () => void
}

type Connection = 'live' | 'connecting' | 'reconnecting'

const CONNECTION_LABELS: Readonly<Record<Connection, string>> = {
  live: 'Live',
  connecting: 'Connecting…',
  reconnecting: 'Reconnecting…',
}

// "Live" only when every symbol's socket is open.
function overallConnection(statuses: readonly LiveStatus[]): Connection {
  if (statuses.length > 0 && statuses.every((status) => status === 'live')) {
    return 'live'
  }
  return statuses.includes('reconnecting') ? 'reconnecting' : 'connecting'
}

function TopBar({ session, statuses, onSignOut }: TopBarProps) {
  const connection = overallConnection(statuses)

  return (
    <header className="topbar">
      <div className="brand">
        <Logo />
        <span>Market data</span>
      </div>

      <div className="topbar-right">
        <span className="connection" role="status">
          <span className={`status-dot status-${connection}`} />
          {CONNECTION_LABELS[connection]}
        </span>
        <span className="user">
          <span className="user-email">{session.email}</span>
          <span className="role">{session.role}</span>
        </span>
        <button className="button-ghost" type="button" onClick={onSignOut}>
          Sign out
        </button>
      </div>
    </header>
  )
}

export default TopBar
