import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { ApiError } from '../api/client'
import { useAuth } from '../auth/useAuth'
import { AuthLayout } from '../components/AuthLayout'

export function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [displayName, setDisplayName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    if (password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }
    setSubmitting(true)
    try {
      await register(email, password, displayName)
      navigate('/')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthLayout title="Create account" subtitle="Track every dart you throw">
      <form onSubmit={handleSubmit} className="space-y-4">
        <label className="block">
          <span className="label">Display name</span>
          <input
            required
            maxLength={100}
            autoComplete="nickname"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className="input"
          />
        </label>
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
          <span className="label">
            Password <span className="font-normal normal-case tracking-normal text-ink-500">(8+ characters)</span>
          </span>
          <input
            type="password"
            required
            minLength={8}
            autoComplete="new-password"
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
          {submitting ? 'Creating…' : 'Create account'}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-ink-400">
        Already registered?{' '}
        <Link to="/login" className="font-medium text-felt-400 hover:underline">
          Sign in
        </Link>
      </p>
    </AuthLayout>
  )
}
