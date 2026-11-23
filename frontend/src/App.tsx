import { lazy, Suspense, useEffect, useState } from 'react'
import { ApiError, fetchSession, logout, type User } from './api'
import LoginPage from './components/LoginPage'
import { isAbortError } from './guards'

// The chart library is the biggest part of the bundle, so the dashboard is
// downloaded only after a successful sign-in.
const Dashboard = lazy(() => import('./components/Dashboard'))

const SESSION_EXPIRED = 'Your session has expired. Please sign in again.'
const SIGN_OUT_FAILED =
  "Couldn't sign out: the server didn't answer. You're still signed in. Try again in a moment."

// checking: GET /auth/session has not answered yet.
// offline: it never answered, so we cannot tell whether anyone is signed in.
type Phase =
  | { readonly kind: 'checking' }
  | { readonly kind: 'offline' }
  | { readonly kind: 'signedOut' }
  | { readonly kind: 'signedIn'; readonly user: User }

const CHECKING: Phase = { kind: 'checking' }
const OFFLINE: Phase = { kind: 'offline' }
const SIGNED_OUT: Phase = { kind: 'signedOut' }

function App() {
  const [phase, setPhase] = useState<Phase>(CHECKING)
  const [notice, setNotice] = useState<string | null>(null)
  const [signOutError, setSignOutError] = useState<string | null>(null)

  // The cookie is invisible to React, so the api says who it belongs to.
  useEffect(() => {
    const controller = new AbortController()
    fetchSession(controller.signal).then(
      (user) => setPhase({ kind: 'signedIn', user }),
      (caught: unknown) => {
        if (isAbortError(caught)) {
          return
        }
        const isSignedOut = caught instanceof ApiError && caught.status === 401
        setPhase(isSignedOut ? SIGNED_OUT : OFFLINE)
      },
    )
    return () => controller.abort()
  }, [])

  const signIn = (user: User): void => {
    setNotice(null)
    setSignOutError(null)
    setPhase({ kind: 'signedIn', user })
  }

  // Only the api can remove the cookie. If it never heard us, the user is
  // still signed in, so the dashboard stays and says so.
  const signOut = async (): Promise<void> => {
    try {
      await logout()
    } catch {
      setSignOutError(SIGN_OUT_FAILED)
      return
    }
    setNotice(null)
    setSignOutError(null)
    setPhase(SIGNED_OUT)
  }

  // The cookie's token expired. The browser drops the cookie itself at the
  // same moment (its Max-Age matches the token), so there is nothing to log out.
  const expire = (): void => {
    setNotice(SESSION_EXPIRED)
    setSignOutError(null)
    setPhase(SIGNED_OUT)
  }

  switch (phase.kind) {
    case 'checking':
      return (
        <div className="app-loading" role="status">
          Checking your sign-in…
        </div>
      )
    case 'offline':
      return (
        <div className="app-loading" role="alert">
          <div className="app-offline">
            <p>Can't reach the server. Reload the page to try again.</p>
            <button className="button-ghost" type="button" onClick={() => window.location.reload()}>
              Reload
            </button>
          </div>
        </div>
      )
    case 'signedOut':
      return <LoginPage notice={notice} onSignIn={signIn} />
    case 'signedIn':
      return (
        <Suspense fallback={<div className="app-loading" role="status">Loading the dashboard…</div>}>
          <Dashboard
            user={phase.user}
            signOutError={signOutError}
            onSignOut={signOut}
            onExpired={expire}
          />
        </Suspense>
      )
  }
}

export default App
