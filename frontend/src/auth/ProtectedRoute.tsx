// Wrapper for routes that require a signed-in user.

import { Navigate, Outlet } from 'react-router-dom'

import { useAuth } from './AuthContext'

export function ProtectedRoute() {
  const { user, loading } = useAuth()

  if (loading) {
    return <div className="p-8 text-center text-gray-500">Loading…</div>
  }
  if (!user) {
    return <Navigate to="/login" replace />
  }
  return <Outlet />
}
