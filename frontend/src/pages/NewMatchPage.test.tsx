import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../auth/AuthContext'
import { NewMatchPage } from './NewMatchPage'

const BOTS = ['noob', 'easy', 'medium', 'hard', 'pro'].map((difficulty) => ({
  id: `bot-${difficulty}`,
  user_id: null,
  display_name: `${difficulty} Bot`,
  nickname: null,
  is_active: true,
  bot_difficulty: difficulty,
  created_at: '2026-09-08T00:00:00Z',
}))

function jsonResponse(body: unknown, status = 200) {
  return { ok: status < 400, status, json: () => Promise.resolve(body) }
}

/** A fetch stub that routes by URL and records match creations. */
function stubApi() {
  const created: unknown[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      if (url === '/api/v1/players/bots') return Promise.resolve(jsonResponse(BOTS))
      if (url === '/api/v1/players' && method === 'GET') return Promise.resolve(jsonResponse([]))
      if (url === '/api/v1/players' && method === 'POST') {
        return Promise.resolve(
          jsonResponse({ error: { code: 'PLAYER_PROFILE_EXISTS', message: 'exists' } }, 409),
        )
      }
      if (url === '/api/v1/matches' && method === 'POST') {
        created.push(JSON.parse(String(init?.body)))
        return Promise.resolve(jsonResponse({ id: 'match-1' }, 201))
      }
      return Promise.resolve(jsonResponse({ error: { code: 'NOT_FOUND', message: url } }, 404))
    }),
  )
  return created
}

function renderPage() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <AuthProvider>
          <NewMatchPage />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('NewMatchPage bot opponents', () => {
  it('offers the five difficulties easiest to hardest once Bot is chosen', async () => {
    stubApi()
    renderPage()
    const user = userEvent.setup()

    expect(screen.queryByRole('radiogroup', { name: /bot difficulty/i })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /^bot$/i }))

    const radios = screen.getAllByRole('radio')
    expect(radios.map((r) => r.textContent?.replace(/~.*$/, ''))).toEqual([
      'Noob',
      'Easy',
      'Medium',
      'Hard',
      'Pro',
    ])
    expect(screen.getByRole('radio', { name: /medium/i })).toHaveAttribute('aria-checked', 'true')
  })

  it('starts the match against the chosen bot', async () => {
    const created = stubApi()
    renderPage()
    const user = userEvent.setup()

    await user.click(screen.getByRole('button', { name: /^bot$/i }))
    await user.click(screen.getByRole('radio', { name: /pro/i }))
    await user.click(screen.getByRole('button', { name: /start match/i }))

    await waitFor(() => expect(created).toHaveLength(1))
    expect(created[0]).toMatchObject({
      opponent_player_id: 'bot-pro',
      best_of_legs: 3,
      game_type: 'x01',
      starting_player_id: null,
    })
  })
})
