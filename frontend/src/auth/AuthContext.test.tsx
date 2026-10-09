import { act, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { SESSION_EXPIRED_EVENT } from '../api/client'
import { AuthProvider } from './AuthContext'
import { useAuth } from './useAuth'

function Probe() {
  const { user, logout } = useAuth()
  return (
    <>
      <p>{user ? `signed in as ${user.display_name}` : 'signed out'}</p>
      <button onClick={logout}>Sign out</button>
    </>
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('AuthProvider sign-out hook', () => {
  it('runs onSignOut on logout and on session expiry, so the app can clear its cache', async () => {
    localStorage.setItem('dartmetrics_token', 'stored-token')
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve({
            id: 'user-1',
            email: 'pat@example.com',
            display_name: 'Pat',
            is_active: true,
            created_at: '2026-08-26T00:00:00Z',
            player_id: null,
          }),
      }),
    )
    const onSignOut = vi.fn()
    render(
      <AuthProvider onSignOut={onSignOut}>
        <Probe />
      </AuthProvider>,
    )
    expect(await screen.findByText('signed in as Pat')).toBeInTheDocument()

    await act(async () => {
      screen.getByRole('button', { name: 'Sign out' }).click()
    })
    expect(screen.getByText('signed out')).toBeInTheDocument()
    expect(localStorage.getItem('dartmetrics_token')).toBeNull()
    expect(onSignOut).toHaveBeenCalledTimes(1)

    await act(async () => {
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT))
    })
    expect(onSignOut).toHaveBeenCalledTimes(2)
  })
})
