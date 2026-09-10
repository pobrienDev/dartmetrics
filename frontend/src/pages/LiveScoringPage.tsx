// Live Scoring: the heart of the app (dev plan 15.1).
//
// Dart entry is per dart: pick a multiplier, tap a number. The visit
// auto-submits when 3 darts are entered or the entered darts must end
// the turn (reached 0 or an impossible score). That last check is a
// UI convenience only — the backend re-validates everything and its
// response is the truth the screen re-renders from.
//
// While darts are being entered the active player's card shows the
// running remaining score and, in 501, a suggested checkout for the
// darts still in hand. Busts, 180s and checkouts get a visible moment
// (shake / flash) driven by the server's verdict on the visit.
//
// Against a bot, the page asks the server to throw for the bot
// whenever the scoreboard shows the bot as active; a short pause
// keeps the exchange readable.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { api, ApiError } from '../api/client'
import type {
  BotVisitResponse,
  DartMultiplier,
  DartRequest,
  MatchState,
  PlayerState,
  TurnSummary,
  VisitResponse,
} from '../api/types'
import { checkoutFor } from '../utils/checkouts'
import { boardClosed, CRICKET_TARGETS, marksAfterDarts, markSymbol } from '../utils/cricket'
import { dartLabel, dartScore, visitMustEnd } from '../utils/darts'
import { GAME_CHIP, GAME_LABELS } from '../utils/games'

interface RecentVisit {
  turn: TurnSummary
  labels: string
}

type Moment = 'bust' | 'oneEighty' | 'ton' | 'checkout' | null

