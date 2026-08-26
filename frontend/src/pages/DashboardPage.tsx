// Dashboard: KPI placeholders, New Match entry point, and matches to
// resume (GET /matches?status=in_progress).

import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { api } from '../api/client'
import type { MatchListResponse } from '../api/types'
import { useAuth } from '../auth/AuthContext'

export function DashboardPage() {
  const { user, logout } = useAuth()

  const ongoing = useQuery({
    queryKey: ['matches', 'in_progress'],
    queryFn: () => api<MatchListResponse>('/api/v1/matches?status=in_progress'),
  })

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
          <Link
            to="/matches/new"
            className="rounded-lg bg-emerald-600 px-4 py-2 font-semibold text-white hover:bg-emerald-700"
          >
            + New Match
          </Link>
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
          {['3-dart average', 'Win rate', 'Checkout %', '180s'].map((label) => (
            <div key={label} className="rounded-xl bg-white p-5 shadow-sm">
              <p className="text-sm text-gray-500">{label}</p>
              <p className="mt-1 text-2xl font-bold text-gray-300">—</p>
            </div>
          ))}
        </div>
      </main>
    </div>
  )
}
