import { useState, type SubmitEvent } from 'react'
import { ApiError, login } from '../api'
import type { Session } from '../session'
import Logo from './Logo'

interface LoginPageProps {
  // Shown above the form, e.g. "your session has expired".
  readonly notice: string | null
  readonly onSignIn: (session: Session) => void
}

function loginErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return 'Sign-in failed. Please try again.'
  }
  if (error.status === 401) {
    return 'Wrong email or password.'
  }
  if (error.status === 422) {
    return 'Enter a valid email address and a password.'
  }
  return error.status === 0 ? error.message : 'Sign-in failed. Please try again.'
}

function LoginPage({ notice, onSignIn }: LoginPageProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (event: SubmitEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)

    // The api trims and lower-cases emails too; doing it here keeps the
    // email shown in the top bar the same as the one stored.
    const cleanEmail = email.trim().toLowerCase()
    try {
      const result = await login(cleanEmail, password)
      onSignIn({ token: result.token, role: result.role, email: cleanEmail })
    } catch (caught) {
      setError(loginErrorMessage(caught))
      setIsSubmitting(false)
    }
  }

  return (
    <main className="login">
      <div className="login-card panel">
        <div className="login-brand">
          <Logo />
          <h1>Market data</h1>
        </div>
        <p className="login-subtitle">Live prices from the trade stream, minute by minute.</p>

        <form className="login-form" onSubmit={handleSubmit}>
          {notice !== null && <p className="banner banner-info">{notice}</p>}

          <label className="field">
            <span className="field-label">Email</span>
            <input
              className="field-input"
              type="email"
              name="email"
              autoComplete="username"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>

          <label className="field">
            <span className="field-label">Password</span>
            <input
              className="field-input"
              type="password"
              name="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>

          {error !== null && (
            <p className="banner banner-error" role="alert">
              {error}
            </p>
          )}

          <button className="button-primary" type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </main>
  )
}

export default LoginPage
