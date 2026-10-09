// Wrapper for routes that require a signed-in user.

import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { useAuth } from './useAuth'

export function ProtectedRoute() {
  const { user, loading, startupError, retry } = useAuth()
  const location = useLocation()

  if (loading) {
    return <div className="p-8 text-center text-ink-400">Loading…</div>
  }
  if (!user && startupError) {
    // The token is still stored and may well be fine; offer a retry
    // rather than bouncing to login.
    return (
      <div role="alert" className="p-8 text-center text-ink-300">
        <p>{startupError}</p>
        <button onClick={retry} className="btn-secondary mt-4 min-h-11 px-4 py-2">
          Try again
        </button>
      </div>
    )
  }
  if (!user) {
    // Remember the page so login can return here (e.g. a live match
    // whose token expired mid-game).
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  }
  return <Outlet />
}
