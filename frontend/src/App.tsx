import { lazy, Suspense, useState } from 'react'
import LoginPage from './components/LoginPage'
import { clearSession, loadSession, saveSession, type Session } from './session'

// The chart library is the biggest part of the bundle, so the dashboard is
// downloaded only after a successful sign-in.
const Dashboard = lazy(() => import('./components/Dashboard'))

function App() {
  const [session, setSession] = useState<Session | null>(loadSession)
  const [notice, setNotice] = useState<string | null>(null)

  const signIn = (next: Session): void => {
    saveSession(next)
    setNotice(null)
    setSession(next)
  }

  const signOut = (message: string | null): void => {
    clearSession()
    setNotice(message)
    setSession(null)
  }

  if (session === null) {
    return <LoginPage notice={notice} onSignIn={signIn} />
  }

  return (
    <Suspense fallback={<div className="app-loading" role="status">Loading the dashboard…</div>}>
      <Dashboard session={session} onSignOut={signOut} />
    </Suspense>
  )
}

export default App