interface Flash {
  moment: Exclude<Moment, null>
  playerId: string
  key: number
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

/** Bot players are called "Medium Bot" etc.; the badge already says bot. */
function shortName(player: PlayerState): string {
  return player.bot_difficulty ? player.display_name.replace(/\s+bot$/i, '') : player.display_name
}

const BOT_THROW_DELAY_MS = 1200
const FLASH_MS = 1300

export function LiveScoringPage() {
  const { matchId } = useParams<{ matchId: string }>()
  const queryClient = useQueryClient()

  const [multiplier, setMultiplier] = useState<Exclude<DartMultiplier, 'miss'>>('single')
  const [band, setBand] = useState<'inner' | 'outer'>('outer')
  const [darts, setDarts] = useState<DartRequest[]>([])
  const [banner, setBanner] = useState<{ text: string; moment: Moment } | null>(null)
  const [flash, setFlash] = useState<Flash | null>(null)
  const [recentTurns, setRecentTurns] = useState<RecentVisit[]>([])

  const matchQuery = useQuery({
    queryKey: ['match', matchId],
    queryFn: () => api<MatchState>(`/api/v1/matches/${matchId}`),
  })
  const state = matchQuery.data
  const activePlayer = state?.players.find((p) => p.is_active_turn)
  const isCricket = state?.game_type === 'cricket'
  const isHalveIt = state?.game_type === 'halve_it'
  const isX01 = state?.game_type === 'x01'
  const activeTarget = isHalveIt ? activePlayer?.round_target : null
  const botIsUp = state?.status === 'in_progress' && activePlayer?.bot_difficulty != null

  // Band rounds pre-select their own band; the player can override.
  useEffect(() => {
    setBand(defaultBand(activeTarget))
  }, [activeTarget])

  // Flashes clear themselves so the next one can play.
  useEffect(() => {
    if (!flash) return
    const timer = setTimeout(() => setFlash(null), FLASH_MS)
    return () => clearTimeout(timer)
  }, [flash])

  function show(text: string | null, moment: Moment = null) {
    setBanner(text ? { text, moment } : null)
  }

  function celebrate(moment: Exclude<Moment, null>, playerId: string) {
    setFlash({ moment, playerId, key: Date.now() })
  }

  // Shared by human and bot visits: apply the server's state and
  // announce what happened.
  function applyVisit(response: VisitResponse, visitDarts: DartRequest[], who: string) {
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
    const turn = response.turn
    const isYou = who === 'You'
    const threw = isYou ? 'You threw' : `${who} threw`

    if (response.state.game_type === 'halve_it' && !turn.is_checkout) {
      const newScore = response.state.players.find(
        (p) => p.player_id === turn.player_id,
      )?.score
      if (oldScore != null && newScore != null) {
        if (newScore < oldScore) {
          celebrate('bust', turn.player_id)
          show(`${who}: halved! ${oldScore} → ${newScore}`, 'bust')
        } else if (newScore > oldScore) {
          show(`${who}: +${newScore - oldScore}`)
        } else {
          show(null)
        }
      }
      return
    }
    if (turn.is_checkout) {
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
      celebrate('checkout', turn.player_id)
      show(response.state.status === 'completed' ? wonMatch : wonLeg, 'checkout')
    } else if (turn.is_bust) {
      celebrate('bust', turn.player_id)
      show(`${who}: bust! Score stays at ${turn.turn_start_score}.`, 'bust')
    } else if (turn.points_scored === 180) {
      celebrate('oneEighty', turn.player_id)
      show(isYou ? 'ONE HUNDRED AND EIGHTY!' : `${who}: ONE HUNDRED AND EIGHTY!`, 'oneEighty')
    } else if (!isCricketGame(response.state) && turn.points_scored >= 100) {
      celebrate('ton', turn.player_id)
      show(`${threw} ${labels} for ${turn.points_scored}!`, 'ton')
    } else if (!isYou) {
      show(`${who} threw ${labels} for ${turn.points_scored}.`)
    } else {
      show(null)
    }
  }

  const submitVisit = useMutation({
    mutationFn: (visitDarts: DartRequest[]) =>
      api<VisitResponse>(`/api/v1/matches/${matchId}/visits`, {
        method: 'POST',
        body: { player_id: activePlayer?.player_id, darts: visitDarts },
      }),
    onSuccess: (response, visitDarts) => applyVisit(response, visitDarts, 'You'),
    onError: (err) => {
      setDarts([])
      show(err instanceof ApiError ? err.message : 'Something went wrong.', 'bust')
    },
  })

  const botVisit = useMutation({
    mutationFn: () =>
      api<BotVisitResponse>(`/api/v1/matches/${matchId}/bot-visit`, { method: 'POST' }),
    onSuccess: (response) =>
      applyVisit(response, response.darts, activePlayer ? shortName(activePlayer) : 'Bot'),
    onError: (err) => {
      // NOT_BOT_TURN just means the board moved on; a refetch resyncs.
      if (err instanceof ApiError && err.code === 'NOT_BOT_TURN') {
        queryClient.invalidateQueries({ queryKey: ['match', matchId] })
        return
      }
      show(err instanceof ApiError ? err.message : 'Something went wrong.', 'bust')
    },
  })

  // Let the bot throw after a beat whenever it is up. The ref stops a
  // second request while one is in flight (state updates re-run the
  // effect before the mutation's pending flag flips).
  const botRequestInFlight = useRef(false)
  useEffect(() => {
    if (!botIsUp || botRequestInFlight.current) return
    const timer = setTimeout(() => {
      botRequestInFlight.current = true
      botVisit.mutate(undefined, {
        onSettled: () => {
          botRequestInFlight.current = false
        },
      })
    }, BOT_THROW_DELAY_MS)
    return () => clearTimeout(timer)
    // botVisit is a stable mutation handle; only the board matters here.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [botIsUp, state])

  const undoVisit = useMutation({
    mutationFn: () =>
      api<MatchState>(`/api/v1/matches/${matchId}/visits/latest`, { method: 'DELETE' }),
    onSuccess: (newState) => {
      queryClient.setQueryData(['match', matchId], newState)
      // Mirrors the server: undoing past a bot's reply removes the
      // human visit before it as well.
      setRecentTurns((prev) => {
        const latestWasBot = newState.players.some(
          (p) => p.player_id === prev[0]?.turn.player_id && p.bot_difficulty != null,
        )
        return prev.slice(latestWasBot ? 2 : 1)
      })
      setDarts([])
      show('Last visit undone.')
    },
    onError: (err) => show(err instanceof ApiError ? err.message : 'Something went wrong.', 'bust'),
  })

  function addDart(rawDart: DartRequest) {
    if (!activePlayer || submitVisit.isPending || botIsUp) return
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
    return <div className="p-8 text-center text-ink-400">Loading match…</div>
  }
  if (matchQuery.isError || !state) {
    return (
      <div className="p-8 text-center text-bust-400">
        Match not found. <Link to="/" className="underline">Back to dashboard</Link>
      </div>
    )
  }

  const finished = state.status !== 'in_progress'
  const winner = state.players.find((p) => p.player_id === state.winner_player_id)
  const visitScore = darts.reduce((sum, d) => sum + dartScore(d), 0)
  const dartsLeft = 3 - darts.length

  return (
    <div className="min-h-screen bg-ink-950">
      <header className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3 sm:px-6">
        <Link to="/" className="btn-ghost -ml-2 px-2 py-1 text-sm">
          ← Dashboard
        </Link>
        <span className="flex items-center gap-2 text-sm text-ink-400">
          <span className={`rounded-md border px-1.5 py-0.5 text-xs font-medium ${GAME_CHIP[state.game_type]}`}>
            {GAME_LABELS[state.game_type]}
          </span>
          Best of {state.best_of_legs}
          {state.current_leg ? ` · Leg ${state.current_leg.leg_number}` : ''}
        </span>
      </header>

      {/* Scoreboard */}
      <div className="mx-auto grid max-w-3xl grid-cols-2 gap-3 px-4 py-2 sm:gap-4 sm:px-6">
        {state.players.map((player) => {
          const isActive = player.is_active_turn && !finished
          const playerFlash = flash?.playerId === player.player_id ? flash : null
          const flashClass =
            playerFlash?.moment === 'bust'
              ? 'animate-shake ring-2 ring-bust-500'
              : playerFlash?.moment === 'oneEighty'
                ? 'animate-flash-gold ring-2 ring-gold-400'
                : playerFlash?.moment === 'checkout'
                  ? 'animate-flash-green ring-2 ring-felt-400'
                  : playerFlash?.moment === 'ton'
                    ? 'ring-2 ring-gold-400/70'
                    : ''
          // Running score while darts are being entered (501 only).
          const liveRemaining =
            isX01 && isActive && player.remaining_score != null
              ? player.remaining_score - visitScore
              : player.remaining_score
          const hint =
            isX01 && isActive && !botIsUp && liveRemaining != null
              ? checkoutFor(liveRemaining, dartsLeft)
              : null

          return (
            <div
              key={`${player.player_id}-${playerFlash?.key ?? ''}`}
              className={`relative rounded-2xl border p-4 text-center transition-colors sm:p-6 ${
                isActive
                  ? 'border-felt-500 bg-felt-900/60'
                  : 'border-ink-700 bg-ink-800'
              } ${flashClass}`}
            >
              <p className="flex items-center justify-center gap-2 text-base font-semibold sm:text-lg">
                <span className="truncate">{shortName(player)}</span>
                {player.bot_difficulty && (
                  <span className="shrink-0 rounded bg-ink-700 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-ink-300">
                    bot
                  </span>
                )}
                {isActive && <span className="shrink-0" aria-label="throwing">🎯</span>}
              </p>
              {isHalveIt ? (
                <>
                  <p className="score-display my-2 text-6xl sm:text-7xl">{player.score ?? '—'}</p>
                  <p className="text-sm text-felt-300">
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
                        <p className="text-xs text-ink-400">{target === 25 ? 'Bull' : target}</p>
                        <p className={`font-display text-2xl font-bold ${count >= 3 ? 'text-felt-400' : 'text-ink-100'}`}>
                          {markSymbol(count)}
                        </p>
                      </div>
                    )
                  })}
                </div>
              ) : (
                <>
                  <p
                    className={`score-display my-2 text-6xl sm:text-7xl ${
                      playerFlash?.moment === 'bust' ? 'text-bust-400' : ''
                    }`}
                  >
                    {liveRemaining ?? '—'}
                  </p>
                  <p className="h-5 text-sm">
                    {hint ? (
                      <span className="text-gold-300">
                        <span className="text-ink-400">Out: </span>
                        <span className="font-mono font-semibold">{hint.join(' ')}</span>
                      </span>
                    ) : isActive && darts.length > 0 ? (
                      <span className="text-ink-400">Visit so far: {visitScore}</span>
                    ) : null}
                  </p>
                </>
              )}
              <p className="mt-1 text-xs uppercase tracking-wider text-ink-400">
                Legs <span className="font-display text-base font-bold text-ink-100">{player.legs_won}</span>
              </p>
            </div>
          )
        })}
      </div>

