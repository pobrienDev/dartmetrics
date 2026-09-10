import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../auth/AuthContext'
import { LoginPage } from './LoginPage'

function renderLogin() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <LoginPage />
      </AuthProvider>
    </MemoryRouter>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('LoginPage', () => {
  it('renders email, password and submit controls', () => {
    renderLogin()
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
  })

  it('shows the backend error message when login fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: () =>
          Promise.resolve({
            error: {
              code: 'INVALID_CREDENTIALS',
              message: 'Incorrect email or password.',
            },
          }),
      }),
    )

    renderLogin()
    const user = userEvent.setup()
    await user.type(screen.getByLabelText(/email/i), 'pat@example.com')
    await user.type(screen.getByLabelText(/password/i), 'wrong-password')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Incorrect email or password.',
    )
  })
})

describe('LoginPage after a session expired mid-match', () => {
  it('explains, then returns to the remembered page after signing in', async () => {
    const me = {
      id: '00000000-0000-0000-0000-000000000001',
      email: 'pat@example.com',
      display_name: 'Patrick',
      is_active: true,
      created_at: '2026-08-26T00:00:00Z',
    }
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: () =>
            Promise.resolve(
              url === '/api/v1/auth/login' ? { access_token: 't', token_type: 'bearer' } : me,
            ),
        }),
      ),
    )
    render(
      <MemoryRouter initialEntries={[{ pathname: '/login', state: { from: '/matches/abc' } }]}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/matches/abc" element={<p>back in the match</p>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    )
    expect(screen.getByText(/pick up where you left off/i)).toBeInTheDocument()

    const user = userEvent.setup()
    await user.type(screen.getByLabelText(/email/i), 'pat@example.com')
    await user.type(screen.getByLabelText(/password/i), 'correct-horse-battery')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    expect(await screen.findByText('back in the match')).toBeInTheDocument()
  })
})
