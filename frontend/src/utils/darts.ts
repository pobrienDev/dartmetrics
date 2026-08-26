// Pure dart helpers shared by the scoring UI. Kept free of React so
// they can be unit tested directly.
//
// These MIRROR backend rules for UI convenience only (when to stop
// collecting darts in a visit); the backend remains the authority on
// every outcome.

import type { DartRequest } from '../api/types'

export function dartScore(dart: DartRequest): number {
  if (dart.multiplier === 'miss' || dart.segment === null) return 0
  const factor = { single: 1, double: 2, triple: 3 }[dart.multiplier]
  return dart.segment * factor
}

export function dartLabel(dart: DartRequest): string {
  if (dart.multiplier === 'miss') return 'Miss'
  const prefix = { single: '', double: 'D', triple: 'T' }[dart.multiplier]
  return `${prefix}${dart.segment}`
}

/** A visit must be submitted when 3 darts are thrown, or the entered
 * darts leave a score of 1 or less (checkout or certain bust — the
 * server decides which). */
export function visitMustEnd(dartsInVisit: number, remainingAfter: number): boolean {
  return dartsInVisit >= 3 || remainingAfter <= 1
}
