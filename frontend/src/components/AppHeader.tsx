// Top bar shared by the signed-in pages: logo, primary nav, user menu.

import { Link, NavLink } from 'react-router-dom'

import { useAuth } from '../auth/useAuth'
import { Logo } from './Logo'

export function AppHeader() {
  const { user, logout } = useAuth()
  return (
    <header className="sticky top-0 z-10 border-b border-ink-800 bg-ink-950/80 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <div className="flex items-center gap-6">
          <Logo />
          <nav className="hidden items-center gap-1 sm:flex">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                `rounded-lg px-3 py-1.5 text-sm font-medium ${isActive ? 'bg-ink-800 text-ink-100' : 'text-ink-400 hover:text-ink-100'}`
              }
            >
              Dashboard
            </NavLink>
            <NavLink
              to="/matches"
              className={({ isActive }) =>
                `rounded-lg px-3 py-1.5 text-sm font-medium ${isActive ? 'bg-ink-800 text-ink-100' : 'text-ink-400 hover:text-ink-100'}`
              }
            >
              Match history
            </NavLink>
          </nav>
        </div>
        <div className="flex items-center gap-3">
          <Link to="/matches/new" className="btn-primary px-3.5 py-2 text-sm">
            + New Match
          </Link>
          <span className="hidden text-sm text-ink-400 sm:inline">{user?.display_name}</span>
          <button onClick={logout} className="btn-secondary px-3 py-2 text-sm">
            Sign out
          </button>
        </div>
      </div>
    </header>
  )
}
