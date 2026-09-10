import { act, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api, SESSION_EXPIRED_EVENT } from '../api/client'
import { AuthProvider } from './AuthContext'
import { ProtectedRoute } from './ProtectedRoute'

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

/** Stand-in login page that reveals where ProtectedRoute wants to return to. */
function LoginProbe() {
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from
  return <p>login screen{from ? ` (from ${from})` : ''}</p>
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginProbe />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<p>secret dashboard</p>} />
            <Route path="/matches/:id" element={<p>live match</p>} />
          </Route>
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('ProtectedRoute', () => {
  it('redirects a signed-out visitor to the login page', () => {
    renderAt('/')
    expect(screen.getByText(/login screen/)).toBeInTheDocument()
    expect(screen.queryByText('secret dashboard')).not.toBeInTheDocument()
  })

  it('renders the protected content once the stored token resolves to a user', async () => {
    localStorage.setItem('dartmetrics_token', 'stored-token')
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve({
            id: '00000000-0000-0000-0000-000000000001',
            email: 'pat@example.com',
            display_name: 'Patrick',
            is_active: true,
            created_at: '2026-08-26T00:00:00Z',
          }),
      }),
    )

    renderAt('/')
    expect(await screen.findByText('secret dashboard')).toBeInTheDocument()
  })

  it('falls back to login when the stored token is rejected', async () => {
    localStorage.setItem('dartmetrics_token', 'expired-token')
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: () =>
          Promise.resolve({
            error: { code: 'NOT_AUTHENTICATED', message: 'Invalid or expired token.' },
          }),
      }),
    )

    renderAt('/')
    expect(await screen.findByText(/login screen/)).toBeInTheDocument()
    // The dead token must also have been cleared from storage
    expect(localStorage.getItem('dartmetrics_token')).toBeNull()
  })
})

describe('ProtectedRoute when the session expires mid-page', () => {
  it('bounces to login remembering the page, once a request comes back 401', async () => {
    localStorage.setItem('dartmetrics_token', 'stored-token')
    const me = {
      id: '00000000-0000-0000-0000-000000000001',
      email: 'pat@example.com',
      display_name: 'Patrick',
      is_active: true,
      created_at: '2026-08-26T00:00:00Z',
    }
    const fetchSpy = vi.fn().mockResolvedValue({ ok: true, status: 200, json: () => Promise.resolve(me) })
    vi.stubGlobal('fetch', fetchSpy)

    renderAt('/matches/abc')
    expect(await screen.findByText('live match')).toBeInTheDocument()

    // An hour later the token is dead: the next API call is rejected.
    fetchSpy.mockResolvedValue({
      ok: false,
      status: 401,
      json: () => Promise.resolve({ error: { code: 'NOT_AUTHENTICATED', message: 'Invalid or expired token.' } }),
    })
    await act(async () => {
      await api('/api/v1/matches/abc/visits', { method: 'POST', body: {} }).catch(() => {})
    })

    expect(await screen.findByText('login screen (from /matches/abc)')).toBeInTheDocument()
    expect(localStorage.getItem('dartmetrics_token')).toBeNull()
  })

  it('reacts to the expiry event directly', async () => {
    localStorage.setItem('dartmetrics_token', 'stored-token')
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve({
            id: '00000000-0000-0000-0000-000000000001',
            email: 'pat@example.com',
            display_name: 'Patrick',
            is_active: true,
            created_at: '2026-08-26T00:00:00Z',
          }),
      }),
    )
    renderAt('/')
    expect(await screen.findByText('secret dashboard')).toBeInTheDocument()
    act(() => {
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT))
    })
    expect(await screen.findByText('login screen (from /)')).toBeInTheDocument()
  })
})
