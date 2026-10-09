import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
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

function halveItState(overrides: Partial<{ mine: number; theirs: number; round: number; active: string }> = {}): MatchState {
  const { mine = 40, theirs = 40, round = 1, active = ME } = overrides
  const base = x01State({ active })
  return {
    ...base,
    game_type: 'halve_it',
    players: base.players.map((p) => ({
      ...p,
      remaining_score: null,
      score: p.player_id === ME ? mine : theirs,
      round,
      round_target: 'outer_black',
    })),
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

function renderPage(queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  return render(
    <QueryClientProvider client={queryClient}>
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

describe('LiveScoringPage Halve It feedback', () => {
  // The server stores every Halve It turn with points_scored 0 (the
  // running total lives in the leg state), so the recent-visits row
  // must be judged from the total before and after the round.
  function halveItTurn() {
    return {
      id: 'turn-1',
      player_id: ME,
      turn_number: 1,
      turn_start_score: 0,
      turn_end_score: 0,
      points_scored: 0,
      is_bust: false,
      is_checkout: false,
    }
  }

  it('shows +N when the round added points', async () => {
    stubApi(halveItState({ mine: 40 }), () => ({
      turn: halveItTurn(),
      state: halveItState({ mine: 100, round: 2, active: RIVAL }),
    }))
    renderPage()
    const user = userEvent.setup()

    await screen.findAllByText('40')
    for (let i = 0; i < 3; i++) await user.click(screen.getByRole('button', { name: '20' }))

    expect(await screen.findByRole('status')).toHaveTextContent('You: +60')
    const row = screen.getByText('Recent visits').parentElement!
    expect(row).toHaveTextContent('+60')
    expect(row).toHaveTextContent('(40 → 100)')
    expect(row).not.toHaveTextContent('HALVED')
  })

  it('shows HALVED only when the total actually halved', async () => {
    stubApi(halveItState({ mine: 40 }), () => ({
      turn: halveItTurn(),
      state: halveItState({ mine: 20, round: 2, active: RIVAL }),
    }))
    renderPage()
    const user = userEvent.setup()

    await screen.findAllByText('40')
    for (let i = 0; i < 3; i++) await user.click(screen.getByRole('button', { name: '1' }))

    expect(await screen.findByRole('status')).toHaveTextContent('You: halved! 40 → 20')
    const row = screen.getByText('Recent visits').parentElement!
    expect(row).toHaveTextContent('HALVED')
    expect(row).toHaveTextContent('(40 → 20)')
    expect(row).not.toHaveTextContent('+0')
  })
})

describe('LiveScoringPage resync after failures', () => {
  function botState(active = RIVAL): MatchState {
    const base = x01State({ active })
    return {
      ...base,
      players: base.players.map((p) =>
        p.player_id === RIVAL ? { ...p, display_name: 'Pro Bot', bot_difficulty: 'pro' } : p,
      ),
    }
  }

  /** Route by URL; count the GETs of the match and let a test script the bot replies. */
  function stubRoutes(initial: MatchState, botReplies: Array<() => { body: unknown; status: number }>) {
    const calls = { matchGets: 0, botPosts: 0, visitPosts: 0 }
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string, init?: RequestInit) => {
        const method = init?.method ?? 'GET'
        if (url === '/api/v1/matches/match-1' && method === 'GET') {
          calls.matchGets += 1
          return Promise.resolve(jsonResponse(initial))
        }
        if (url === '/api/v1/matches/match-1/visits' && method === 'POST') {
          calls.visitPosts += 1
          return Promise.resolve(
            jsonResponse({ error: { code: 'NOT_PLAYER_TURN', message: 'It is not your turn.' } }, 409),
          )
        }
        if (url === '/api/v1/matches/match-1/bot-visit' && method === 'POST') {
          const reply = botReplies[Math.min(calls.botPosts, botReplies.length - 1)]()
          calls.botPosts += 1
          return Promise.resolve(jsonResponse(reply.body, reply.status))
        }
        return Promise.resolve(jsonResponse({ error: { code: 'NOT_FOUND', message: url } }, 404))
      }),
    )
    return calls
  }

  it('refetches the match when a visit is rejected', async () => {
    const calls = stubRoutes(x01State({ mine: 40 }), [])
    renderPage()
    const user = userEvent.setup()

    await screen.findByText('40')
    expect(calls.matchGets).toBe(1)
    await user.click(screen.getByRole('button', { name: '20' }))
    await user.click(screen.getByRole('button', { name: '20' }))

    expect(await screen.findByRole('status')).toHaveTextContent('It is not your turn.')
    await waitFor(() => expect(calls.matchGets).toBe(2))
    expect(calls.visitPosts).toBe(1)
  })

  it('offers a retry when the bot cannot throw, instead of waiting forever', async () => {
    const calls = stubRoutes(botState(), [
      () => ({ body: { error: { code: 'INTERNAL', message: 'boom' } }, status: 500 }),
      () => ({
        body: {
          turn: { id: 'turn-2', player_id: RIVAL, turn_number: 1, turn_start_score: 501, turn_end_score: 441, points_scored: 60, is_bust: false, is_checkout: false },
          state: x01State({ theirs: 441, active: ME }),
          darts: [{ segment: 20, multiplier: 'single' }, { segment: 20, multiplier: 'single' }, { segment: 20, multiplier: 'single' }],
        },
        status: 201,
      }),
    ])
    renderPage()
    const user = userEvent.setup()

    // The bot throws after its 1.2 s beat and fails; the page resyncs and offers a retry.
    const retry = await screen.findByRole('button', { name: 'Try again' }, { timeout: 4000 })
    expect(calls.botPosts).toBe(1)
    await waitFor(() => expect(calls.matchGets).toBe(2))
    // Two live regions here: the banner and the bot's own line.
    expect(screen.getAllByRole('status').map((el) => el.textContent).join(' ')).toContain('boom')

    await user.click(retry)
    await waitFor(() => expect(calls.botPosts).toBe(2), { timeout: 4000 })
    expect(await screen.findByText('441')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
  })
})

describe('LiveScoringPage abandon', () => {
  it('abandons the match after a confirmation and refreshes the match lists', async () => {
    const abandoned: MatchState = { ...x01State(), status: 'cancelled', current_leg: null }
    abandoned.players = abandoned.players.map((p) => ({ ...p, is_active_turn: false }))
    const posted: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string, init?: RequestInit) => {
        const method = init?.method ?? 'GET'
        if (url === '/api/v1/matches/match-1' && method === 'GET') return Promise.resolve(jsonResponse(x01State()))
        if (url === '/api/v1/matches/match-1/abandon' && method === 'POST') {
          posted.push(url)
          return Promise.resolve(jsonResponse(abandoned))
        }
        return Promise.resolve(jsonResponse({ error: { code: 'NOT_FOUND', message: url } }, 404))
      }),
    )
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    // The dashboard's resume list, cached from an earlier visit.
    queryClient.setQueryData(['matches', 'in_progress'], { items: [{ id: 'match-1' }], total: 1, limit: 20, offset: 0 })
    renderPage(queryClient)
    const user = userEvent.setup()

    await screen.findAllByText('501')
    await user.click(screen.getByRole('button', { name: 'Abandon match' }))
    // Nothing is sent until the confirmation.
    expect(posted).toHaveLength(0)
    expect(screen.getByRole('alertdialog')).toHaveTextContent('without a winner')

    await user.click(screen.getByRole('button', { name: 'Keep playing' }))
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Abandon match' }))
    await user.click(screen.getByRole('button', { name: 'Yes, abandon' }))

    expect(await screen.findByText('Match ended.')).toBeInTheDocument()
    expect(posted).toEqual(['/api/v1/matches/match-1/abandon'])
    expect(screen.queryByRole('button', { name: 'Abandon match' })).not.toBeInTheDocument()
    expect(queryClient.getQueryState(['matches', 'in_progress'])?.isInvalidated).toBe(true)
  })
})

