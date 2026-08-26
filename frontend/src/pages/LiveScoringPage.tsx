// Live Scoring: the heart of the app (dev plan 15.1).
//
// Dart entry is per dart: pick a multiplier, tap a number. The visit
// auto-submits when 3 darts are entered or the entered darts must end
// the turn (reached 0 or an impossible score). That last check is a
// UI convenience only — the backend re-validates everything and its
// response is the truth the screen re-renders from.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { api, ApiError } from '../api/client'
import type {
  DartMultiplier,
  DartRequest,
  MatchState,
  TurnSummary,
  VisitResponse,
} from '../api/types'

function dartScore(dart: DartRequest): number {
  if (dart.multiplier === 'miss' || dart.segment === null) return 0
  const factor = { single: 1, double: 2, triple: 3 }[dart.multiplier]
  return dart.segment * factor
}

function dartLabel(dart: DartRequest): string {
  if (dart.multiplier === 'miss') return 'Miss'
  const prefix = { single: '', double: 'D', triple: 'T' }[dart.multiplier]
  return `${prefix}${dart.segment}`
}

export function LiveScoringPage() {
  const { matchId } = useParams<{ matchId: string }>()
  const queryClient = useQueryClient()

  const [multiplier, setMultiplier] = useState<Exclude<DartMultiplier, 'miss'>>('single')
  const [darts, setDarts] = useState<DartRequest[]>([])
  const [banner, setBanner] = useState<string | null>(null)
  const [recentTurns, setRecentTurns] = useState<TurnSummary[]>([])

  const matchQuery = useQuery({
    queryKey: ['match', matchId],
    queryFn: () => api<MatchState>(`/api/v1/matches/${matchId}`),
  })
  const state = matchQuery.data
  const activePlayer = state?.players.find((p) => p.is_active_turn)

  const submitVisit = useMutation({
    mutationFn: (visitDarts: DartRequest[]) =>
      api<VisitResponse>(`/api/v1/matches/${matchId}/visits`, {
        method: 'POST',
        body: { player_id: activePlayer?.player_id, darts: visitDarts },
      }),
    onSuccess: (response) => {
      queryClient.setQueryData(['match', matchId], response.state)
      setRecentTurns((prev) => [response.turn, ...prev].slice(0, 5))
      setDarts([])
      setMultiplier('single')
      if (response.turn.is_checkout) {
        setBanner(
          response.state.status === 'completed' ? 'Game shot — match won!' : 'Leg won!',
        )
      } else if (response.turn.is_bust) {
        setBanner(`Bust! Score stays at ${response.turn.turn_start_score}.`)
      } else {
        setBanner(null)
      }
    },
    onError: (err) => {
      setDarts([])
      setBanner(err instanceof ApiError ? err.message : 'Something went wrong.')
    },
  })

  const undoVisit = useMutation({
    mutationFn: () =>
      api<MatchState>(`/api/v1/matches/${matchId}/visits/latest`, { method: 'DELETE' }),
    onSuccess: (newState) => {
      queryClient.setQueryData(['match', matchId], newState)
      setRecentTurns((prev) => prev.slice(1))
      setDarts([])
      setBanner('Last visit undone.')
    },
    onError: (err) =>
      setBanner(err instanceof ApiError ? err.message : 'Something went wrong.'),
  })

  function addDart(dart: DartRequest) {
    if (!activePlayer || submitVisit.isPending) return
    const next = [...darts, dart]
    const remaining =
      (activePlayer.remaining_score ?? 0) - next.reduce((sum, d) => sum + dartScore(d), 0)

    // The turn must end when the player reaches 0 or an unfinishable
    // score (<= 1). The server is the judge; we just stop collecting.
    if (next.length === 3 || remaining <= 1) {
      submitVisit.mutate(next)
    } else {
      setDarts(next)
    }
  }

  if (matchQuery.isLoading) {
    return <div className="p-8 text-center text-gray-500">Loading match…</div>
  }
  if (matchQuery.isError || !state) {
    return (
      <div className="p-8 text-center text-red-600">
        Match not found. <Link to="/" className="underline">Back to dashboard</Link>
      </div>
    )
  }

  const finished = state.status !== 'in_progress'
  const winner = state.players.find((p) => p.player_id === state.winner_player_id)

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <header className="flex items-center justify-between px-6 py-3">
        <Link to="/" className="text-sm text-emerald-400 hover:underline">
          ← Dashboard
        </Link>
        <span className="text-sm text-gray-400">
          Best of {state.best_of_legs}
          {state.current_leg ? ` · Leg ${state.current_leg.leg_number}` : ''}
        </span>
      </header>

      {/* Scoreboard */}
      <div className="mx-auto grid max-w-3xl grid-cols-2 gap-4 px-6 py-4">
        {state.players.map((player) => (
          <div
            key={player.player_id}
            className={`rounded-2xl p-6 text-center ${
              player.is_active_turn && !finished
                ? 'bg-emerald-800 ring-2 ring-emerald-400'
                : 'bg-gray-800'
            }`}
          >
            <p className="truncate text-lg font-medium">
              {player.display_name}
              {player.is_active_turn && !finished && ' 🎯'}
            </p>
            <p className="my-2 text-6xl font-bold tabular-nums">
              {player.remaining_score ?? '—'}
            </p>
            <p className="text-sm text-gray-400">Legs: {player.legs_won}</p>
          </div>
        ))}
      </div>

      {banner && (
        <p role="status" className="mx-auto max-w-3xl px-6 pb-2 text-center text-lg font-semibold text-amber-300">
          {banner}
        </p>
      )}

      {finished ? (
        <div className="mx-auto max-w-3xl px-6 py-8 text-center">
          <p className="text-3xl font-bold text-emerald-400">
            {state.status === 'completed' && winner
              ? `${winner.display_name} wins the match!`
              : 'Match ended.'}
          </p>
          <Link
            to="/"
            className="mt-6 inline-block rounded-lg bg-emerald-600 px-6 py-3 font-semibold hover:bg-emerald-700"
          >
            Back to dashboard
          </Link>
        </div>
      ) : (
        <div className="mx-auto max-w-3xl px-6 pb-10">
          {/* Current visit */}
          <div className="mb-3 flex items-center justify-between">
            <div className="flex gap-2">
              {[0, 1, 2].map((slot) => (
                <span
                  key={slot}
                  className="inline-flex h-9 w-14 items-center justify-center rounded-lg bg-gray-800 font-mono text-sm"
                >
                  {darts[slot] ? dartLabel(darts[slot]) : '·'}
                </span>
              ))}
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setDarts(darts.slice(0, -1))}
                disabled={darts.length === 0}
                className="rounded-lg bg-gray-700 px-3 py-1.5 text-sm hover:bg-gray-600 disabled:opacity-40"
              >
                ⌫ Dart
              </button>
              <button
                onClick={() => undoVisit.mutate()}
                disabled={undoVisit.isPending}
                className="rounded-lg bg-gray-700 px-3 py-1.5 text-sm hover:bg-gray-600 disabled:opacity-40"
              >
                Undo visit
              </button>
            </div>
          </div>

          {/* Multiplier selector */}
          <div className="mb-3 grid grid-cols-4 gap-2">
            {(['single', 'double', 'triple'] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMultiplier(m)}
                className={`rounded-lg py-2 text-sm font-semibold uppercase ${
                  multiplier === m
                    ? 'bg-emerald-600'
                    : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                }`}
              >
                {m}
              </button>
            ))}
            <button
              onClick={() => addDart({ segment: null, multiplier: 'miss' })}
              className="rounded-lg bg-gray-800 py-2 text-sm font-semibold uppercase text-gray-300 hover:bg-gray-700"
            >
              Miss
            </button>
          </div>

          {/* Number pad */}
          <div className="grid grid-cols-7 gap-2">
            {Array.from({ length: 20 }, (_, i) => i + 1).map((n) => (
              <button
                key={n}
                onClick={() => addDart({ segment: n, multiplier })}
                className="rounded-lg bg-gray-800 py-3 text-lg font-semibold tabular-nums hover:bg-gray-700"
              >
                {n}
              </button>
            ))}
            <button
              onClick={() => addDart({ segment: 25, multiplier: multiplier === 'triple' ? 'single' : multiplier })}
              className="col-span-2 rounded-lg bg-red-900 py-3 text-lg font-semibold hover:bg-red-800"
              title="Outer bull 25; select Double for the inner bull (50)"
            >
              Bull
            </button>
          </div>

          {/* Recent visits */}
          {recentTurns.length > 0 && (
            <div className="mt-6">
              <p className="mb-2 text-sm font-medium text-gray-400">Recent visits</p>
              <ul className="space-y-1 text-sm">
                {recentTurns.map((turn) => {
                  const who = state.players.find((p) => p.player_id === turn.player_id)
                  return (
                    <li key={turn.id} className="flex justify-between rounded-lg bg-gray-800 px-3 py-2">
                      <span>{who?.display_name}</span>
                      <span className="font-mono">
                        {turn.is_bust
                          ? 'BUST'
                          : turn.is_checkout
                            ? `${turn.points_scored} ✓ out`
                            : turn.points_scored}
                        {'  '}({turn.turn_start_score} → {turn.turn_end_score})
                      </span>
                    </li>
                  )
                })}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
