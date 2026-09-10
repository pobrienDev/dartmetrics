// Wrapper for routes that require a signed-in user.

import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { useAuth } from './useAuth'

export function ProtectedRoute() {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return <div className="p-8 text-center text-ink-400">Loading…</div>
  }
  if (!user) {
    // Remember the page so login can return here (e.g. a live match
    // whose token expired mid-game).
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  }
  return <Outlet />
}
