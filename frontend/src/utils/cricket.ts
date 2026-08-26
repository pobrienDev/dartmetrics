// UI-side mirror of the Cricket marks rules — used ONLY to decide when
// a visit must auto-submit (board visibly closed) and to preview marks.
// The backend engine remains the authority on every outcome.

import type { DartRequest } from '../api/types'

export const CRICKET_TARGETS = [20, 19, 18, 17, 16, 15, 25]
const MARKS_TO_CLOSE = 3

export function marksAfterDarts(
  marks: Record<string, number>,
  darts: DartRequest[],
): Record<string, number> {
  const next = { ...marks }
  for (const dart of darts) {
    if (dart.multiplier === 'miss' || dart.segment === null) continue
    if (!CRICKET_TARGETS.includes(dart.segment)) continue
    const key = String(dart.segment)
    const current = next[key] ?? 0
    if (current >= MARKS_TO_CLOSE) continue
    const raw = { single: 1, double: 2, triple: 3 }[dart.multiplier]
    next[key] = Math.min(MARKS_TO_CLOSE, current + raw)
  }
  return next
}

export function boardClosed(marks: Record<string, number>): boolean {
  return CRICKET_TARGETS.every((t) => (marks[String(t)] ?? 0) >= MARKS_TO_CLOSE)
}

/** Classic cricket notation: 1 mark = /, 2 = X, closed = ◎ */
export function markSymbol(count: number): string {
  return ['·', '╱', '✕', '◎'][Math.min(count, 3)]
}
