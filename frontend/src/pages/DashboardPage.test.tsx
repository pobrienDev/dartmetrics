import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { PlayerStats, UserResponse } from '../api/types'
import { AuthProvider } from '../auth/AuthContext'
import { DashboardPage } from './DashboardPage'

const ME: UserResponse = {
  id: 'user-1',
  email: 'pat@example.com',
  display_name: 'Pat',
  is_active: true,
  created_at: '2026-09-08T00:00:00Z',
  player_id: 'player-1',
}

const STATS: PlayerStats = {
  player_id: 'player-1',
  display_name: 'Pat',
  matches_played: 12,
  matches_won: 7,
  win_percentage: 58.33,
  legs_played: 30,
  legs_won: 16,
  leg_win_percentage: 53.33,
  best_leg_darts: 15,
  total_darts: 900,
  three_dart_average: 61.2,
  first_nine_average: 70.5,
  highest_visit: 140,
  count_100_plus: 20,
  count_140_plus: 3,
  count_180: 1,
  checkout_attempts: 40,
  checkout_successes: 16,
  checkout_percentage: 40,
}

function jsonResponse(body: unknown, status = 200) {
  return { ok: status < 400, status, json: () => Promise.resolve(body) }
}

/** Stub the API. The player list is deliberately empty: on a busy site
 *  the signed-in user is not on its first page, so the dashboard must
 *  not depend on finding itself there. */
function stubApi(me: UserResponse = ME) {
  const urls: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string, init?: RequestInit) => {
      urls.push(`${init?.method ?? 'GET'} ${url}`)
      if (url === '/api/v1/me') return Promise.resolve(jsonResponse(me))
      if (url === '/api/v1/matches?status=in_progress') {
        return Promise.resolve(jsonResponse({ items: [], total: 0, limit: 20, offset: 0 }))
      }
      if (url === '/api/v1/players') return Promise.resolve(jsonResponse([]))
      if (url === '/api/v1/players/player-1/stats') return Promise.resolve(jsonResponse(STATS))
      return Promise.resolve(jsonResponse({ error: { code: 'NOT_FOUND', message: url } }, 404))
    }),
  )
  return urls
}

function renderPage() {
  localStorage.setItem('dartmetrics_token', 'test-token')
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>
        <AuthProvider>
          <DashboardPage />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('DashboardPage', () => {
  it('loads the career KPIs through the player id on /me, not the player list', async () => {
    const urls = stubApi()
    renderPage()

    expect(await screen.findByText('61.2')).toBeInTheDocument()
    expect(screen.getByText('58%')).toBeInTheDocument()
    expect(screen.getByText('900 darts thrown')).toBeInTheDocument()
    expect(screen.queryByText('No darts thrown yet')).not.toBeInTheDocument()
    expect(urls).toContain('GET /api/v1/players/player-1/stats')
    expect(urls).not.toContain('GET /api/v1/players')
  })

  it('nudges a user who has no player profile yet', async () => {
    stubApi({ ...ME, player_id: null })
    renderPage()

    expect(await screen.findByText('No darts thrown yet')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Start a match' })).toHaveAttribute('href', '/matches/new')
  })
})
