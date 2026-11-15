import { parseCandle, type Candle } from './candles'
import { isAbortError, isRecord, isString } from './guards'

// Every call starts with /api. nginx (Docker) or the Vite dev proxy passes it
// on to the api with the /api cut off, so the page needs no api address.
const API_PREFIX = '/api'

// The most GET /candles allows.
const HISTORY_HOURS = 24

// status 0: the server never answered, or answered with something unusable.
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export interface LoginResult {
  readonly token: string
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
  return response.json() as Promise<unknown>
}

function withToken(token: string, signal: AbortSignal): RequestInit {
  return { headers: { Authorization: `Bearer ${token}` }, signal }
}

function unexpected(what: string): ApiError {
  return new ApiError(0, `Unexpected ${what} from the server`)
}

export async function login(email: string, password: string): Promise<LoginResult> {
  const body = await request('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })

  if (!isRecord(body) || !isString(body.access_token) || !isString(body.role)) {
    throw unexpected('login answer')
  }
  return { token: body.access_token, role: body.role }
}

export async function fetchSymbols(
  token: string,
  signal: AbortSignal,
): Promise<readonly string[]> {
  const body = await request('/symbols', withToken(token, signal))
  if (!Array.isArray(body) || !body.every(isString)) {
    throw unexpected('symbol list')
  }
  return body
}

export async function fetchCandles(
  symbol: string,
  token: string,
  signal: AbortSignal,
): Promise<readonly Candle[]> {
  const query = new URLSearchParams({ symbol, hours: String(HISTORY_HOURS) })
  const body = await request(`/candles?${query}`, withToken(token, signal))
  if (!Array.isArray(body)) {
    throw unexpected('candle list')
  }
  return body.map(parseCandle).filter((candle): candle is Candle => candle !== null)
}
