import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { MatchState, VisitResponse } from '../api/types'
import { LiveScoringPage } from './LiveScoringPage'

const ME = '00000000-0000-0000-0000-000000000001'
const RIVAL = '00000000-0000-0000-0000-000000000002'

function x01State(overrides: Partial<{ mine: number; theirs: number; active: string }> = {}): MatchState {
  const { mine = 501, theirs = 501, active = ME } = overrides
  return {
    id: 'match-1',
    game_type: 'x01',
    status: 'in_progress',
    best_of_legs: 1,
    legs_required_to_win: 1,
    winner_player_id: null,
    current_leg: { id: 'leg-1', leg_number: 1, status: 'in_progress', starting_player_id: ME, winner_player_id: null },
    players: [
      { player_id: ME, display_name: 'Pat', legs_won: 0, remaining_score: mine, marks: null, score: null, round: null, round_target: null, bot_difficulty: null, is_active_turn: active === ME },
      { player_id: RIVAL, display_name: 'Rival', legs_won: 0, remaining_score: theirs, marks: null, score: null, round: null, round_target: null, bot_difficulty: null, is_active_turn: active === RIVAL },
    ],
  }
}

function jsonResponse(body: unknown, status = 200) {
  return { ok: status < 400, status, json: () => Promise.resolve(body) }
}

/** Serve the match state; answer visit posts with `visitReply`. */
function stubApi(initial: MatchState, visitReply: () => VisitResponse) {
  const posted: unknown[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string, init?: RequestInit) => {
      if (url === '/api/v1/matches/match-1' && (init?.method ?? 'GET') === 'GET') {
        return Promise.resolve(jsonResponse(initial))
      }
      if (url === '/api/v1/matches/match-1/visits' && init?.method === 'POST') {
        posted.push(JSON.parse(String(init.body)))
        return Promise.resolve(jsonResponse(visitReply(), 201))
      }
      return Promise.resolve(jsonResponse({ error: { code: 'NOT_FOUND', message: url } }, 404))
    }),
  )
  return posted
}

function renderPage() {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={['/matches/match-1']}>
        <Routes>
          <Route path="/matches/:matchId" element={<LiveScoringPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('LiveScoringPage 501 feedback', () => {
  it('shows the running score and a checkout hint while darts are entered', async () => {
    stubApi(x01State({ mine: 170 }), () => {
      throw new Error('no visit expected')
    })
    renderPage()
    const user = userEvent.setup()

    // 170 with three darts in hand: the classic big fish.
    expect(await screen.findByText('170')).toBeInTheDocument()
    expect(screen.getByText('T20 T20 Bull')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'triple' }))
    await user.click(screen.getByRole('button', { name: '20' }))

    // The card now shows 110 live, and the hint fits the two darts left.
    expect(screen.getByText('110')).toBeInTheDocument()
    expect(screen.getByText('T20 Bull')).toBeInTheDocument()
    expect(screen.getByText('T20', { selector: 'span.font-mono' })).toBeInTheDocument()
  })

  it('shakes the card and names the bust when the server rejects the visit', async () => {
    const posted = stubApi(x01State({ mine: 40 }), () => ({
      turn: {
        id: 'turn-1',
        player_id: ME,
        turn_number: 1,
        turn_start_score: 40,
        turn_end_score: 40,
        points_scored: 0,
        is_bust: true,
        is_checkout: false,
      },
      state: x01State({ mine: 40, active: RIVAL }),
    }))
    renderPage()
    const user = userEvent.setup()

    await screen.findByText('40')
    // 20 + 20 leaves 0 without a double: the UI submits, the server busts it.
    await user.click(screen.getByRole('button', { name: '20' }))
    await user.click(screen.getByRole('button', { name: '20' }))

    expect(await screen.findByRole('status')).toHaveTextContent(/bust/i)
    expect(posted).toHaveLength(1)
    // The scoreboard card comes before the same name in Recent visits.
    const card = screen.getAllByText('Pat')[0].closest('div.rounded-2xl')
    expect(card?.className).toContain('animate-shake')
  })

  it('celebrates a 180', async () => {
    stubApi(x01State(), () => ({
      turn: {
        id: 'turn-1',
        player_id: ME,
        turn_number: 1,
        turn_start_score: 501,
        turn_end_score: 321,
        points_scored: 180,
        is_bust: false,
        is_checkout: false,
      },
      state: x01State({ mine: 321, active: RIVAL }),
    }))
    renderPage()
    const user = userEvent.setup()

    await screen.findAllByText('501')
    await user.click(screen.getByRole('button', { name: 'triple' }))
    for (let i = 0; i < 3; i++) await user.click(screen.getByRole('button', { name: '20' }))

    expect(await screen.findByRole('status')).toHaveTextContent('ONE HUNDRED AND EIGHTY!')
    expect(screen.getByText('321')).toBeInTheDocument()
    expect(screen.getAllByText('Pat')[0].closest('div.rounded-2xl')?.className).toContain('animate-flash-gold')
  })

  it('offers the match summary once the match is over', async () => {
    const done: MatchState = { ...x01State({ mine: 0 }), status: 'completed', winner_player_id: ME, current_leg: null }
    done.players = done.players.map((p) => ({ ...p, is_active_turn: false }))
    stubApi(done, () => {
      throw new Error('no visit expected')
    })
    renderPage()

    expect(await screen.findByText('Pat wins the match!')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'View match summary' })).toHaveAttribute(
      'href',
      '/matches/match-1/summary',
    )
  })
})
