// Dashboard: KPI placeholders, New Match entry point, and matches to
// resume (GET /matches?status=in_progress).

import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { api } from '../api/client'
import type { MatchListResponse, PlayerResponse, PlayerStats } from '../api/types'
import { useAuth } from '../auth/AuthContext'

export function DashboardPage() {
  const { user, logout } = useAuth()

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

  const kpis = [
    {
      label: '3-dart average',
      value: stats.data?.three_dart_average?.toFixed(1) ?? '—',
      hint: stats.data ? `${stats.data.total_darts} darts thrown` : undefined,
    },
    {
      label: 'Win rate',
      value:
        stats.data?.win_percentage !== null && stats.data?.win_percentage !== undefined
          ? `${stats.data.win_percentage.toFixed(0)}%`
          : '—',
      hint: stats.data
        ? `${stats.data.matches_won}–${stats.data.matches_played - stats.data.matches_won}`
        : undefined,
    },
    {
      label: 'Checkout %',
      value:
        stats.data?.checkout_percentage !== null &&
        stats.data?.checkout_percentage !== undefined
          ? `${stats.data.checkout_percentage.toFixed(0)}%`
          : '—',
      hint: stats.data
        ? `${stats.data.checkout_successes}/${stats.data.checkout_attempts} attempts`
        : undefined,
    },
    {
      label: '180s',
      value: stats.data ? String(stats.data.count_180) : '—',
      hint: stats.data ? `high visit ${stats.data.highest_visit ?? '—'}` : undefined,
    },
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="flex items-center justify-between border-b border-gray-200 bg-white px-6 py-4">
        <h1 className="text-xl font-bold text-gray-900">
          Dart<span className="text-emerald-600">Metrics</span>
        </h1>
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-600">{user?.display_name}</span>
          <button
            onClick={logout}
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-100"
          >
            Sign out
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-8">
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">
            Welcome back, {user?.display_name}
          </h2>
          <div className="flex items-center gap-3">
            <Link to="/matches" className="text-sm font-medium text-emerald-600 hover:underline">
              Match history
            </Link>
            <Link
              to="/matches/new"
              className="rounded-lg bg-emerald-600 px-4 py-2 font-semibold text-white hover:bg-emerald-700"
            >
              + New Match
            </Link>
          </div>
        </div>

        {ongoing.data && ongoing.data.items.length > 0 && (
          <section className="mb-8">
            <h3 className="mb-2 text-sm font-medium text-gray-500">Resume a match</h3>
            <ul className="space-y-2">
              {ongoing.data.items.map((match) => (
                <li key={match.id}>
                  <Link
                    to={`/matches/${match.id}`}
                    className="flex items-center justify-between rounded-xl bg-white px-4 py-3 shadow-sm hover:bg-emerald-50"
                  >
                    <span className="font-medium text-gray-800">
                      {match.players.map((p) => p.display_name).join(' vs ')}
                    </span>
                    <span className="text-sm text-gray-500">
                      {match.players.map((p) => p.legs_won).join('–')} · best of{' '}
                      {match.best_of_legs}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        )}

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {kpis.map((kpi) => (
            <div key={kpi.label} className="rounded-xl bg-white p-5 shadow-sm">
              <p className="text-sm text-gray-500">{kpi.label}</p>
              <p
                className={`mt-1 text-2xl font-bold ${
                  kpi.value === '—' ? 'text-gray-300' : 'text-gray-900'
                }`}
              >
                {kpi.value}
              </p>
              {kpi.hint && <p className="mt-0.5 text-xs text-gray-400">{kpi.hint}</p>}
            </div>
          ))}
        </div>
      </main>
    </div>
  )
}
