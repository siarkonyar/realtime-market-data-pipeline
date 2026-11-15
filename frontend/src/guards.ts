// Checks for data that comes from outside (the network, sessionStorage).
// TypeScript types vanish at runtime, so these do the checking for real.

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

export function isString(value: unknown): value is string {
  return typeof value === 'string'
}

export function finiteNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}
