import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../auth/AuthContext'
import { MatchHistoryPage } from './MatchHistoryPage'

const MATCH = {
  id: 'match-1',
  game_type: 'cricket',
  status: 'completed',
  best_of_legs: 3,
  winner_player_id: 'p1',
  created_at: '2026-09-20T18:00:00Z',
  players: [
    { player_id: 'p1', display_name: 'Pat', legs_won: 2 },
    { player_id: 'p2', display_name: 'Guest Gary', legs_won: 1 },
  ],
}

function jsonResponse(body: unknown, status = 200) {
  return { ok: status < 400, status, json: () => Promise.resolve(body) }
}

function stubApi() {
  const urls: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      urls.push(url)
      if (url.startsWith('/api/v1/matches?')) {
        const items = url.includes('status=cancelled') ? [] : [MATCH]
        return Promise.resolve(jsonResponse({ items, total: items.length, limit: 10, offset: 0 }))
      }
      return Promise.resolve(jsonResponse({ error: { code: 'NOT_FOUND', message: url } }, 404))
    }),
  )
  return urls
}

function renderPage() {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>
        <AuthProvider>
          <MatchHistoryPage />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('MatchHistoryPage', () => {
  it('lists matches with the scoreline and links finished ones to the summary', async () => {
    stubApi()
    renderPage()

    expect(await screen.findByText('Guest Gary')).toBeInTheDocument()
    expect(screen.getByText('2–1')).toBeInTheDocument()
    expect(screen.getByText('completed')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /pat.*guest gary/i })).toHaveAttribute('href', '/matches/match-1/summary')
  })

  it('filters by status through the query string', async () => {
    const urls = stubApi()
    renderPage()
    const user = userEvent.setup()

    await screen.findByText('Guest Gary')
    await user.click(screen.getByRole('button', { name: 'Cancelled' }))

    expect(await screen.findByText(/no matches here yet/i)).toBeInTheDocument()
    expect(urls.at(-1)).toBe('/api/v1/matches?limit=10&offset=0&status=cancelled')
  })
})
