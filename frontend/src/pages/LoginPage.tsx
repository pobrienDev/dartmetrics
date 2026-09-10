import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { ApiError } from '../api/client'
import { useAuth } from '../auth/useAuth'
import { AuthLayout } from '../components/AuthLayout'

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  // Set by ProtectedRoute when a signed-out visitor (or an expired
  // session) lands here from somewhere specific.
  const from = (location.state as { from?: string } | null)?.from
  const returnTo = from && from !== '/' ? from : null
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login(email, password)
      navigate(returnTo ?? '/', { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthLayout
      title="Welcome back"
      subtitle={returnTo ? 'Your session ended. Sign in to pick up where you left off.' : 'Sign in to your account'}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <label className="block">
          <span className="label">Email</span>
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="input"
          />
        </label>
        <label className="block">
          <span className="label">Password</span>
          <input
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="input"
          />
        </label>

        {error && (
          <p role="alert" className="rounded-xl border border-bust-700/60 bg-bust-900/40 px-3 py-2 text-sm text-bust-400">
            {error}
          </p>
        )}

        <button type="submit" disabled={submitting} className="btn-primary w-full px-4 py-3">
          {submitting ? 'Signing in…' : 'Sign in'}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-ink-400">
        No account?{' '}
        <Link to="/register" className="font-medium text-felt-400 hover:underline">
          Register
        </Link>
      </p>
    </AuthLayout>
  )
}
