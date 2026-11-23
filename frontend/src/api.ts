import { parseCandle, type Candle } from './candles'
import { isAbortError, isRecord, isString } from './guards'

// Every call starts with /api. nginx (Docker) or the Vite dev proxy passes it
// on to the api with the /api cut off, so the page needs no api address.
// Same address, so the browser attaches the session cookie to every call on
// its own: no code here ever sees the token.
const API_PREFIX = '/api'

// The most GET /candles allows.
const HISTORY_HOURS = 24

const NO_CONTENT = 204

// status 0: the server never answered, or answered with something unusable.
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

// Who the session cookie belongs to. React cannot read the cookie itself, so
// this always comes from the api.
export interface User {
  readonly email: string
  readonly role: string
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (isRecord(body) && isString(body.detail)) {
      return body.detail
    }
  } catch {
    // Not JSON (an nginx error page, say): the status line below says enough.
  }
  return `Request failed (${response.status})`
}

async function request(path: string, init: RequestInit): Promise<unknown> {
  let response: Response
  try {
    response = await fetch(`${API_PREFIX}${path}`, init)
  } catch (error) {
    if (isAbortError(error)) {
      throw error
    }
    throw new ApiError(0, 'Cannot reach the server. Is the api running?')
  }

  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response))
  }
  // 204 has no body, and reading an empty body as JSON throws.
  if (response.status === NO_CONTENT) {
    return null
  }
  return response.json() as Promise<unknown>
}

function unexpected(what: string): ApiError {
  return new ApiError(0, `Unexpected ${what} from the server`)
}

function parseUser(body: unknown, what: string): User {
  if (!isRecord(body) || !isString(body.email) || !isString(body.role)) {
    throw unexpected(what)
  }
  return { email: body.email, role: body.role }
}

// The api answers with the user and sets the session cookie in the same reply.
export async function login(email: string, password: string): Promise<User> {
  const body = await request('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  return parseUser(body, 'login answer')
}

// A new account always gets the "user" role. The answer sets no cookie, so
// the caller signs in afterwards.
export async function register(email: string, password: string): Promise<void> {
  await request('/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
}

// Asked once when the page loads. 401 means no cookie, or an expired one.
export async function fetchSession(signal: AbortSignal): Promise<User> {
  const body = await request('/auth/session', { signal })
  return parseUser(body, 'session answer')
}

// Only the api can remove an httpOnly cookie. If this throws, the cookie is
// still in the browser and the user is still signed in.
export async function logout(): Promise<void> {
  await request('/auth/logout', { method: 'POST' })
}

export async function fetchSymbols(signal: AbortSignal): Promise<readonly string[]> {
  const body = await request('/symbols', { signal })
  if (!Array.isArray(body) || !body.every(isString)) {
    throw unexpected('symbol list')
  }
  return body
}

export async function fetchCandles(
  symbol: string,
  signal: AbortSignal,
): Promise<readonly Candle[]> {
  const query = new URLSearchParams({ symbol, hours: String(HISTORY_HOURS) })
  const body = await request(`/candles?${query}`, { signal })
  if (!Array.isArray(body)) {
    throw unexpected('candle list')
  }
  return body.map(parseCandle).filter((candle): candle is Candle => candle !== null)
}
