// Authentication state shared across the app.
//
// On mount, if a token is stored, we ask the backend who we are
// (GET /api/v1/me). Until that check finishes, `loading` is true so
// protected routes can wait instead of bouncing to /login.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'

import { api, clearToken, getToken, setToken } from '../api/client'
import type { TokenResponse, UserResponse } from '../api/types'

interface AuthState {
  user: UserResponse | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, displayName: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null)
  const [loading, setLoading] = useState<boolean>(() => getToken() !== null)

  useEffect(() => {
    if (!getToken()) return
    api<UserResponse>('/api/v1/me')
      .then(setUser)
      .catch(() => clearToken()) // expired/invalid token: start signed out
      .finally(() => setLoading(false))
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const token = await api<TokenResponse>('/api/v1/auth/login', {
      method: 'POST',
      body: { email, password },
    })
    setToken(token.access_token)
    setUser(await api<UserResponse>('/api/v1/me'))
  }, [])

  const register = useCallback(
    async (email: string, password: string, displayName: string) => {
      await api<UserResponse>('/api/v1/auth/register', {
        method: 'POST',
        body: { email, password, display_name: displayName },
      })
      await login(email, password)
    },
    [login],
  )

  const logout = useCallback(() => {
    // Stateless JWT: logout is discarding the token (see README).
    clearToken()
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>')
  return context
}
