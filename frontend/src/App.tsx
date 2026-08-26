import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Route, Routes } from 'react-router-dom'

import { AuthProvider } from './auth/AuthContext'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { DashboardPage } from './pages/DashboardPage'
import { LiveScoringPage } from './pages/LiveScoringPage'
import { LoginPage } from './pages/LoginPage'
import { MatchHistoryPage } from './pages/MatchHistoryPage'
import { NewMatchPage } from './pages/NewMatchPage'
import { RegisterPage } from './pages/RegisterPage'

const queryClient = new QueryClient()

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route element={<ProtectedRoute />}>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/matches" element={<MatchHistoryPage />} />
              <Route path="/matches/new" element={<NewMatchPage />} />
              <Route path="/matches/:matchId" element={<LiveScoringPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}
