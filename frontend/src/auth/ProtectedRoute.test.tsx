import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from './AuthContext'
import { ProtectedRoute } from './ProtectedRoute'

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<p>login screen</p>} />
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<p>secret dashboard</p>} />
          </Route>
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('ProtectedRoute', () => {
  it('redirects a signed-out visitor to the login page', () => {
    renderAt('/')
    expect(screen.getByText('login screen')).toBeInTheDocument()
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
    expect(await screen.findByText('login screen')).toBeInTheDocument()
    // The dead token must also have been cleared from storage
    expect(localStorage.getItem('dartmetrics_token')).toBeNull()
  })
})