describe('LiveScoringPage Cricket, bot turn and undo', () => {
  function cricketState(marks: Record<string, number>, active = ME): MatchState {
    const base = x01State({ active })
    return {
      ...base,
      game_type: 'cricket',
      players: base.players.map((p) => ({
        ...p,
        remaining_score: null,
        marks: p.player_id === ME ? marks : { '20': 0, '19': 0, '18': 0, '17': 0, '16': 0, '15': 0, '25': 0 },
      })),
    }
  }

  it('shows the marks grid and submits a Cricket visit', async () => {
    const posted = stubApi(cricketState({ '20': 1, '19': 0, '18': 0, '17': 0, '16': 0, '15': 0, '25': 0 }), () => ({
      turn: { id: 'turn-1', player_id: ME, turn_number: 1, turn_start_score: 0, turn_end_score: 0, points_scored: 0, is_bust: false, is_checkout: false },
      state: cricketState({ '20': 3, '19': 1, '18': 0, '17': 0, '16': 0, '15': 0, '25': 0 }, RIVAL),
    }))
    renderPage()
    const user = userEvent.setup()

    // Every Cricket target has a column; 20 already carries one mark.
    await screen.findAllByText('Bull')
    expect(screen.getAllByText('╱')).toHaveLength(1)

    await user.click(screen.getByRole('button', { name: 'double' }))
    await user.click(screen.getByRole('button', { name: '20' }))
    await user.click(screen.getByRole('button', { name: 'single' }))
    await user.click(screen.getByRole('button', { name: '19' }))
    await user.click(screen.getByRole('button', { name: '19' }))

    await waitFor(() => expect(posted).toHaveLength(1))
    expect(posted[0]).toMatchObject({
      player_id: ME,
      darts: [
        { segment: 20, multiplier: 'double' },
        { segment: 19, multiplier: 'single' },
        { segment: 19, multiplier: 'single' },
      ],
    })
    // The closed 20 shows as a full mark from the server's state.
    expect(await screen.findByText('◎')).toBeInTheDocument()
  })

  it('asks the server to throw for the bot after a beat, then hands the turn back', async () => {
    const botState = x01State({ active: RIVAL })
    botState.players = botState.players.map((p) =>
      p.player_id === RIVAL ? { ...p, display_name: 'Medium Bot', bot_difficulty: 'medium' } : p,
    )
    const botPosts: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string, init?: RequestInit) => {
        const method = init?.method ?? 'GET'
        if (url === '/api/v1/matches/match-1' && method === 'GET') return Promise.resolve(jsonResponse(botState))
        if (url === '/api/v1/matches/match-1/bot-visit' && method === 'POST') {
          botPosts.push(url)
          return Promise.resolve(
            jsonResponse(
              {
                turn: { id: 'turn-1', player_id: RIVAL, turn_number: 1, turn_start_score: 501, turn_end_score: 416, points_scored: 85, is_bust: false, is_checkout: false },
                state: x01State({ theirs: 416, active: ME }),
                darts: [{ segment: 20, multiplier: 'triple' }, { segment: 5, multiplier: 'single' }, { segment: 20, multiplier: 'single' }],
              },
              201,
            ),
          )
        }
        return Promise.resolve(jsonResponse({ error: { code: 'NOT_FOUND', message: url } }, 404))
      }),
    )
    renderPage()

    expect(await screen.findByRole('status')).toHaveTextContent('Medium is stepping up…')
    expect(screen.queryByRole('button', { name: '20' })).not.toBeInTheDocument() // no pad while the bot is up
    expect(botPosts).toHaveLength(0)

    // After BOT_THROW_DELAY_MS the visit is requested and the board updates.
    expect(await screen.findByText('416', {}, { timeout: 4000 })).toBeInTheDocument()
    expect(botPosts).toHaveLength(1)
    expect(screen.getByRole('button', { name: '20' })).toBeInTheDocument()
    expect(screen.getByText('Recent visits').parentElement).toHaveTextContent('T20 5 20')
  })

  it('undoes the last visit and drops it from recent visits', async () => {
    const deletes: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string, init?: RequestInit) => {
        const method = init?.method ?? 'GET'
        if (url === '/api/v1/matches/match-1' && method === 'GET') return Promise.resolve(jsonResponse(x01State()))
        if (url === '/api/v1/matches/match-1/visits' && method === 'POST') {
          return Promise.resolve(
            jsonResponse(
              {
                turn: { id: 'turn-1', player_id: ME, turn_number: 1, turn_start_score: 501, turn_end_score: 441, points_scored: 60, is_bust: false, is_checkout: false },
                state: x01State({ mine: 441, active: RIVAL }),
              },
              201,
            ),
          )
        }
        if (url === '/api/v1/matches/match-1/visits/latest' && method === 'DELETE') {
          deletes.push(url)
          return Promise.resolve(jsonResponse(x01State()))
        }
        return Promise.resolve(jsonResponse({ error: { code: 'NOT_FOUND', message: url } }, 404))
      }),
    )
    renderPage()
    const user = userEvent.setup()

    await screen.findAllByText('501')
    for (let i = 0; i < 3; i++) await user.click(screen.getByRole('button', { name: '20' }))
    expect(await screen.findByText('441')).toBeInTheDocument()
    expect(screen.getByText('Recent visits')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Undo visit' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Last visit undone.')
    expect(deletes).toEqual(['/api/v1/matches/match-1/visits/latest'])
    // Both cards back on 501 (the third match is the game chip in the header).
    expect(screen.getAllByText('501')).toHaveLength(3)
    expect(screen.queryByText('Recent visits')).not.toBeInTheDocument()
  })
})
