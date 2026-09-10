// Match summary: the final (or live) scoreline, each player's numbers
// for the match, and a leg-by-leg breakdown. Everything comes from
// GET /matches/{id}/summary, which the backend derives from raw darts.

import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'

import { api } from '../api/client'
import type { MatchSummary, PlayerMatchSummary } from '../api/types'
import { AppHeader } from '../components/AppHeader'
import { GAME_CHIP, GAME_LABELS } from '../utils/games'

function pct(value: number | null): string {
  return value == null ? '—' : `${value.toFixed(0)}%`
}

function num(value: number | null): string {
  return value == null ? '—' : String(value)
}

function avg(value: number | null): string {
  return value == null ? '—' : value.toFixed(1)
}

function StatRow({ label, values }: { label: string; values: [string, string] }) {
  return (
    <tr className="border-t border-ink-700">
      <td className="py-2.5 text-right font-display text-2xl font-bold tabular-nums">{values[0]}</td>
      <td className="px-3 py-2.5 text-center text-xs font-medium uppercase tracking-wider text-ink-400">
        {label}
      </td>
      <td className="py-2.5 text-left font-display text-2xl font-bold tabular-nums">{values[1]}</td>
    </tr>
  )
}

export function MatchSummaryPage() {
  const { matchId } = useParams<{ matchId: string }>()
  const query = useQuery({
    queryKey: ['match', matchId, 'summary'],
    queryFn: () => api<MatchSummary>(`/api/v1/matches/${matchId}/summary`),
  })

  if (query.isLoading) {
    return <div className="p-8 text-center text-ink-400">Loading summary…</div>
  }
  if (query.isError || !query.data) {
    return (
      <div className="p-8 text-center text-bust-400">
        Match not found.{' '}
        <Link to="/matches" className="underline">
          Back to history
        </Link>
      </div>
    )
  }

  const summary = query.data
  const [p1, p2] = summary.players as [PlayerMatchSummary, PlayerMatchSummary]
  const winner = summary.players.find((p) => p.player_id === summary.winner_player_id)
  const isX01 = summary.game_type === 'x01'
  const live = summary.status === 'in_progress'

  const rows: { label: string; values: [string, string] }[] = [
    { label: 'Darts', values: [String(p1.darts_thrown), String(p2.darts_thrown)] },
  ]
  if (isX01) {
    rows.push(
      { label: '3-dart avg', values: [avg(p1.three_dart_average), avg(p2.three_dart_average)] },
      { label: 'High visit', values: [num(p1.highest_visit), num(p2.highest_visit)] },
      { label: '100+', values: [String(p1.count_100_plus), String(p2.count_100_plus)] },
      { label: '140+', values: [String(p1.count_140_plus), String(p2.count_140_plus)] },
      { label: '180s', values: [String(p1.count_180), String(p2.count_180)] },
      {
        label: 'Checkout',
        values: [
          `${pct(p1.checkout_percentage)} (${p1.checkout_successes}/${p1.checkout_attempts})`,
          `${pct(p2.checkout_percentage)} (${p2.checkout_successes}/${p2.checkout_attempts})`,
        ],
      },
    )
  }

  return (
    <div className="min-h-screen">
      <AppHeader />

      <main className="mx-auto max-w-2xl px-4 py-8 sm:px-6">
        <div className="mb-6 flex flex-wrap items-center gap-2 text-sm text-ink-400">
          <span className={`rounded-md border px-1.5 py-0.5 text-xs font-medium ${GAME_CHIP[summary.game_type]}`}>
            {GAME_LABELS[summary.game_type]}
          </span>
          <span>best of {summary.best_of_legs}</span>
          {summary.completed_at && (
            <>
              <span>·</span>
              <span>
                {new Date(summary.completed_at).toLocaleDateString(undefined, {
                  day: 'numeric',
                  month: 'short',
                  year: 'numeric',
                })}
              </span>
            </>
          )}
          {live && <span className="text-gold-300">· in progress</span>}
        </div>

        {/* Scoreline */}
        <section className="card animate-rise p-6">
          <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3">
            <div className="text-right">
              <p className={`truncate text-lg font-semibold ${winner?.player_id === p1.player_id ? 'text-felt-300' : ''}`}>
                {p1.display_name}
              </p>
            </div>
            <p className="score-display text-6xl">
              {p1.legs_won}
              <span className="mx-2 text-ink-500">–</span>
              {p2.legs_won}
            </p>
            <div className="text-left">
              <p className={`truncate text-lg font-semibold ${winner?.player_id === p2.player_id ? 'text-felt-300' : ''}`}>
                {p2.display_name}
              </p>
            </div>
          </div>
          <p className="mt-4 text-center font-display text-2xl font-bold">
            {winner
              ? <span className="text-felt-300">🏆 {winner.display_name} wins the match</span>
              : live
                ? <span className="text-ink-300">Match in progress</span>
                : <span className="text-ink-400">Match abandoned</span>}
          </p>
        </section>

        {/* Per-player numbers */}
        <section className="card mt-4 p-6">
          <table className="w-full">
            <thead>
              <tr>
                <th className="pb-2 text-right text-sm font-medium text-ink-300">{p1.display_name}</th>
                <th className="px-3 pb-2" />
                <th className="pb-2 text-left text-sm font-medium text-ink-300">{p2.display_name}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <StatRow key={row.label} {...row} />
              ))}
            </tbody>
          </table>
        </section>

        {/* Legs */}
        {summary.legs.length > 0 && (
          <section className="card mt-4 p-6">
            <h2 className="label">Legs</h2>
            <ol className="divide-y divide-ink-700">
              {summary.legs.map((leg) => {
                const legWinner = summary.players.find((p) => p.player_id === leg.winner_player_id)
                return (
                  <li key={leg.leg_number} className="flex items-center justify-between py-2.5 text-sm">
                    <span className="text-ink-400">Leg {leg.leg_number}</span>
                    <span className="font-medium">
                      {legWinner
                        ? <span className="text-felt-300">{legWinner.display_name}</span>
                        : <span className="text-ink-400">{leg.status.replace('_', ' ')}</span>}
                    </span>
                    <span className="tabular-nums text-ink-400">
                      {leg.darts_thrown[p1.player_id] ?? 0} · {leg.darts_thrown[p2.player_id] ?? 0} darts
                    </span>
                  </li>
                )
              })}
            </ol>
          </section>
        )}

        <div className="mt-6 flex flex-wrap gap-3">
          {live && (
            <Link to={`/matches/${summary.id}`} className="btn-primary px-5 py-3">
              Resume scoring
            </Link>
          )}
          <Link to="/matches/new" className={live ? 'btn-secondary px-5 py-3' : 'btn-primary px-5 py-3'}>
            + New Match
          </Link>
          <Link to="/matches" className="btn-secondary px-5 py-3">
            Match history
          </Link>
        </div>
      </main>
    </div>
  )
}
