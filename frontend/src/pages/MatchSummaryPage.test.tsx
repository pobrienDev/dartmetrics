import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { MatchSummary } from '../api/types'
import { AuthProvider } from '../auth/AuthContext'
import { MatchSummaryPage } from './MatchSummaryPage'

const ME = '00000000-0000-0000-0000-000000000001'
const RIVAL = '00000000-0000-0000-0000-000000000002'

const SUMMARY: MatchSummary = {
  id: 'match-1',
  game_type: 'x01',
  status: 'completed',
  best_of_legs: 3,
  winner_player_id: ME,
  started_at: '2026-09-09T20:00:00Z',
  completed_at: '2026-09-09T20:20:00Z',
  players: [
    {
      player_id: ME, display_name: 'Pat', legs_won: 2, darts_thrown: 33, points_scored: 1002,
      three_dart_average: 91.1, highest_visit: 180, count_100_plus: 3, count_140_plus: 1, count_180: 1,
      checkout_attempts: 4, checkout_successes: 2, checkout_percentage: 50.0,
    },
    {
      player_id: RIVAL, display_name: 'Rival', legs_won: 1, darts_thrown: 36, points_scored: 1000,
      three_dart_average: 83.3, highest_visit: 140, count_100_plus: 2, count_140_plus: 1, count_180: 0,
      checkout_attempts: 3, checkout_successes: 1, checkout_percentage: 33.3,
    },
  ],
  legs: [
    { leg_number: 1, status: 'completed', starting_player_id: ME, winner_player_id: ME, darts_thrown: { [ME]: 15, [RIVAL]: 12 } },
    { leg_number: 2, status: 'completed', starting_player_id: RIVAL, winner_player_id: RIVAL, darts_thrown: { [ME]: 9, [RIVAL]: 12 } },
    { leg_number: 3, status: 'completed', starting_player_id: ME, winner_player_id: ME, darts_thrown: { [ME]: 9, [RIVAL]: 12 } },
  ],
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('MatchSummaryPage', () => {
  it('shows the scoreline, the winner, per-player numbers and every leg', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) =>
        Promise.resolve(
          url === '/api/v1/matches/match-1/summary'
            ? { ok: true, status: 200, json: () => Promise.resolve(SUMMARY) }
            : { ok: false, status: 404, json: () => Promise.resolve({ error: { code: 'NOT_FOUND', message: url } }) },
        ),
      ),
    )
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter initialEntries={['/matches/match-1/summary']}>
          <AuthProvider>
            <Routes>
              <Route path="/matches/:matchId/summary" element={<MatchSummaryPage />} />
            </Routes>
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    )

    expect(await screen.findByText(/Pat wins the match/)).toBeInTheDocument()
    expect(screen.getByText('91.1')).toBeInTheDocument()
    expect(screen.getByText('83.3')).toBeInTheDocument()
    expect(screen.getByText('50% (2/4)')).toBeInTheDocument()
    expect(screen.getByText('Leg 3')).toBeInTheDocument()
    expect(screen.getAllByText('Pat', { selector: 'span.text-felt-300' })).toHaveLength(2)
    expect(screen.getByText('15 · 12 darts')).toBeInTheDocument()
    expect(screen.getAllByText('9 · 12 darts')).toHaveLength(2)
  })
})