      <div className="mx-auto min-h-10 max-w-3xl px-4 py-1 text-center sm:px-6">
        {banner && (
          <p
            role="status"
            key={banner.text}
            className={`animate-pop font-display text-xl font-bold sm:text-2xl ${
              banner.moment === 'bust'
                ? 'text-bust-400'
                : banner.moment === 'oneEighty' || banner.moment === 'ton'
                  ? 'text-gold-300'
                  : banner.moment === 'checkout'
                    ? 'text-felt-300'
                    : 'text-ink-100'
            }`}
          >
            {banner.text}
          </p>
        )}
      </div>

      {finished ? (
        <div className="mx-auto max-w-3xl px-4 py-8 text-center sm:px-6">
          <p className="animate-pop font-display text-4xl font-extrabold text-felt-300 sm:text-5xl">
            {state.status === 'completed' && winner
              ? `${winner.display_name} wins the match!`
              : 'Match ended.'}
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Link to={`/matches/${state.id}/summary`} className="btn-primary px-6 py-3">
              View match summary
            </Link>
            <Link to="/" className="btn-secondary px-6 py-3">
              Back to dashboard
            </Link>
          </div>
        </div>
      ) : botIsUp ? (
        <div className="mx-auto max-w-3xl px-4 pb-10 sm:px-6">
          <p role="status" className="py-10 text-center text-xl text-ink-300">
            {botVisit.isPending
              ? `${activePlayer ? shortName(activePlayer) : 'Bot'} is throwing…`
              : `${activePlayer ? shortName(activePlayer) : 'Bot'} is stepping up…`}
          </p>
          <div className="flex justify-center">
            <button
              onClick={() => undoVisit.mutate()}
              disabled={undoVisit.isPending || botVisit.isPending}
              className="btn-secondary px-3 py-2.5 text-sm"
            >
              Undo my last visit
            </button>
          </div>
          {recentTurns.length > 0 && (
            <RecentVisits turns={recentTurns} state={state} isCricket={isCricket} />
          )}
        </div>
      ) : (
        <div className="mx-auto max-w-3xl px-4 pb-10 sm:px-6">
          {/* Current visit */}
          <div className="mb-3 flex items-center justify-between">
            <div className="flex gap-2">
              {[0, 1, 2].map((slot) => (
                <span
                  key={slot}
                  className={`inline-flex h-10 w-14 items-center justify-center rounded-lg border font-mono text-sm ${
                    darts[slot]
                      ? 'border-felt-700 bg-felt-900/60 text-felt-200'
                      : 'border-ink-700 bg-ink-900 text-ink-500'
                  }`}
                >
                  {darts[slot] ? dartLabel(darts[slot]) : '·'}
                </span>
              ))}
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setDarts(darts.slice(0, -1))}
                disabled={darts.length === 0}
                className="btn-secondary px-3 py-2.5 text-sm"
              >
                ⌫ Dart
              </button>
              <button
                onClick={() => undoVisit.mutate()}
                disabled={undoVisit.isPending}
                className="btn-secondary px-3 py-2.5 text-sm"
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
                className={`rounded-xl py-3 text-sm font-bold uppercase tracking-wider transition ${
                  multiplier === m
                    ? 'bg-felt-500 text-ink-950'
                    : 'bg-ink-800 text-ink-300 hover:bg-ink-700'
                }`}
              >
                {m}
              </button>
            ))}
            <button
              onClick={() => addDart({ segment: null, multiplier: 'miss' })}
              className="rounded-xl bg-ink-800 py-3 text-sm font-bold uppercase tracking-wider text-ink-300 transition hover:bg-ink-700"
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
                  className={`rounded-xl py-2.5 text-xs font-bold uppercase tracking-wider transition ${
                    band === b ? 'bg-sky-600 text-white' : 'bg-ink-800 text-ink-300 hover:bg-ink-700'
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
                className="rounded-xl bg-ink-800 py-3.5 font-display text-2xl font-bold tabular-nums transition hover:bg-ink-700 active:scale-95 sm:py-4"
              >
                {n}
              </button>
            ))}
            <button
              onClick={() => addDart({ segment: 25, multiplier: multiplier === 'triple' ? 'single' : multiplier })}
              className="col-span-5 flex items-center justify-center gap-3 rounded-xl bg-gradient-to-br from-bust-700 to-bust-900 py-3.5 font-display text-2xl font-bold ring-1 ring-bust-500/50 transition hover:from-bust-500 hover:to-bust-700 active:scale-95 sm:col-span-2 sm:py-4"
              title="Outer bull 25; select Double for the inner bull (50)"
            >
              <span className="inline-block h-4 w-4 rounded-full border-2 border-white/80 bg-bust-500" aria-hidden="true" />
              Bull
            </button>
          </div>

          {recentTurns.length > 0 && (
            <RecentVisits turns={recentTurns} state={state} isCricket={isCricket} />
          )}
        </div>
      )}
    </div>
  )
}

function isCricketGame(state: MatchState): boolean {
  return state.game_type === 'cricket'
}

function RecentVisits({
  turns,
  state,
  isCricket,
}: {
  turns: RecentVisit[]
  state: MatchState
  isCricket: boolean
}) {
  const isHalveIt = state.game_type === 'halve_it'
  return (
    <div className="mt-6">
      <p className="label">Recent visits</p>
      <ul className="space-y-1 text-sm">
        {turns.map(({ turn, labels }) => {
          const who = state.players.find((p) => p.player_id === turn.player_id)
          // Halve It: a round either adds its qualifying points or halves.
          const halved = isHalveIt && turn.points_scored === 0 && !turn.is_checkout
          const tone = turn.is_bust || halved
            ? 'text-bust-400'
            : turn.is_checkout
              ? 'text-felt-300'
              : turn.points_scored >= 100 && !isCricket
                ? 'text-gold-300'
                : 'text-ink-200'
          return (
            <li key={turn.id} className="flex justify-between rounded-lg bg-ink-800 px-3 py-2">
              <span className="text-ink-300">{who ? shortName(who) : ''}</span>
              <span className={`font-mono ${tone}`}>
                {isCricket ? (
                  <>
                    {labels}
                    {turn.is_checkout && ' ◎ closed'}
                  </>
                ) : isHalveIt ? (
                  <>
                    {labels}
                    {'  '}
                    {halved ? 'HALVED' : `+${turn.points_scored}`}
                  </>
                ) : (
                  <>
                    {labels}
                    {'  '}
                    {turn.is_bust
                      ? 'BUST'
                      : turn.is_checkout
                        ? `${turn.points_scored} ✓ out`
                        : turn.points_scored}
                    {'  '}
                    <span className="text-ink-500">({turn.turn_start_score} → {turn.turn_end_score})</span>
                  </>
                )}
              </span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
