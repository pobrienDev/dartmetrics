// Match history: filterable, paginated list of the user's matches
// (FR-010). In-progress matches resume scoring; completed ones open
// the match's final state.

import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api/client'
import type { MatchListItem, MatchListResponse, MatchStatus } from '../api/types'

const PAGE_SIZE = 10

const FILTERS: { label: string; value: MatchStatus | null }[] = [
  { label: 'All', value: null },
  { label: 'In progress', value: 'in_progress' },
  { label: 'Completed', value: 'completed' },
  { label: 'Cancelled', value: 'cancelled' },
]

const STATUS_BADGE: Record<MatchStatus, string> = {
  scheduled: 'bg-gray-100 text-gray-600',
  in_progress: 'bg-amber-100 text-amber-700',
  completed: 'bg-emerald-100 text-emerald-700',
  cancelled: 'bg-gray-100 text-gray-500',
}

function MatchCard({ match }: { match: MatchListItem }) {
  const [p1, p2] = match.players
  const winnerName = match.players.find(
    (p) => p.player_id === match.winner_player_id,
  )?.display_name

  return (
    <Link
      to={`/matches/${match.id}`}
      className="flex items-center justify-between rounded-xl bg-white px-4 py-3 shadow-sm hover:bg-emerald-50"
    >
      <div>
        <p className="font-medium text-gray-900">
          {p1.display_name}{' '}
          <span className="mx-1 font-bold tabular-nums">
            {p1.legs_won}–{p2.legs_won}
          </span>{' '}
          {p2.display_name}
        </p>
        <p className="mt-0.5 text-xs text-gray-500">
          {new Date(match.created_at).toLocaleDateString(undefined, {
            day: 'numeric',
            month: 'short',
            year: 'numeric',
          })}
          {' · '}
          {match.game_type === 'x01' ? '501' : match.game_type.replace('_', ' ')}
          {' · '}best of {match.best_of_legs}
          {winnerName && ` · ${winnerName} won`}
        </p>
      </div>
      <span
        className={`rounded-full px-2.5 py-1 text-xs font-medium ${STATUS_BADGE[match.status]}`}
      >
        {match.status.replace('_', ' ')}
      </span>
    </Link>
  )
}

export function MatchHistoryPage() {
  const [status, setStatus] = useState<MatchStatus | null>(null)
  const [offset, setOffset] = useState(0)

  const query = useQuery({
    queryKey: ['matches', 'history', status, offset],
    queryFn: () => {
      const params = new URLSearchParams({
        limit: String(PAGE_SIZE),
        offset: String(offset),
      })
      if (status) params.set('status', status)
      return api<MatchListResponse>(`/api/v1/matches?${params}`)
    },
  })

  const total = query.data?.total ?? 0
  const hasPrev = offset > 0
  const hasNext = offset + PAGE_SIZE < total

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="flex items-center justify-between border-b border-gray-200 bg-white px-6 py-4">
        <Link to="/" className="text-sm text-emerald-600 hover:underline">
          ← Dashboard
        </Link>
        <Link
          to="/matches/new"
          className="rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-emerald-700"
        >
          + New Match
        </Link>
      </header>

      <main className="mx-auto max-w-2xl px-6 py-8">
        <h1 className="mb-4 text-2xl font-bold text-gray-900">Match history</h1>

        <div className="mb-4 flex gap-2">
          {FILTERS.map((filter) => (
            <button
              key={filter.label}
              onClick={() => {
                setStatus(filter.value)
                setOffset(0)
              }}
              className={`rounded-full px-3 py-1.5 text-sm font-medium ${
                status === filter.value
                  ? 'bg-emerald-600 text-white'
                  : 'bg-white text-gray-600 shadow-sm hover:bg-gray-100'
              }`}
            >
              {filter.label}
            </button>
          ))}
        </div>

        {query.isLoading && <p className="text-gray-500">Loading…</p>}
        {query.isError && (
          <p role="alert" className="text-red-600">
            Could not load matches.
          </p>
        )}

        {query.data && query.data.items.length === 0 && (
          <p className="rounded-xl bg-white p-6 text-center text-gray-500 shadow-sm">
            No matches here yet.{' '}
            <Link to="/matches/new" className="text-emerald-600 hover:underline">
              Start one?
            </Link>
          </p>
        )}

        <div className="space-y-2">
          {query.data?.items.map((match) => (
            <MatchCard key={match.id} match={match} />
          ))}
        </div>

        {total > PAGE_SIZE && (
          <div className="mt-6 flex items-center justify-between text-sm">
            <button
              onClick={() => setOffset(offset - PAGE_SIZE)}
              disabled={!hasPrev}
              className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 font-medium text-gray-700 hover:bg-gray-100 disabled:opacity-40"
            >
              ← Newer
            </button>
            <span className="text-gray-500">
              {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
            </span>
            <button
              onClick={() => setOffset(offset + PAGE_SIZE)}
              disabled={!hasNext}
              className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 font-medium text-gray-700 hover:bg-gray-100 disabled:opacity-40"
            >
              Older →
            </button>
          </div>
        )}
      </main>
    </div>
  )
}
