// Live Scoring: the heart of the app (dev plan 15.1).
//
// Dart entry is per dart: pick a multiplier, tap a number. The visit
// auto-submits when 3 darts are entered or the entered darts must end
// the turn (reached 0 or an impossible score). That last check is a
// UI convenience only — the backend re-validates everything and its
// response is the truth the screen re-renders from.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { api, ApiError } from '../api/client'
import type {
  DartMultiplier,
  DartRequest,
  MatchState,
  TurnSummary,
  VisitResponse,
} from '../api/types'
import { boardClosed, CRICKET_TARGETS, marksAfterDarts, markSymbol } from '../utils/cricket'
import { dartLabel, dartScore, visitMustEnd } from '../utils/darts'

interface RecentVisit {
  turn: TurnSummary
  labels: string
}

const ROUND_LABELS: Record<string, string> = {
  outer_black: 'Outer Black',
  outer_white: 'Outer White',
  inner_black: 'Inner Black',
  inner_white: 'Inner White',
  doubles: 'Any Double',
  triples: 'Any Triple',
  sixty_three: 'Exactly 63',
  green_bull: 'Green Bull (25)',
  red_bull: 'Red Bull (50)',
}

function defaultBand(roundTarget: string | null | undefined): 'inner' | 'outer' {
  return roundTarget?.startsWith('inner') ? 'inner' : 'outer'
}

