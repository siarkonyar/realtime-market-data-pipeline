import { describe, expect, it } from 'vitest'
import { devProxy } from './vite.config'

// `npm run dev` must send requests to the api the same way nginx does in
// the container, or code that works in one place breaks in the other.
describe('dev proxy', () => {
  it('sends /api requests to the api on port 8000', () => {
    expect(devProxy['/api'].target).toBe('http://localhost:8000')
  })

  it('strips /api, so the api gets its own path', () => {
    expect(devProxy['/api'].rewrite('/api/candles?symbol=NVDA&hours=1')).toBe(
      '/candles?symbol=NVDA&hours=1',
    )
  })

  it('keeps the rest of a longer path', () => {
    expect(devProxy['/api'].rewrite('/api/auth/login')).toBe('/auth/login')
  })

  it('sends /ws to the api as a WebSocket and keeps the /ws prefix', () => {
    expect(devProxy['/ws']).toEqual({ target: 'ws://localhost:8000', ws: true })
  })
})
