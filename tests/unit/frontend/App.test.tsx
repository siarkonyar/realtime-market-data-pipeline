import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../../../frontend/src/App'

// App asks GET /api/auth/session as soon as it renders, so every test decides
// what that one request answers.
function answerSessionWith(answer: () => Promise<Response>) {
  const fetchMock = vi.fn(answer)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('App', () => {
  it('shows a checking screen while the session is being asked for', () => {
    // Arrange: a request that never answers.
    const fetchMock = answerSessionWith(() => new Promise<Response>(() => {}))

    // Act
    render(<App />)

    // Assert
    expect(screen.getByRole('status')).toHaveTextContent('Checking your sign-in…')
    expect(fetchMock).toHaveBeenCalledWith('/api/auth/session', expect.anything())
  })

  it('shows the login page when there is no session', async () => {
    answerSessionWith(async () =>
      new Response(JSON.stringify({ detail: 'not authenticated' }), { status: 401 }),
    )

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Market data' })).toBeInTheDocument()
  })

  it('asks for a reload when the server does not answer', async () => {
    answerSessionWith(async () => {
      throw new TypeError('Failed to fetch')
    })

    render(<App />)

    expect(await screen.findByRole('alert')).toHaveTextContent("Can't reach the server")
    expect(screen.getByRole('button', { name: 'Reload' })).toBeInTheDocument()
  })
})
