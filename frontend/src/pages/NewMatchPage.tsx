// New Match: pick an existing opponent, create a guest, or choose a
// bot difficulty; choose the match length and who throws first, then
// jump into live scoring.

import { useMutation, useQuery } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { api, ApiError } from '../api/client'
import type { BotDifficulty, GameType, MatchState, PlayerResponse } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { BOT_CHOICES } from '../utils/bots'

const GAME_CHOICES: { value: GameType; label: string; hint: string }[] = [
  { value: 'x01', label: '501', hint: 'double-out' },
  { value: 'cricket', label: 'Cricket', hint: 'race to close' },
  { value: 'halve_it', label: 'Halve It', hint: 'start on 40' },
]

type OpponentKind = 'human' | 'bot'

export function NewMatchPage() {
  const { user } = useAuth()
  const navigate = useNavigate()

  const [gameType, setGameType] = useState<GameType>('x01')
  const [opponentKind, setOpponentKind] = useState<OpponentKind>('human')
  const [botDifficulty, setBotDifficulty] = useState<BotDifficulty>('medium')
  const [opponentId, setOpponentId] = useState<string>('')
  const [guestName, setGuestName] = useState('')
  const [bestOf, setBestOf] = useState(3)
  const [opponentStarts, setOpponentStarts] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const playersQuery = useQuery({
    queryKey: ['players'],
    queryFn: () => api<PlayerResponse[]>('/api/v1/players'),
  })

  // Opponent choices: everyone except the signed-in user's own player.
  const opponents =
    playersQuery.data?.filter((p) => p.user_id !== user?.id) ?? []

  const createMatch = useMutation({
    mutationFn: async () => {
      // Ensure the user has their own player profile; PLAYER_PROFILE_EXISTS
      // just means it's already there.
      try {
        await api('/api/v1/players', {
          method: 'POST',
          body: { display_name: user?.display_name ?? 'Me' },
        })
      } catch (err) {
        if (!(err instanceof ApiError && err.code === 'PLAYER_PROFILE_EXISTS')) throw err
      }

      let opponent = opponentId
      if (opponentKind === 'bot') {
        // The backend keeps one shared bot per difficulty.
        const bots = await api<PlayerResponse[]>('/api/v1/players/bots')
        const bot = bots.find((b) => b.bot_difficulty === botDifficulty)
        if (!bot) throw new Error(`No ${botDifficulty} bot is available.`)
        opponent = bot.id
      } else if (!opponent) {
        const guest = await api<PlayerResponse>('/api/v1/players', {
          method: 'POST',
          body: { display_name: guestName.trim(), is_guest: true },
        })
        opponent = guest.id
      }

      const match = await api<MatchState>('/api/v1/matches', {
        method: 'POST',
        body: {
          opponent_player_id: opponent,
          best_of_legs: bestOf,
          game_type: gameType,
          starting_player_id: opponentStarts ? opponent : null,
        },
      })
      return match
    },
    onSuccess: (match) => navigate(`/matches/${match.id}`),
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : 'Something went wrong.'),
  })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    if (opponentKind === 'human' && !opponentId && guestName.trim() === '') {
      setError('Choose an opponent or enter a guest name.')
      return
    }
    createMatch.mutate()
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b border-gray-200 bg-white px-6 py-4">
        <Link to="/" className="text-sm text-emerald-600 hover:underline">
          ← Dashboard
        </Link>
      </header>

      <main className="mx-auto max-w-lg px-6 py-8">
        <h1 className="mb-6 text-2xl font-bold text-gray-900">New match</h1>

        <form onSubmit={handleSubmit} className="space-y-6 rounded-xl bg-white p-6 shadow-sm">
          <fieldset>
            <legend className="mb-2 text-sm font-medium text-gray-700">Game</legend>
            <div className="flex gap-2">
              {GAME_CHOICES.map((game) => (
                <button
                  key={game.value}
                  type="button"
                  onClick={() => setGameType(game.value)}
                  className={`flex-1 rounded-lg border px-3 py-3 text-sm font-medium ${
                    gameType === game.value
                      ? 'border-emerald-600 bg-emerald-50 text-emerald-700'
                      : 'border-gray-300 text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  {game.label}
                  <span className="block text-xs font-normal text-gray-500">
                    {game.hint}
                  </span>
                </button>
              ))}
            </div>
          </fieldset>

          <fieldset>
            <legend className="mb-2 text-sm font-medium text-gray-700">Opponent</legend>
            <div className="mb-2 flex gap-2">
              {(
                [
                  { value: 'human', label: 'Person' },
                  { value: 'bot', label: 'Bot' },
                ] as { value: OpponentKind; label: string }[]
              ).map((kind) => (
                <button
                  key={kind.value}
                  type="button"
                  onClick={() => setOpponentKind(kind.value)}
                  className={`flex-1 rounded-lg border px-3 py-3 text-sm font-medium ${
                    opponentKind === kind.value
                      ? 'border-emerald-600 bg-emerald-50 text-emerald-700'
                      : 'border-gray-300 text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  {kind.label}
                </button>
              ))}
            </div>
            {opponentKind === 'bot' ? (
              <div
                role="radiogroup"
                aria-label="Bot difficulty"
                className="grid grid-cols-5 gap-2"
              >
                {BOT_CHOICES.map((bot) => (
                  <button
                    key={bot.value}
                    type="button"
                    role="radio"
                    aria-checked={botDifficulty === bot.value}
                    onClick={() => setBotDifficulty(bot.value)}
                    className={`rounded-lg border px-1 py-3 text-sm font-medium ${
                      botDifficulty === bot.value
                        ? 'border-emerald-600 bg-emerald-50 text-emerald-700'
                        : 'border-gray-300 text-gray-700 hover:bg-gray-50'
                    }`}
                  >
                    {bot.label}
                    <span className="block text-xs font-normal text-gray-500">
                      {bot.hint}
                    </span>
                  </button>
                ))}
              </div>
            ) : (
              <>
                <select
                  value={opponentId}
                  onChange={(e) => setOpponentId(e.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 focus:border-emerald-500 focus:outline-none"
                >
                  <option value="">— New guest —</option>
                  {opponents.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.display_name}
                      {p.user_id === null ? ' (guest)' : ''}
                    </option>
                  ))}
                </select>
                {opponentId === '' && (
                  <input
                    placeholder="Guest name"
                    value={guestName}
                    onChange={(e) => setGuestName(e.target.value)}
                    maxLength={100}
                    className="mt-2 w-full rounded-lg border border-gray-300 px-3 py-2 focus:border-emerald-500 focus:outline-none"
                  />
                )}
              </>
            )}
          </fieldset>

          <fieldset>
            <legend className="mb-2 text-sm font-medium text-gray-700">Match length</legend>
            <div className="flex gap-2">
              {[1, 3, 5, 7].map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setBestOf(n)}
                  className={`flex-1 rounded-lg border px-3 py-3 text-sm font-medium ${
                    bestOf === n
                      ? 'border-emerald-600 bg-emerald-50 text-emerald-700'
                      : 'border-gray-300 text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  Best of {n}
                </button>
              ))}
            </div>
          </fieldset>

          <fieldset>
            <legend className="mb-2 text-sm font-medium text-gray-700">Who throws first?</legend>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setOpponentStarts(false)}
                className={`flex-1 rounded-lg border px-3 py-3 text-sm font-medium ${
                  !opponentStarts
                    ? 'border-emerald-600 bg-emerald-50 text-emerald-700'
                    : 'border-gray-300 text-gray-700 hover:bg-gray-50'
                }`}
              >
                Me
              </button>
              <button
                type="button"
                onClick={() => setOpponentStarts(true)}
                className={`flex-1 rounded-lg border px-3 py-3 text-sm font-medium ${
                  opponentStarts
                    ? 'border-emerald-600 bg-emerald-50 text-emerald-700'
                    : 'border-gray-300 text-gray-700 hover:bg-gray-50'
                }`}
              >
                {opponentKind === 'bot' ? 'Bot' : 'Opponent'}
              </button>
            </div>
          </fieldset>

          {error && (
            <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={createMatch.isPending}
            className="w-full rounded-lg bg-emerald-600 px-4 py-3 font-semibold text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            {createMatch.isPending ? 'Starting…' : 'Start match'}
          </button>
        </form>
      </main>
    </div>
  )
}
