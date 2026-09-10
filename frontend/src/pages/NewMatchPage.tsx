// New Match: pick an existing opponent, create a guest, or choose a
// bot difficulty; choose the match length and who throws first, then
// jump into live scoring.

import { useMutation, useQuery } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { api, ApiError } from '../api/client'
import type { BotDifficulty, GameType, MatchState, PlayerResponse } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { AppHeader } from '../components/AppHeader'
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
    <div className="min-h-screen">
      <AppHeader />

      <main className="mx-auto max-w-lg px-4 py-8 sm:px-6">
        <h1 className="mb-6 font-display text-4xl font-bold">New match</h1>

        <form onSubmit={handleSubmit} className="card space-y-6 p-6">
          <fieldset>
            <legend className="label">Game</legend>
            <div className="flex gap-2">
              {GAME_CHOICES.map((game) => (
                <button
                  key={game.value}
                  type="button"
                  onClick={() => setGameType(game.value)}
                  className={`choice flex-1 ${gameType === game.value ? 'choice-on' : 'choice-off'}`}
                >
                  {game.label}
                  <span className="block text-xs font-normal text-ink-400">
                    {game.hint}
                  </span>
                </button>
              ))}
            </div>
          </fieldset>

          <fieldset>
            <legend className="label">Opponent</legend>
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
                  className={`choice flex-1 ${opponentKind === kind.value ? 'choice-on' : 'choice-off'}`}
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
                    className={`choice px-1 ${botDifficulty === bot.value ? 'choice-on' : 'choice-off'}`}
                  >
                    {bot.label}
                    <span className="block text-xs font-normal text-ink-400">
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
                  className="input"
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
                    className="input mt-2"
                  />
                )}
              </>
            )}
          </fieldset>

          <fieldset>
            <legend className="label">Match length</legend>
            <div className="flex gap-2">
              {[1, 3, 5, 7].map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setBestOf(n)}
                  className={`choice flex-1 ${bestOf === n ? 'choice-on' : 'choice-off'}`}
                >
                  Best of {n}
                </button>
              ))}
            </div>
          </fieldset>

          <fieldset>
            <legend className="label">Who throws first?</legend>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setOpponentStarts(false)}
                className={`choice flex-1 ${!opponentStarts ? 'choice-on' : 'choice-off'}`}
              >
                Me
              </button>
              <button
                type="button"
                onClick={() => setOpponentStarts(true)}
                className={`choice flex-1 ${opponentStarts ? 'choice-on' : 'choice-off'}`}
              >
                {opponentKind === 'bot' ? 'Bot' : 'Opponent'}
              </button>
            </div>
          </fieldset>

          {error && (
            <p role="alert" className="rounded-xl border border-bust-700/60 bg-bust-900/40 px-3 py-2 text-sm text-bust-400">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={createMatch.isPending}
            className="btn-primary w-full px-4 py-3"
          >
            {createMatch.isPending ? 'Starting…' : 'Start match'}
          </button>
        </form>
      </main>
    </div>
  )
}
