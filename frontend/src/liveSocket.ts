import { parseCandle, type Candle } from './candles'

export type LiveStatus = 'connecting' | 'live' | 'reconnecting' | 'unauthorized'

export interface LiveHandlers {
  readonly onCandle: (candle: Candle) => void
  readonly onStatus: (status: LiveStatus) => void
}

// The api closes with 1008 when the session cookie is missing, wrong or
// expired: retrying with the same cookie cannot help. 1011 (Redis error), 1013
// (too slow, or Redis restarted) and a plain drop are worth another try.
const CLOSE_NOT_SIGNED_IN = 1008
const CLOSE_NORMAL = 1000

// 1s, 2s, 4s ... up to 30s, so a restarting api is not flooded.
const FIRST_RETRY_MS = 1_000
const MAX_RETRY_MS = 30_000

function socketUrl(symbol: string): string {
  const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const query = new URLSearchParams({ symbol })
  return `${scheme}://${window.location.host}/ws/candles?${query}`
}

function parseMessage(data: unknown): Candle | null {
  if (typeof data !== 'string') {
    return null
  }
  try {
    return parseCandle(JSON.parse(data))
  } catch {
    return null
  }
}

// Random spread (50-100% of the delay), so five sockets that dropped together
// do not all knock again at the same moment.
function retryDelay(attempt: number): number {
  const delay = Math.min(FIRST_RETRY_MS * 2 ** attempt, MAX_RETRY_MS)
  return delay * (0.5 + Math.random() / 2)
}

// Keeps /ws/candles open for one symbol until the returned function is called.
// The browser sends the session cookie with the handshake (it has Path=/), so
// the token never shows up in a URL, a message, or this code.
export function openLiveCandles(symbol: string, handlers: LiveHandlers): () => void {
  let socket: WebSocket | null = null
  let retryTimer: number | undefined
  let attempt = 0
  let isStopped = false

  const scheduleRetry = (): void => {
    handlers.onStatus('reconnecting')
    retryTimer = window.setTimeout(connect, retryDelay(attempt))
    attempt += 1
  }

  function connect(): void {
    const current = new WebSocket(socketUrl(symbol))
    socket = current

    current.addEventListener('open', () => {
      handlers.onStatus('live')
    })

    current.addEventListener('message', (event) => {
      const candle = parseMessage(event.data)
      if (candle !== null) {
        // Only real data resets the wait: an api that accepts and then
        // closes at once still backs off.
        attempt = 0
        handlers.onCandle(candle)
      }
    })

    current.addEventListener('close', (event) => {
      if (isStopped) {
        return
      }
      if (event.code === CLOSE_NOT_SIGNED_IN) {
        handlers.onStatus('unauthorized')
        return
      }
      scheduleRetry()
    })
  }

  handlers.onStatus('connecting')
  connect()

  return () => {
    isStopped = true
    window.clearTimeout(retryTimer)
    socket?.close(CLOSE_NORMAL)
  }
}
