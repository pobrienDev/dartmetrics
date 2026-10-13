// The last few visits of the leg, newest first, as the scoring screen
// records them from the server's replies.

import type { MatchState, TurnSummary } from '../api/types'
import { shortName } from '../utils/players'

export interface RecentVisit {
  turn: TurnSummary
  labels: string
  // Halve It only: the player's running total before and after the
  // round. The server stores every Halve It turn with points_scored 0
  // (the total lives in the leg state), so the row is rendered from
  // these instead.
  scoreBefore?: number | null
  scoreAfter?: number | null
}

function tone(turn: TurnSummary, halved: boolean, bigVisitsCount: boolean): string {
  if (turn.is_bust || halved) return 'text-bust-400'
  if (turn.is_checkout) return 'text-felt-300'
  if (bigVisitsCount && turn.points_scored >= 100) return 'text-gold-300'
  return 'text-ink-200'
}

function X01Result({ turn }: { turn: TurnSummary }) {
  const result = turn.is_bust ? 'BUST' : turn.is_checkout ? `${turn.points_scored} ✓ out` : turn.points_scored
  return (
    <>
      {'  '}
      {result}
      {'  '}
      <span className="text-ink-500">({turn.turn_start_score} → {turn.turn_end_score})</span>
    </>
  )
}

function HalveItResult({ delta, before, after }: { delta: number | null; before?: number | null; after?: number | null }) {
  return (
    <>
      {'  '}
      {delta == null ? '' : delta < 0 ? 'HALVED' : `+${delta}`}
      {before != null && after != null && (
        <>
          {'  '}
          <span className="text-ink-500">({before} → {after})</span>
        </>
      )}
    </>
  )
}

export function RecentVisits({ turns, state }: { turns: RecentVisit[]; state: MatchState }) {
  const isCricket = state.game_type === 'cricket'
  const isHalveIt = state.game_type === 'halve_it'
  return (
    <div className="mt-6">
      <p className="label">Recent visits</p>
      <ul className="space-y-1 text-sm">
        {turns.map(({ turn, labels, scoreBefore, scoreAfter }) => {
          const who = state.players.find((p) => p.player_id === turn.player_id)
          // Halve It: a round either adds its qualifying points or halves,
          // judged from the running total (points_scored is always 0).
          const delta =
            isHalveIt && scoreBefore != null && scoreAfter != null ? scoreAfter - scoreBefore : null
          return (
            <li key={turn.id} className="flex justify-between rounded-lg bg-ink-800 px-3 py-2">
              <span className="text-ink-300">{who ? shortName(who) : ''}</span>
              <span className={`font-mono ${tone(turn, delta != null && delta < 0, !isCricket)}`}>
                {labels}
                {isCricket ? (
                  turn.is_checkout && ' ◎ closed'
                ) : isHalveIt ? (
                  <HalveItResult delta={delta} before={scoreBefore} after={scoreAfter} />
                ) : (
                  <X01Result turn={turn} />
                )}
              </span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
