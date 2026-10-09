import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Route, Routes } from 'react-router-dom'

import { AuthProvider } from './auth/AuthContext'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { DashboardPage } from './pages/DashboardPage'
import { LiveScoringPage } from './pages/LiveScoringPage'
import { LoginPage } from './pages/LoginPage'
import { MatchHistoryPage } from './pages/MatchHistoryPage'
import { MatchSummaryPage } from './pages/MatchSummaryPage'
import { NewMatchPage } from './pages/NewMatchPage'
import { RegisterPage } from './pages/RegisterPage'

const queryClient = new QueryClient()

// Cached data belongs to the signed-in user; drop all of it when the
// session ends so a second person signing in on the same tab starts
// from an empty cache.
const clearCache = () => queryClient.clear()

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider onSignOut={clearCache}>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route element={<ProtectedRoute />}>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/matches" element={<MatchHistoryPage />} />
              <Route path="/matches/new" element={<NewMatchPage />} />
              <Route path="/matches/:matchId" element={<LiveScoringPage />} />
              <Route path="/matches/:matchId/summary" element={<MatchSummaryPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}
