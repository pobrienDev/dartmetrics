// Match history: filterable, paginated list of the user's matches
// (FR-010). In-progress matches resume scoring; finished ones open
// the match summary.

import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api/client'
import type { MatchListItem, MatchListResponse, MatchStatus } from '../api/types'
import { AppHeader } from '../components/AppHeader'
import { GAME_CHIP, GAME_LABELS } from '../utils/games'

const PAGE_SIZE = 10

const FILTERS: { label: string; value: MatchStatus | null }[] = [
  { label: 'All', value: null },
  { label: 'In progress', value: 'in_progress' },
  { label: 'Completed', value: 'completed' },
  { label: 'Cancelled', value: 'cancelled' },
]

const STATUS_BADGE: Record<MatchStatus, string> = {
  scheduled: 'bg-ink-700 text-ink-300',
  in_progress: 'bg-gold-500/15 text-gold-300',
  completed: 'bg-felt-900/70 text-felt-300',
  cancelled: 'bg-ink-700 text-ink-400',
}

function MatchCard({ match }: { match: MatchListItem }) {
  const [p1, p2] = match.players
  const winnerId = match.winner_player_id
  const href = match.status === 'in_progress' ? `/matches/${match.id}` : `/matches/${match.id}/summary`

  return (
    <Link
      to={href}
      className="card flex items-center justify-between gap-4 px-4 py-3 transition hover:border-felt-600"
    >
      <div className="min-w-0">
        <p className="font-medium">
          <span className={p1.player_id === winnerId ? 'text-felt-300' : ''}>{p1.display_name}</span>{' '}
          <span className="mx-1 font-display text-xl font-bold tabular-nums">
            {p1.legs_won}–{p2.legs_won}
          </span>{' '}
          <span className={p2.player_id === winnerId ? 'text-felt-300' : ''}>{p2.display_name}</span>
        </p>
        <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-ink-400">
          <span className={`rounded-md border px-1.5 py-0.5 font-medium ${GAME_CHIP[match.game_type]}`}>
            {GAME_LABELS[match.game_type]}
          </span>
          <span>best of {match.best_of_legs}</span>
          <span>·</span>
          <span>
            {new Date(match.created_at).toLocaleDateString(undefined, {
              day: 'numeric',
              month: 'short',
              year: 'numeric',
            })}
          </span>
        </p>
      </div>
      <span className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ${STATUS_BADGE[match.status]}`}>
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
    <div className="min-h-screen">
      <AppHeader />

      <main className="mx-auto max-w-2xl px-4 py-8 sm:px-6">
        <h1 className="mb-4 font-display text-4xl font-bold">Match history</h1>

        <div className="mb-4 flex flex-wrap gap-2">
          {FILTERS.map((filter) => (
            <button
              key={filter.label}
              onClick={() => {
                setStatus(filter.value)
                setOffset(0)
              }}
              className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${
                status === filter.value
                  ? 'bg-felt-500 text-ink-950'
                  : 'bg-ink-800 text-ink-300 hover:bg-ink-700'
              }`}
            >
              {filter.label}
            </button>
          ))}
        </div>

        {query.isLoading && <p className="text-ink-400">Loading…</p>}
        {query.isError && (
          <p role="alert" className="text-bust-400">
            Could not load matches.
          </p>
        )}

        {query.data && query.data.items.length === 0 && (
          <p className="card p-6 text-center text-ink-400">
            No matches here yet.{' '}
            <Link to="/matches/new" className="text-felt-400 hover:underline">
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
              className="btn-secondary px-3 py-1.5"
            >
              ← Newer
            </button>
            <span className="text-ink-400">
              {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
            </span>
            <button
              onClick={() => setOffset(offset + PAGE_SIZE)}
              disabled={!hasNext}
              className="btn-secondary px-3 py-1.5"
            >
              Older →
            </button>
          </div>
        )}
      </main>
    </div>
  )
}
