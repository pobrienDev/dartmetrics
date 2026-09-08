// The auth context and its hook live apart from <AuthProvider> so the
// provider's file exports only a component (keeps Vite fast refresh
// working for it).

import { createContext, useContext } from 'react'

import type { UserResponse } from '../api/types'

export interface AuthState {
  user: UserResponse | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, displayName: string) => Promise<void>
  logout: () => void
}

export const AuthContext = createContext<AuthState | null>(null)

export function useAuth(): AuthState {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>')
  return context
}
