// Dashboard shell: proves the authenticated round-trip works and
// gives later phases (KPIs, recent matches) a home.

import { useAuth } from '../auth/AuthContext'

export function DashboardPage() {
  const { user, logout } = useAuth()

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
        <h2 className="mb-6 text-lg font-semibold text-gray-900">
          Welcome back, {user?.display_name}
        </h2>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {['3-dart average', 'Win rate', 'Checkout %', '180s'].map((label) => (
            <div key={label} className="rounded-xl bg-white p-5 shadow-sm">
              <p className="text-sm text-gray-500">{label}</p>
              <p className="mt-1 text-2xl font-bold text-gray-300">—</p>
            </div>
          ))}
        </div>

        <p className="mt-8 text-sm text-gray-400">
          Match creation and live scoring arrive in the next phase.
        </p>
      </main>
    </div>
  )
}