export function LiveScoringPage() {
  const { matchId } = useParams<{ matchId: string }>()
  const queryClient = useQueryClient()

  const [multiplier, setMultiplier] = useState<Exclude<DartMultiplier, 'miss'>>('single')
  const [band, setBand] = useState<'inner' | 'outer'>('outer')
  const [darts, setDarts] = useState<DartRequest[]>([])
  const [banner, setBanner] = useState<string | null>(null)
  const [recentTurns, setRecentTurns] = useState<RecentVisit[]>([])

  const matchQuery = useQuery({
    queryKey: ['match', matchId],
    queryFn: () => api<MatchState>(`/api/v1/matches/${matchId}`),
  })
  const state = matchQuery.data
  const activePlayer = state?.players.find((p) => p.is_active_turn)
  const isCricket = state?.game_type === 'cricket'
  const isHalveIt = state?.game_type === 'halve_it'
  const activeTarget = isHalveIt ? activePlayer?.round_target : null

  // Band rounds pre-select their own band; the player can override.
  useEffect(() => {
    setBand(defaultBand(activeTarget))
  }, [activeTarget])

  const submitVisit = useMutation({
    mutationFn: (visitDarts: DartRequest[]) =>
      api<VisitResponse>(`/api/v1/matches/${matchId}/visits`, {
        method: 'POST',
        body: { player_id: activePlayer?.player_id, darts: visitDarts },
      }),
    onSuccess: (response, visitDarts) => {
      // For Halve It, compare against the cached state to spot a halving
      const before = queryClient.getQueryData<MatchState>(['match', matchId])
      const oldScore = before?.players.find(
        (p) => p.player_id === response.turn.player_id,
      )?.score
      queryClient.setQueryData(['match', matchId], response.state)
      const labels = visitDarts.map(dartLabel).join(' ')
      setRecentTurns((prev) => [{ turn: response.turn, labels }, ...prev].slice(0, 5))
      setDarts([])
      setMultiplier('single')
      if (response.state.game_type === 'halve_it' && !response.turn.is_checkout) {
        const newScore = response.state.players.find(
          (p) => p.player_id === response.turn.player_id,
        )?.score
        if (oldScore != null && newScore != null) {
          setBanner(
            newScore < oldScore
              ? `Halved! ${oldScore} → ${newScore}`
              : newScore > oldScore
                ? `+${newScore - oldScore}`
                : null,
          )
        }
        return
      }
      if (response.turn.is_checkout) {
        const game = response.state.game_type
        const wonLeg =
          game === 'cricket'
            ? 'Board closed — leg won!'
            : game === 'halve_it'
              ? 'Game decided on points!'
              : 'Leg won!'
        const wonMatch =
          game === 'cricket'
            ? 'Board closed — match won!'
            : game === 'halve_it'
              ? 'Match decided on points!'
              : 'Game shot — match won!'
        setBanner(response.state.status === 'completed' ? wonMatch : wonLeg)
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

  function addDart(rawDart: DartRequest) {
    if (!activePlayer || submitVisit.isPending) return
    // In Halve It, numbered singles carry the selected band.
    const dart: DartRequest =
      isHalveIt &&
      rawDart.multiplier === 'single' &&
      rawDart.segment !== null &&
      rawDart.segment !== 25
        ? { ...rawDart, band }
        : rawDart
    const next = [...darts, dart]

    // The server is the judge; we just stop collecting darts.
    let mustEnd: boolean
    if (isCricket) {
      mustEnd =
        next.length === 3 || boardClosed(marksAfterDarts(activePlayer.marks ?? {}, next))
    } else if (isHalveIt) {
      mustEnd = next.length === 3 // rounds never end early
    } else {
      const remaining =
        (activePlayer.remaining_score ?? 0) -
        next.reduce((sum, d) => sum + dartScore(d), 0)
      mustEnd = visitMustEnd(next.length, remaining)
    }

    if (mustEnd) {
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
            {isHalveIt ? (
              <>
                <p className="my-2 text-6xl font-bold tabular-nums">
                  {player.score ?? '—'}
                </p>
                <p className="text-sm text-emerald-300">
                  Round {player.round ?? '—'}
                  {player.round_target
                    ? ` · ${ROUND_LABELS[player.round_target] ?? player.round_target}`
                    : ''}
                </p>
              </>
            ) : isCricket ? (
              <div className="my-2 grid grid-cols-7 gap-1">
                {CRICKET_TARGETS.map((target) => {
                  const count = player.marks?.[String(target)] ?? 0
                  return (
                    <div key={target} className="text-center">
                      <p className="text-xs text-gray-400">
                        {target === 25 ? 'Bull' : target}
                      </p>
                      <p
                        className={`text-2xl font-bold ${
                          count >= 3 ? 'text-emerald-400' : 'text-white'
                        }`}
                      >
                        {markSymbol(count)}
                      </p>
                    </div>
                  )
                })}
              </div>
            ) : (
              <p className="my-2 text-6xl font-bold tabular-nums">
                {player.remaining_score ?? '—'}
              </p>
            )}
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
                className="rounded-lg bg-gray-700 px-3 py-2.5 text-sm hover:bg-gray-600 disabled:opacity-40"
              >
                ⌫ Dart
              </button>
              <button
                onClick={() => undoVisit.mutate()}
                disabled={undoVisit.isPending}
                className="rounded-lg bg-gray-700 px-3 py-2.5 text-sm hover:bg-gray-600 disabled:opacity-40"
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
                className={`rounded-lg py-3 text-sm font-semibold uppercase ${
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
              className="rounded-lg bg-gray-800 py-3 text-sm font-semibold uppercase text-gray-300 hover:bg-gray-700"
            >
              Miss
            </button>
          </div>

          {/* Halve It: which single band a numbered single landed in */}
          {isHalveIt && multiplier === 'single' && (
            <div className="mb-3 grid grid-cols-2 gap-2">
              {(['outer', 'inner'] as const).map((b) => (
                <button
                  key={b}
                  onClick={() => setBand(b)}
                  className={`rounded-lg py-2.5 text-xs font-semibold uppercase ${
                    band === b
                      ? 'bg-sky-700'
                      : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                  }`}
                >
                  {b} single band
                </button>
              ))}
            </div>
          )}

          {/* Number pad: 5 columns on phones keeps every key at a
              comfortable thumb size; 7 columns from tablet up. */}
          <div className="grid grid-cols-5 gap-2 sm:grid-cols-7">
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
              className="col-span-5 rounded-lg bg-red-900 py-3 text-lg font-semibold hover:bg-red-800 sm:col-span-2"
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
                {recentTurns.map(({ turn, labels }) => {
                  const who = state.players.find((p) => p.player_id === turn.player_id)
                  return (
                    <li key={turn.id} className="flex justify-between rounded-lg bg-gray-800 px-3 py-2">
                      <span>{who?.display_name}</span>
                      <span className="font-mono">
                        {isCricket ? (
                          <>
                            {labels}
                            {turn.is_checkout && ' ◎ closed'}
                          </>
                        ) : (
                          <>
                            {turn.is_bust
                              ? 'BUST'
                              : turn.is_checkout
                                ? `${turn.points_scored} ✓ out`
                                : turn.points_scored}
                            {'  '}({turn.turn_start_score} → {turn.turn_end_score})
                          </>
                        )}
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
