import { useState, type SubmitEvent } from 'react'
import { ApiError, login, register } from '../api'
import type { Session } from '../session'
import Logo from './Logo'

interface LoginPageProps {
  // Shown above the form, e.g. "your session has expired".
  readonly notice: string | null
  readonly onSignIn: (session: Session) => void
}

type Mode = 'signIn' | 'register'

// bcrypt, which the api hashes with, reads at most 72 bytes; the api refuses
// longer passwords. 8 is our own floor for new accounts.
const MIN_NEW_PASSWORD = 8
const MAX_PASSWORD = 72

const TEXT: Readonly<
  Record<Mode, { subtitle: string; button: string; busy: string; switchPrompt: string; switchAction: string }>
> = {
  signIn: {
    subtitle: 'Live prices from the trade stream, minute by minute.',
    button: 'Sign in',
    busy: 'Signing in…',
    switchPrompt: 'No account yet?',
    switchAction: 'Create one',
  },
  register: {
    subtitle: 'Create an account to follow the live prices.',
    button: 'Create account',
    busy: 'Creating account…',
    switchPrompt: 'Already have an account?',
    switchAction: 'Sign in',
  },
}

function errorMessage(error: unknown, mode: Mode): string {
  if (!(error instanceof ApiError)) {
    return 'Something went wrong. Please try again.'
  }
  if (error.status === 401) {
    return 'Wrong email or password.'
  }
  if (error.status === 409) {
    return 'An account with this email already exists. Sign in instead.'
  }
  if (error.status === 422) {
    return mode === 'register'
      ? `Enter a valid email address and a password of up to ${MAX_PASSWORD} characters.`
      : 'Enter a valid email address and a password.'
  }
  return error.status === 0 ? error.message : 'Something went wrong. Please try again.'
}

function LoginPage({ notice, onSignIn }: LoginPageProps) {
  const [mode, setMode] = useState<Mode>('signIn')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const isRegistering = mode === 'register'
  const text = TEXT[mode]

  const switchMode = (): void => {
    setMode(isRegistering ? 'signIn' : 'register')
    setConfirmation('')
    setError(null)
  }

  const handleSubmit = async (event: SubmitEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault()
    if (isRegistering && password !== confirmation) {
      setError('The two passwords do not match.')
      return
    }

    setError(null)
    setIsSubmitting(true)

    // The api trims and lower-cases emails too; doing it here keeps the
    // email shown in the top bar the same as the one stored.
    const cleanEmail = email.trim().toLowerCase()
    try {
      if (isRegistering) {
        await register(cleanEmail, password)
      }
      const result = await login(cleanEmail, password)
      onSignIn({ token: result.token, role: result.role, email: cleanEmail })
    } catch (caught) {
      setError(errorMessage(caught, mode))
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
        <p className="login-subtitle">{text.subtitle}</p>

        <form className="login-form" onSubmit={handleSubmit}>
          {notice !== null && !isRegistering && <p className="banner banner-info">{notice}</p>}

          <label className="field">
            <span className="field-label">Email</span>
            <input
              className="field-input"
              type="email"
              name="email"
              autoComplete={isRegistering ? 'email' : 'username'}
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
              autoComplete={isRegistering ? 'new-password' : 'current-password'}
              required
              minLength={isRegistering ? MIN_NEW_PASSWORD : undefined}
              maxLength={MAX_PASSWORD}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>

          {isRegistering && (
            <label className="field">
              <span className="field-label">Repeat password</span>
              <input
                className="field-input"
                type="password"
                name="confirmation"
                autoComplete="new-password"
                required
                maxLength={MAX_PASSWORD}
                value={confirmation}
                onChange={(event) => setConfirmation(event.target.value)}
              />
            </label>
          )}

          {error !== null && (
            <p className="banner banner-error" role="alert">
              {error}
            </p>
          )}

          <button className="button-primary" type="submit" disabled={isSubmitting}>
            {isSubmitting ? text.busy : text.button}
          </button>
        </form>

        <p className="login-switch">
          {text.switchPrompt}{' '}
          <button className="link-button" type="button" onClick={switchMode} disabled={isSubmitting}>
            {text.switchAction}
          </button>
        </p>
      </div>
    </main>
  )
}

export default LoginPage
