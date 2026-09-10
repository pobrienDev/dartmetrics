import type { GameType } from '../api/types'

export const GAME_LABELS: Record<GameType, string> = {
  x01: '501',
  cricket: 'Cricket',
  halve_it: 'Halve It',
}

/** Tailwind classes for a small game-type chip. */
export const GAME_CHIP: Record<GameType, string> = {
  x01: 'bg-felt-900/70 text-felt-300 border-felt-800',
  cricket: 'bg-sky-950/70 text-sky-300 border-sky-900',
  halve_it: 'bg-purple-950/70 text-purple-300 border-purple-900',
}
