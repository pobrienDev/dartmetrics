// Dashboard: career KPIs, matches to resume, and the way into a new match.

import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { api } from '../api/client'
import type { MatchListResponse, PlayerResponse, PlayerStats } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { AppHeader } from '../components/AppHeader'
import { GAME_LABELS } from '../utils/games'

export function DashboardPage() {
  const { user } = useAuth()

  const ongoing = useQuery({
    queryKey: ['matches', 'in_progress'],
    queryFn: () => api<MatchListResponse>('/api/v1/matches?status=in_progress'),
  })

  // The user's own player profile (if created), then their career stats.
  const players = useQuery({
    queryKey: ['players'],
    queryFn: () => api<PlayerResponse[]>('/api/v1/players'),
  })
  const myPlayer = players.data?.find((p) => p.user_id === user?.id)
  const stats = useQuery({
    queryKey: ['stats', myPlayer?.id],
    queryFn: () => api<PlayerStats>(`/api/v1/players/${myPlayer!.id}/stats`),
    enabled: myPlayer !== undefined,
  })

  const s = stats.data
  // First-visit nudge: no profile yet, or a profile that has never thrown
  // a dart. Hidden while there is a match to resume.
  const hasOngoing = (ongoing.data?.items.length ?? 0) > 0
  const noHistory =
    !hasOngoing && players.isSuccess && (myPlayer === undefined || (s !== undefined && s.total_darts === 0))

  const kpis = [
    {
      label: '3-dart average',
      value: s?.three_dart_average?.toFixed(1) ?? '—',
      hint: s ? `${s.total_darts} darts thrown` : undefined,
    },
    {
      label: 'Win rate',
      value: s?.win_percentage != null ? `${s.win_percentage.toFixed(0)}%` : '—',
      hint: s ? `${s.matches_won}–${s.matches_played - s.matches_won}` : undefined,
    },
    {
      label: 'Checkout %',
      value: s?.checkout_percentage != null ? `${s.checkout_percentage.toFixed(0)}%` : '—',
      hint: s ? `${s.checkout_successes}/${s.checkout_attempts} attempts` : undefined,
    },
    {
      label: '180s',
      value: s ? String(s.count_180) : '—',
      hint: s ? `high visit ${s.highest_visit ?? '—'}` : undefined,
    },
  ]

  return (
    <div className="min-h-screen">
      <AppHeader />

      <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
        <div className="mb-8">
          <p className="text-sm text-ink-400">Welcome back, {user?.display_name}</p>
          <h2 className="font-display text-4xl font-bold">Your game</h2>
        </div>

        {ongoing.data && ongoing.data.items.length > 0 && (
          <section className="mb-8">
            <h3 className="label">Resume a match</h3>
            <ul className="space-y-2">
              {ongoing.data.items.map((match) => (
                <li key={match.id}>
                  <Link
                    to={`/matches/${match.id}`}
                    className="card flex items-center justify-between px-4 py-3 transition hover:border-felt-600"
                  >
                    <span className="font-medium">
                      {match.players.map((p) => p.display_name).join(' vs ')}
                    </span>
                    <span className="text-sm text-ink-400">
                      <span className="font-display text-lg font-bold text-ink-100">
                        {match.players.map((p) => p.legs_won).join('–')}
                      </span>{' '}
                      · {GAME_LABELS[match.game_type]} · best of {match.best_of_legs}
                      <span className="ml-3 text-felt-400">Resume →</span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        )}

        {noHistory && (
          <section className="card mb-8 flex flex-col items-start gap-4 border-felt-800 bg-felt-900/30 p-6 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h3 className="font-display text-2xl font-bold">No darts thrown yet</h3>
              <p className="mt-1 text-ink-300">
                Play your first match and your averages, checkouts and 180s start
                counting from the very first dart.
              </p>
            </div>
            <Link to="/matches/new" className="btn-primary shrink-0 px-5 py-3">
              Start a match
            </Link>
          </section>
        )}

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {kpis.map((kpi) => (
            <div key={kpi.label} className="card p-5">
              <p className="text-sm text-ink-400">{kpi.label}</p>
              <p
                className={`score-display mt-2 text-5xl ${
                  kpi.value === '—' ? 'text-ink-600' : 'text-ink-100'
                }`}
              >
                {kpi.value}
              </p>
              {kpi.hint && <p className="mt-2 text-xs text-ink-500">{kpi.hint}</p>}
            </div>
          ))}
        </div>

        <div className="mt-8 flex flex-wrap gap-3">
          <Link to="/matches/new" className="btn-primary px-5 py-3">
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
