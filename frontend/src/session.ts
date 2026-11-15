import { finiteNumber, isRecord, isString } from './guards'

// Who is signed in. Kept in sessionStorage: it survives a page refresh, is
// gone when the tab closes, and other tabs never see it.
export interface Session {
  readonly token: string
  readonly email: string
  readonly role: string
}

const STORAGE_KEY = 'market-data.session'

// A JWT is three base64url parts; the middle one is JSON with "exp" in
// seconds. Read only to skip a stored token that already expired; the api
// still checks the signature on every request.
function expiresAt(token: string): number | null {
  const payload = token.split('.')[1]
  if (payload === undefined) {
    return null
  }

  try {
    const base64 = payload.replace(/-/g, '+').replace(/_/g, '/')
    const claims: unknown = JSON.parse(atob(base64))
    return isRecord(claims) ? finiteNumber(claims.exp) : null
  } catch {
    return null
  }
}

function isUsable(value: unknown): value is Session {
  if (
    !isRecord(value) ||
    !isString(value.token) ||
    !isString(value.email) ||
    !isString(value.role)
  ) {
    return false
  }

  const expiry = expiresAt(value.token)
  return expiry === null || expiry * 1000 > Date.now()
}

// Storage can throw (private mode, blocked site data). Then the session simply
// lasts until the next refresh, so each failure below is a "no session".
export function loadSession(): Session | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    const value: unknown = raw === null ? null : JSON.parse(raw)
    return isUsable(value) ? value : null
  } catch {
    return null
  }
}

export function saveSession(session: Session): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session))
  } catch {
    // Not stored: the user signs in again after a refresh.
  }
}

export function clearSession(): void {
  try {
    sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    // Nothing was stored, so nothing is left behind.
  }
}
